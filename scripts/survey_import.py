"""Turn survey rows into schema-valid features.

Run as: python -m scripts.survey_import visits.csv --out data/places.geojson

Takes whatever gets filled in on a phone or on paper — a flat CSV or a JSON
list, one row per visit — and emits GeoJSON. It exists so that fieldwork is
never blocked on tooling, so it is deliberately dumb: it maps columns to
fields, tidies obvious shorthand, and refuses to invent anything.

Rows it cannot map are reported, with the row number and the reason, and the
run exits non-zero. A survey tool that silently drops a visit is worse than no
survey tool, because you only find out months later when the notebook is gone.

Column names are matched loosely (case, spaces, hyphens and underscores are all
the same). Anything the schema does not define is reported, not discarded
quietly. Run with --template to print a blank capture sheet.
"""

import argparse
import csv
import datetime
import json
import os
import sys

from scripts import schema as schema_mod

GATES = {g["field"]: g for g in schema_mod.gates()}

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# Shorthand people actually write, per field. Anything not here and not an enum
# value is reported rather than guessed at.
SYNONYMS = {
    "payment_to_enter": {"free": "none", "no": "none", "n": "none", "nothing": "none",
                         "donation": "optional", "suggested": "optional", "optional": "optional",
                         "paid": "required", "yes": "required", "y": "required",
                         "ticket": "required", "fee": "required"},
    "payment_to_sit": {"free": "none", "no": "none", "n": "none", "nothing": "none",
                       "donation": "optional", "optional": "optional", "tolerated": "optional",
                       "paid": "required", "yes": "required", "y": "required",
                       "customers": "required", "purchase": "required"},
    "time_pressure": {"no": "none", "n": "none", "nothing": "none", "never": "none",
                      "felt": "implied", "some": "implied", "subtle": "implied",
                      "implied": "implied",
                      "yes": "enforced", "y": "enforced", "limit": "enforced",
                      "asked": "enforced", "sign": "enforced"},
    "conversation": {"no": "discouraged", "n": "discouraged", "silent": "discouraged",
                     "quiet": "discouraged", "hushed": "discouraged",
                     "yes": "possible", "y": "possible", "ok": "possible", "fine": "possible",
                     "loud": "expected", "social": "expected", "chatty": "expected"},
    "activity": {"no": "discouraged", "n": "discouraged",
                 "yes": "possible", "y": "possible", "ok": "possible", "fine": "possible",
                 "laptops": "expected", "working": "expected", "study": "expected"},
    "seating": {"bench": "fixed", "benches": "fixed", "bolted": "fixed", "pews": "fixed",
                "chairs": "movable", "loose": "movable", "moveable": "movable",
                "sofa": "soft", "sofas": "soft", "armchairs": "soft",
                "no": "none", "n": "none", "nowhere": "none", "standing": "none"},
    "setting": {"in": "indoor", "inside": "indoor", "internal": "indoor",
                "out": "outdoor", "outside": "outdoor", "open": "outdoor",
                "arcade": "covered", "sheltered": "covered", "under cover": "covered"},
}

# Column aliases for things a capture sheet calls something else.
COLUMN_ALIASES = {
    "osm_id": "id", "osm": "id", "id": "id", "ref": "id",
    "place": "name", "name": "name",
    "spot": "spot", "where": "spot", "whereabouts": "spot", "which_part": "spot",
    "credit": "suggested_by", "suggested_by": "suggested_by", "contributor": "suggested_by",
    "notes": "why", "why": "why", "sentence": "why", "one_sentence": "why",
    "date": "verified_date", "visited": "verified_date", "visit_date": "verified_date",
    "support": "support_options", "support_options": "support_options",
    "lat": "lat", "latitude": "lat", "lon": "lon", "lng": "lon", "long": "lon",
    "longitude": "lon",
    "payment_enter": "payment_to_enter", "entry": "payment_to_enter",
    "payment_sit": "payment_to_sit", "sit": "payment_to_sit",
    "pressure": "time_pressure", "time": "time_pressure",
    "talk": "conversation", "talking": "conversation",
}

GEOMETRY_COLUMNS = ("lat", "lon")

SKIP_VALUES = ("", "-", "n/a", "na", "?", "unknown", "tbd")


def normalise_key(key):
    k = (key or "").strip().lower().replace("-", "_").replace(" ", "_")
    while "__" in k:
        k = k.replace("__", "_")
    return COLUMN_ALIASES.get(k, k)


class RowProblem(Exception):
    pass


def coerce(field, raw, fields):
    """Take what was written, return what the schema allows, or complain."""
    value = (raw or "").strip() if isinstance(raw, str) else raw
    if value is None or (isinstance(value, str) and value.lower() in SKIP_VALUES):
        return None

    spec = fields[field]

    if field == "support_options":
        if isinstance(value, list):
            parts = value
        else:
            parts = [p.strip() for p in str(value).replace(";", ",").split(",")]
        allowed = schema_mod.enum_values("support_options")
        out = []
        for part in parts:
            if not part:
                continue
            key = part.lower().replace(" ", "_")
            if key not in allowed:
                raise RowProblem(
                    "support_options: %r is not one of %s" % (part, ", ".join(allowed))
                )
            if key not in out:
                out.append(key)
        return out or None

    if field == "verified":
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in ("1", "true", "yes", "y", "verified")

    if field == "verified_date":
        text = str(value).strip()
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y"):
            try:
                return datetime.datetime.strptime(text, fmt).date().isoformat()
            except ValueError:
                continue
        raise RowProblem(
            "verified_date: %r is not a date this understands. Try 2026-08-27 or 27/08/2026."
            % text
        )

    allowed = schema_mod.enum_values(field)
    if allowed:
        text = str(value).strip().lower()
        canonical = text if text in allowed else SYNONYMS.get(field, {}).get(text)
        if canonical in allowed:
            return canonical
        gate = GATES.get(field)
        if gate and canonical:
            # A real answer, and the place does not qualify. Say that, rather
            # than implying the sheet was filled in wrongly.
            raise RowProblem("%s: %r means this place does not qualify. %s"
                             % (field, value, gate["reason"]))
        raise RowProblem(
            "%s: %r is not one of %s (and is not shorthand this recognises)"
            % (field, value, ", ".join(allowed))
        )

    return str(value).strip()


def read_rows(path):
    with open(path, newline="", encoding="utf-8-sig") as fh:
        if path.lower().endswith(".json"):
            data = json.load(fh)
            if isinstance(data, dict) and "rows" in data:
                data = data["rows"]
            if not isinstance(data, list):
                raise SystemExit("%s should hold a list of rows." % path)
            return data
        return list(csv.DictReader(fh))


def convert(rows, default_date=None):
    """Return (features, problems). One row in, at most one feature out."""
    fields = schema_mod.fields()
    known = set(fields) | set(GEOMETRY_COLUMNS)

    features = []
    problems = []

    for number, row in enumerate(rows, start=2):  # row 1 is the header
        props = {}
        lat = lon = None
        unknown = []
        row_problems = []
        bad_geometry = False
        bad_date = False

        for raw_key, raw_value in row.items():
            key = normalise_key(raw_key)
            if key not in known:
                if raw_value not in (None, "") and key:
                    unknown.append(str(raw_key).strip())
                continue
            if key in GEOMETRY_COLUMNS:
                text = str(raw_value or "").strip()
                if text:
                    try:
                        if key == "lat":
                            lat = float(text)
                        else:
                            lon = float(text)
                    except ValueError:
                        row_problems.append("%s: %r is not a number" % (key, raw_value))
                        bad_geometry = True
                continue
            try:
                value = coerce(key, raw_value, fields)
            except RowProblem as exc:
                row_problems.append(str(exc))
                if key == "verified_date":
                    bad_date = True
                continue
            if value is not None:
                props[key] = value

        if unknown:
            row_problems.append(
                "columns the schema does not define: %s. Either add the field to "
                "schema/place.schema.json or drop the column." % ", ".join(sorted(set(unknown)))
            )

        if not props.get("id"):
            row_problems.append(
                "no id. Every place is keyed to an OSM element, like osm:way/123456 — "
                "look it up on openstreetmap.org and put it in an id column."
            )
        if not props.get("name"):
            row_problems.append("no name.")

        # A visit is a verification unless the row says otherwise.
        props.setdefault("verified", True)
        if props["verified"] and not props.get("verified_date"):
            if default_date:
                props["verified_date"] = default_date
            elif not bad_date:
                # If the date column was there but unreadable, that has been said already.
                row_problems.append(
                    "no date for the visit. Add a date column, or pass --date 2026-08-27."
                )

        geometry = None
        if lat is not None and lon is not None:
            geometry = {"type": "Point", "coordinates": [round(lon, 6), round(lat, 6)]}
        elif not bad_geometry:
            row_problems.append(
                "no location. Add lat and lon columns — right-click the place on "
                "openstreetmap.org and choose 'show address' to read them off."
            )

        if row_problems:
            problems.append((number, props.get("name") or props.get("id") or "unnamed", row_problems))
            continue

        # Emit fields in schema order so git diffs stay readable across imports.
        ordered = dict((k, props[k]) for k in fields if k in props)
        ordered.update((k, v) for k, v in props.items() if k not in ordered)
        features.append({"type": "Feature", "geometry": geometry, "properties": ordered})

    return features, problems


TEMPLATE_COLUMNS = [
    "id", "name", "spot", "lat", "lon", "date", "payment_to_enter", "payment_to_sit",
    "time_pressure", "conversation", "activity", "seating", "setting",
    "support_options", "why",
]


def print_template():
    writer = csv.writer(sys.stdout)
    writer.writerow(TEMPLATE_COLUMNS)
    writer.writerow([
        "osm:way/123456", "The place", "top floor, by the window", "51.5194", "-0.1270", "2026-08-27",
        "free", "free", "no", "quiet", "yes", "chairs", "in", "cafe,donation",
        "One sentence on why this is here.",
    ])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("input", nargs="?", help="A CSV or JSON file, one row per visit.")
    parser.add_argument("--out", help="Where to write. Defaults to stdout.")
    parser.add_argument("--date", help="Visit date for rows that do not carry one.")
    parser.add_argument("--template", action="store_true", help="Print a blank capture sheet and exit.")
    args = parser.parse_args(argv)

    if args.template:
        print_template()
        return 0
    if not args.input:
        parser.error("give it a CSV or JSON file, or --template")

    rows = read_rows(args.input)
    features, problems = convert(rows, args.date)

    doc = {"type": "FeatureCollection", "features": features}
    text = json.dumps(doc, indent=2, ensure_ascii=False) + "\n"
    if args.out:
        with open(args.out, "w") as fh:
            fh.write(text)
    else:
        sys.stdout.write(text)

    where = args.out or "stdout"
    sys.stderr.write("\n%d of %d rows became features (%s).\n" % (len(features), len(rows), where))

    if problems:
        sys.stderr.write("\n%d row%s could not be mapped, and none of them were dropped "
                         "quietly:\n\n" % (len(problems), "" if len(problems) == 1 else "s"))
        for number, label, reasons in problems:
            sys.stderr.write("  row %d — %s\n" % (number, label))
            for reason in reasons:
                sys.stderr.write("    %s\n" % reason)
            sys.stderr.write("\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
