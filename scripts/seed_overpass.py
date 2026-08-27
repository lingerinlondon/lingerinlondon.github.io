"""Desk-seed candidate places from OpenStreetMap.

Run as: python -m scripts.seed_overpass

Writes data/candidates.geojson: places that look plausible from a desk, all
marked verified: false, for someone to go and sit in. It is a list of things to
walk to, not data about them.

The mapping rule, which matters more than the query: a tag becomes a field only
where the tag says the thing the field asks. Everything else stays null. A null
is a prompt to go and look; a wrong value is indistinguishable from a real one
a year later. This is why the output is mostly nulls, and that is correct.

The one categorical inference made here is `setting`, taken from the primary
tag: a garden is outdoors and a library is indoors by definition rather than by
judgement. If that ever feels like a stretch, delete SETTING_BY_TAG.
"""

import argparse
import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from scripts import geo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(ROOT, ".cache")
OUT_PATH = os.path.join(ROOT, "data", "candidates.geojson")
PLACES_PATH = os.path.join(ROOT, "data", "places.geojson")

ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]

USER_AGENT = (
    "central-london-third-places/0.1 "
    "(+https://github.com/cormac/central-london-third-places; desk-seeding, low volume)"
)

# The starting categories. Deliberately includes non-establishments — the point
# is to catch gardens and community halls, not another list of cafes.
SELECTORS = [
    ('amenity', 'library'),
    ('amenity', 'community_centre'),
    ('amenity', 'arts_centre'),
    ('tourism', 'museum'),
    ('leisure', 'garden'),
]

# Tags worth keeping verbatim even where no field consumes them yet. The survey
# is expected to turn some of these into fields; keeping them now means not
# re-querying Overpass when it does.
KEEP_TAGS = [
    'name', 'fee', 'access', 'indoor_seating', 'outdoor_seating',
    'internet_access', 'opening_hours', 'wheelchair', 'toilets', 'operator',
    'amenity', 'tourism', 'leisure',
]

SETTING_BY_TAG = {
    ('leisure', 'garden'): 'outdoor',
    ('amenity', 'library'): 'indoor',
    ('amenity', 'community_centre'): 'indoor',
    ('amenity', 'arts_centre'): 'indoor',
    ('tourism', 'museum'): 'indoor',
}

FEE_TO_PAYMENT = {
    'no': 'none',
    'yes': 'required',
    'donation': 'optional',
    'suggested': 'optional',
}


def poly_clause(polygons):
    """Overpass poly filter: 'lat lon lat lon ...' for the outer ring.

    Only the first polygon's outer ring is sent. The local point-in-polygon
    test in geo.py is what actually decides scope; this just avoids asking
    Overpass for all of London.
    """
    ring = polygons[0][0]
    pts = ring[:-1] if ring[0] == ring[-1] else ring
    return " ".join("%.6f %.6f" % (lat, lon) for lon, lat in pts)


def build_query(polygons, timeout=180):
    clause = poly_clause(polygons)
    parts = ['[out:json][timeout:%d];' % timeout, '(']
    for key, value in SELECTORS:
        parts.append('  nwr["%s"="%s"](poly:"%s");' % (key, value, clause))
    parts.append(');')
    parts.append('out center tags;')
    return "\n".join(parts)


def cache_path(query):
    digest = hashlib.sha256(query.encode('utf-8')).hexdigest()[:16]
    return os.path.join(CACHE_DIR, 'overpass-%s.json' % digest)


def fetch(query, refresh=False, attempts=4, sleep=time.sleep):
    """Ask Overpass, with backoff, caching the raw response.

    Overpass is run by volunteers and rate-limits accordingly. Reruns read the
    cache so iterating on the mapping code costs the API nothing.
    """
    path = cache_path(query)
    if os.path.exists(path) and not refresh:
        with open(path) as fh:
            return json.load(fh), 'the cached response in %s' % os.path.relpath(path, ROOT)
    if not os.path.isdir(CACHE_DIR):
        os.makedirs(CACHE_DIR)

    data = urllib.parse.urlencode({'data': query}).encode('utf-8')
    last_error = None
    for attempt in range(attempts):
        endpoint = ENDPOINTS[attempt % len(ENDPOINTS)]
        try:
            request = urllib.request.Request(
                endpoint, data=data, headers={'User-Agent': USER_AGENT}
            )
            with urllib.request.urlopen(request, timeout=300) as response:
                payload = json.loads(response.read().decode('utf-8'))
            with open(path, 'w') as fh:
                json.dump(payload, fh)
            return payload, '%s (cached to %s)' % (endpoint, os.path.relpath(path, ROOT))
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError) as exc:
            last_error = exc
            status = getattr(exc, 'code', None)
            if status and status not in (429, 500, 502, 503, 504):
                raise
            wait = 5 * (2 ** attempt)
            sys.stderr.write(
                "Overpass did not answer (%s). Waiting %ds, then trying %s.\n"
                % (exc, wait, ENDPOINTS[(attempt + 1) % len(ENDPOINTS)])
            )
            if attempt < attempts - 1:
                sleep(wait)
    raise SystemExit(
        "Overpass could not be reached after %d attempts. The last error was: %s\n"
        "It is a volunteer-run service and is sometimes simply busy; try again later."
        % (attempts, last_error)
    )


def element_point(element):
    if 'lat' in element and 'lon' in element:
        return element['lon'], element['lat']
    center = element.get('center')
    if center:
        return center['lon'], center['lat']
    return None


def map_element(element):
    """One OSM element -> one schema-shaped feature, or None to skip it."""
    tags = element.get('tags') or {}
    name = (tags.get('name') or '').strip()
    if not name:
        return None  # the schema needs a name, and an unnamed candidate is unwalkable
    point = element_point(element)
    if point is None:
        return None

    props = {
        'id': 'osm:%s/%s' % (element['type'], element['id']),
        'name': name[:120],
        'payment_to_enter': None,
        'payment_to_sit': None,
        'time_pressure': None,
        'conversation': None,
        'activity': None,
        'seating': None,
        'setting': None,
        'support_options': None,
        'why': None,
        'verified': False,
        'verified_date': None,
    }

    fee = tags.get('fee')
    if fee in FEE_TO_PAYMENT:
        props['payment_to_enter'] = FEE_TO_PAYMENT[fee]
    if fee in ('donation', 'suggested'):
        props['support_options'] = ['donation']

    for key, value in SETTING_BY_TAG.items():
        if tags.get(key[0]) == key[1]:
            props['setting'] = value
            break

    kept = {k: v for k, v in tags.items() if k in KEEP_TAGS}
    props['osm_tags'] = kept or None

    return {
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [round(point[0], 6), round(point[1], 6)]},
        'properties': props,
    }


OSM_DERIVED = ('payment_to_enter', 'support_options', 'setting', 'osm_tags', 'name')


def merge(existing, fresh):
    """Refresh OSM-derived values; never overwrite something a human filled in.

    Running the seeder twice must not undo an afternoon of fieldwork.
    """
    merged = dict(fresh['properties'])
    old = existing['properties']
    for field, value in old.items():
        if field in ('id',):
            continue
        if field in OSM_DERIVED:
            continue
        if value is not None:
            merged[field] = value
    if old.get('verified'):
        merged['verified'] = True
        merged['verified_date'] = old.get('verified_date')
    return {'type': 'Feature', 'geometry': fresh['geometry'], 'properties': merged}


def load_existing(path):
    if not os.path.exists(path):
        return {}
    with open(path) as fh:
        doc = json.load(fh)
    return {
        f['properties']['id']: f
        for f in doc.get('features', [])
        if (f.get('properties') or {}).get('id')
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--refresh', action='store_true',
                        help='Ignore the cached Overpass response and ask again.')
    parser.add_argument('--from-cache-only', action='store_true',
                        help='Fail rather than touch the network. Used by the tests.')
    parser.add_argument('--out', default=OUT_PATH)
    parser.add_argument('--response', help='Read a saved Overpass JSON response instead of querying.')
    args = parser.parse_args(argv)

    polygons = geo.load_boundary()
    query = build_query(polygons)

    if args.response:
        with open(args.response) as fh:
            payload = json.load(fh)
        source = args.response
    elif args.from_cache_only:
        path = cache_path(query)
        if not os.path.exists(path):
            raise SystemExit('No cached response at %s, and --from-cache-only was given.' % path)
        with open(path) as fh:
            payload = json.load(fh)
        source = os.path.relpath(path, ROOT)
    else:
        payload, source = fetch(query, refresh=args.refresh)

    elements = payload.get('elements', [])
    promoted = set(load_existing(PLACES_PATH))
    existing = load_existing(args.out)

    features = {}
    skipped_unnamed = 0
    skipped_outside = 0
    skipped_promoted = 0

    for element in elements:
        feature = map_element(element)
        if feature is None:
            skipped_unnamed += 1
            continue
        lon, lat = feature['geometry']['coordinates']
        if not geo.contains(polygons, lon, lat):
            skipped_outside += 1
            continue
        ident = feature['properties']['id']
        if ident in promoted:
            skipped_promoted += 1
            continue
        if ident in existing:
            feature = merge(existing[ident], feature)
        features[ident] = feature

    ordered = [features[k] for k in sorted(features)]
    doc = {'type': 'FeatureCollection', 'features': ordered}
    with open(args.out, 'w') as fh:
        json.dump(doc, fh, indent=2, ensure_ascii=False, sort_keys=False)
        fh.write('\n')

    print('Read %d elements from %s' % (len(elements), source))
    print('Wrote %d candidates to %s' % (len(ordered), os.path.relpath(args.out, ROOT)))
    print('  skipped %d with no name, %d outside the boundary, %d already in places.geojson'
          % (skipped_unnamed, skipped_outside, skipped_promoted))
    filled = sum(1 for f in ordered if f['properties']['payment_to_enter'] is not None)
    print('  %d have a payment_to_enter from an OSM fee tag; the rest are null, '
          'which is a list of things to go and check' % filled)
    return 0


if __name__ == '__main__':
    sys.exit(main())
