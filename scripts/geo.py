"""Boundary geometry, in the standard library.

Deliberately boring: ray casting and a bit of trigonometry, no shapely. The
boundary is one small polygon and the corpus is a few hundred points, so the
dependency would buy speed nobody needs and cost a GEOS binary in CI.
"""

import json
import math
import os

BOUNDARY_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "boundary.geojson"
)

# CLAUDE.md: "Where a road forms the boundary, places fronting either side are in
# scope." The polygon is drawn down the middle of those roads, so a place on the
# far pavement lands just outside it. This tolerance is that convention, made
# numeric. It is not a fudge factor for a sloppy boundary — widen the polygon for
# that instead.
ROAD_TOLERANCE_M = 25.0

_EARTH_R = 6371008.8


def load_boundary(path=BOUNDARY_PATH):
    """Return the boundary as a list of polygons, each a list of rings."""
    with open(path) as fh:
        doc = json.load(fh)

    geoms = []
    if doc.get("type") == "FeatureCollection":
        geoms = [f["geometry"] for f in doc["features"] if f.get("geometry")]
    elif doc.get("type") == "Feature":
        geoms = [doc["geometry"]]
    else:
        geoms = [doc]

    polygons = []
    for g in geoms:
        if g["type"] == "Polygon":
            polygons.append(g["coordinates"])
        elif g["type"] == "MultiPolygon":
            polygons.extend(g["coordinates"])
        else:
            raise ValueError(
                "data/boundary.geojson must contain Polygon or MultiPolygon "
                "geometry, found %s" % g["type"]
            )
    if not polygons:
        raise ValueError("data/boundary.geojson contains no polygons")
    return polygons


def bbox(polygons):
    xs, ys = [], []
    for rings in polygons:
        for x, y in rings[0]:
            xs.append(x)
            ys.append(y)
    return min(xs), min(ys), max(xs), max(ys)


def _ring_contains(ring, x, y):
    """Ray casting. Points exactly on an edge are handled by the caller."""
    inside = False
    n = len(ring)
    for i in range(n - 1):
        x1, y1 = ring[i][0], ring[i][1]
        x2, y2 = ring[i + 1][0], ring[i + 1][1]
        if (y1 > y) != (y2 > y):
            x_cross = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
            if x_cross > x:
                inside = not inside
    return inside


def _metres_per_degree(lat):
    return _EARTH_R * math.pi / 180.0 * math.cos(math.radians(lat)), _EARTH_R * math.pi / 180.0


def _point_segment_distance_m(px, py, x1, y1, x2, y2):
    """Distance in metres, on a local flat projection centred on the point."""
    kx, ky = _metres_per_degree(py)
    ax, ay = (x1 - px) * kx, (y1 - py) * ky
    bx, by = (x2 - px) * kx, (y2 - py) * ky
    dx, dy = bx - ax, by - ay
    seg_sq = dx * dx + dy * dy
    if seg_sq == 0.0:
        return math.hypot(ax, ay)
    t = -(ax * dx + ay * dy) / seg_sq
    t = max(0.0, min(1.0, t))
    return math.hypot(ax + t * dx, ay + t * dy)


def distance_to_boundary_m(polygons, x, y):
    """Shortest distance in metres from a point to the boundary outline."""
    best = float("inf")
    for rings in polygons:
        for ring in rings:
            for i in range(len(ring) - 1):
                d = _point_segment_distance_m(
                    x, y, ring[i][0], ring[i][1], ring[i + 1][0], ring[i + 1][1]
                )
                if d < best:
                    best = d
    return best


def contains(polygons, x, y, tolerance_m=ROAD_TOLERANCE_M):
    """Is this point inside the project boundary?

    Inside a ring and outside its holes counts. So does being within
    tolerance_m of the outline, which is the either-side-of-the-road convention.
    """
    for rings in polygons:
        outer = rings[0]
        if _ring_contains(outer, x, y):
            in_hole = any(_ring_contains(h, x, y) for h in rings[1:])
            if not in_hole:
                return True
    if tolerance_m > 0 and distance_to_boundary_m(polygons, x, y) <= tolerance_m:
        return True
    return False


def feature_point(feature):
    """Representative point for a feature: Point as-is, otherwise ring centroid.

    Places are seeded as points. Anything else gets a centroid so a hand-drawn
    polygon still validates rather than crashing.
    """
    g = feature.get("geometry")
    if not g:
        return None
    t = g["type"]
    if t == "Point":
        return g["coordinates"][0], g["coordinates"][1]
    coords = g["coordinates"]
    while isinstance(coords[0][0], (list, tuple)):
        coords = coords[0]
    xs = [c[0] for c in coords]
    ys = [c[1] for c in coords]
    return sum(xs) / len(xs), sum(ys) / len(ys)
