"""Check the seeder's three promises. Run: python -m tests.run_seed

Never touches the network — it reads a saved Overpass response from fixtures.

  1. it produces a candidates file that validates, with everything unverified
  2. every feature is inside the boundary, and unnamed elements are dropped
  3. rerunning is idempotent, and never overwrites fieldwork
"""

import json
import os
import shutil
import sys
import tempfile

from scripts import geo, seed_overpass, validate

HERE = os.path.dirname(os.path.abspath(__file__))
RESPONSE = os.path.join(HERE, "fixtures", "overpass_response.json")


def seed(out, places=None):
    argv = ["--response", RESPONSE, "--out", out]
    stdout = sys.stdout
    sys.stdout = open(os.devnull, "w")
    try:
        if places is not None:
            original = seed_overpass.PLACES_PATH
            seed_overpass.PLACES_PATH = places
            try:
                seed_overpass.main(argv)
            finally:
                seed_overpass.PLACES_PATH = original
        else:
            seed_overpass.main(argv)
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    with open(out) as fh:
        return json.load(fh)


def main():
    failures = []
    tmp = tempfile.mkdtemp(prefix="seed-test-")
    out = os.path.join(tmp, "candidates.geojson")
    empty_places = os.path.join(tmp, "places.geojson")
    with open(empty_places, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": []}, fh)

    try:
        doc = seed(out, empty_places)
        features = doc["features"]

        problems, _ = validate.run([(out, "candidate")])
        if problems:
            failures.append("seeded output does not validate:\n" + "\n".join(p.render() for p in problems))
        else:
            print("ok   seeded %d candidates, all schema-valid" % len(features))

        if any(f["properties"]["verified"] for f in features):
            failures.append("seeding produced a feature marked verified")
        else:
            print("ok   everything seeded is unverified")

        polygons = geo.load_boundary()
        outside = [f["properties"]["id"] for f in features
                   if not geo.contains(polygons, *f["geometry"]["coordinates"])]
        if outside:
            failures.append("outside the boundary: %s" % ", ".join(outside))
        else:
            print("ok   every candidate is inside the boundary")

        if any(not (f["properties"].get("name") or "").strip() for f in features):
            failures.append("an unnamed element was kept")
        else:
            print("ok   unnamed elements are dropped rather than given a placeholder")

        first = open(out).read()
        seed(out, empty_places)
        if open(out).read() != first:
            failures.append("rerunning the seeder changed the file")
        else:
            print("ok   rerunning is byte-identical")

        # Fieldwork must survive a reseed.
        doc = json.load(open(out))
        target = doc["features"][0]["properties"]
        ident = target["id"]
        target.update({"time_pressure": "none", "seating": "soft", "verified": True,
                       "verified_date": "2026-08-26", "why": "A sentence written on a bench."})
        json.dump(doc, open(out, "w"), indent=2)

        after = seed(out, empty_places)
        kept = [f for f in after["features"] if f["properties"]["id"] == ident][0]["properties"]
        lost = [k for k, v in [("time_pressure", "none"), ("seating", "soft"),
                               ("verified", True), ("verified_date", "2026-08-26"),
                               ("why", "A sentence written on a bench.")] if kept.get(k) != v]
        if lost:
            failures.append("reseeding overwrote fieldwork: %s" % ", ".join(lost))
        else:
            print("ok   reseeding preserves fields a human filled in")

        # A candidate that has been promoted must not be seeded back.
        json.dump({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": {"type": "Point", "coordinates": [-0.127, 51.5194]},
             "properties": {"id": ident, "name": "Promoted", "verified": True,
                            "verified_date": "2026-08-26", "why": "Promoted into the corpus."}}]},
            open(empty_places, "w"))
        after = seed(out, empty_places)
        if any(f["properties"]["id"] == ident for f in after["features"]):
            failures.append("a place already in places.geojson was seeded again as a candidate")
        else:
            print("ok   places already in the corpus are not re-seeded as candidates")

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    if failures:
        print("\n%d seeder check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nSeeder behaves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
