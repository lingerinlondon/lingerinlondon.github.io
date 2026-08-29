"""Validate the corpus. Run as: python -m scripts.validate

Five checks, in the order a contributor meets them:

  1. every feature matches schema/place.schema.json
  2. every feature passes the four eligibility gates
  3. every feature sits inside data/boundary.geojson
  4. no id and spot pair appears twice
  5. why is present and stays a sentence, and verified carries a date

Checks 1, 2 and 5 are expressed in the schema, so the schema stays the single
source of truth; this file turns a JSON Schema error into a sentence someone
can act on. Checks 3 and 4 are here because they are about the corpus as a
whole rather than about one feature.

A gate failure is worded differently from every other error on purpose. It does
not mean someone described a place badly. It means the place belongs somewhere
other than this list, and saying so unkindly would be both rude and wrong.

Exit code is 0 if the corpus is clean and 1 if it is not.
"""

import argparse
import json
import os
import sys

from scripts import geo, schema as schema_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TARGETS = ["data/places.geojson"]

FIELD_HINTS = {
    "id": (
        "Every place is keyed to the OSM element it sits in or on, which is what gives "
        "each entry a link a reader can follow. Expected something like osm:way/123456."
    ),
    "spot": (
        "Which part of the element, when the whole of it is not the point — "
        "'top floor, by the window'. Leave it out for the place as a whole."
    ),
    "verified_date": "Expected a date like 2026-08-27.",
    "why": "One sentence on why this place is here, up to 200 characters.",
    "verified": "true if someone has sat there, false if it has been reviewed but not visited.",
}


class Problem(object):
    def __init__(self, source, feature_label, field, message, hint=None):
        self.source = source
        self.feature_label = feature_label
        self.field = field
        self.message = message
        self.hint = hint

    @property
    def where(self):
        return "%s — %s" % (self.source, self.feature_label)

    def detail(self):
        line = "  %s: %s" % (self.field, self.message) if self.field else "  %s" % self.message
        out = [line]
        if self.hint:
            out.append("    %s" % self.hint)
        return "\n".join(out)

    def render(self):
        return "\n".join([self.where, self.detail()])


def label_for(feature, index):
    props = (feature or {}).get("properties") or {}
    name = props.get("name")
    spot = props.get("spot")
    ident = props.get("id")
    if name and spot:
        name = "%s (%s)" % (name, spot)
    if name and ident:
        return "%s [%s]" % (name, ident)
    if name:
        return str(name)
    if ident:
        return str(ident)
    return "feature %d, which has no name and no id yet" % index


def _field_of(error):
    for part in error.absolute_path:
        if isinstance(part, str) and part != "properties":
            return part
    if error.validator in ("required", "unevaluatedProperties", "additionalProperties"):
        if "'" in error.message:
            return error.message.split("'")[1]
    return None


def _plain(error, field, gates):
    """A JSON Schema error, said plainly. Gate fields get their own wording."""
    v = error.validator

    if v == "enum" and field in gates:
        gate = gates[field]
        return (
            "%s does not pass. %s\n    %s"
            % (json.dumps(error.instance), gate["reason"], "This is one of the four things a "
               "place has to be to belong in this list, not a detail to correct.")
        )

    if v == "required":
        if field == "verified_date":
            return (
                "missing. A place marked verified needs the date it was checked in "
                "person — without one there is no way to tell how old the answer is."
            )
        if field == "why":
            return "missing. Every place needs its one sentence."
        return "missing."
    if v == "enum":
        allowed = ", ".join(str(x) for x in error.validator_value if x is not None)
        return "%s is not one of: %s" % (json.dumps(error.instance), allowed)
    if v == "maxLength":
        return "is %d characters. The limit is %d." % (len(error.instance), error.validator_value)
    if v == "minLength":
        return "is empty."
    if v in ("pattern", "format"):
        if field == "verified_date":
            return "%s is not a date." % json.dumps(error.instance)
        return "%s is not the expected shape." % json.dumps(error.instance)
    if v == "type":
        want = error.validator_value
        want = ", ".join(want) if isinstance(want, list) else want
        return "%s should be %s, not %s." % (
            json.dumps(error.instance), want, type(error.instance).__name__
        )
    if v in ("unevaluatedProperties", "additionalProperties"):
        return (
            "is not a field in the schema. Fields are defined in "
            "schema/place.schema.json, and adding one is a deliberate decision."
        )
    if v == "uniqueItems":
        return "lists the same value twice."
    return error.message


def schema_problems(source, features):
    validator = schema_mod.validator()
    gates = {g["field"]: g for g in schema_mod.gates()}
    problems = []
    for i, feature in enumerate(features):
        props = (feature or {}).get("properties") or {}
        label = label_for(feature, i)
        errors = sorted(validator.iter_errors(props), key=lambda e: list(e.absolute_path))
        seen = set()
        for error in errors:
            if error.context:
                continue
            field = _field_of(error)
            message = _plain(error, field, gates)
            if (field, message) in seen:
                continue
            seen.add((field, message))
            problems.append(Problem(source, label, field, message, FIELD_HINTS.get(field)))
    return problems


def boundary_problems(source, features, polygons):
    problems = []
    for i, feature in enumerate(features):
        label = label_for(feature, i)
        point = geo.feature_point(feature)
        if point is None:
            problems.append(
                Problem(source, label, None, "has no geometry, so we cannot tell where it is.")
            )
            continue
        lon, lat = point
        if not geo.contains(polygons, lon, lat):
            away = geo.distance_to_boundary_m(polygons, lon, lat)
            problems.append(
                Problem(
                    source, label, None,
                    "sits about %s outside the project boundary." % _distance(away),
                    "This project covers central London only, and that scope is in its "
                    "name on purpose. It is not a judgement on the place. "
                    "data/boundary.geojson is the authoritative outline.",
                )
            )
    return problems


def _distance(metres):
    if metres < 1000:
        return "%d m" % int(round(metres / 10.0) * 10)
    return "%.1f km" % (metres / 1000.0)


def duplicate_problems(by_source):
    """One id and spot pair, one entry.

    The key is the pair, not the id, because one library can hold two genuinely
    different places to sit — the top floor by the window is not the ground floor.
    """
    seen = {}
    problems = []
    for source, features in by_source:
        for i, feature in enumerate(features):
            props = (feature or {}).get("properties") or {}
            ident = props.get("id")
            if not isinstance(ident, str) or not ident:
                continue
            key = (ident, props.get("spot") or None)
            label = label_for(feature, i)
            if key in seen:
                problems.append(
                    Problem(
                        source, label, "id",
                        "already used by %s." % seen[key],
                        "Two entries can share an OSM id as long as they name different "
                        "spots within it. These two name the same spot, or neither names one.",
                    )
                )
            else:
                seen[key] = label
    return problems


def read_features(path):
    if not os.path.exists(path):
        return [], None
    try:
        with open(path) as fh:
            doc = json.load(fh)
    except ValueError as exc:
        return None, Problem(path, "the file itself", None, "is not valid JSON: %s" % exc)
    if not isinstance(doc, dict) or doc.get("type") != "FeatureCollection":
        return None, Problem(path, "the file itself", None, "should be a GeoJSON FeatureCollection.")
    features = doc.get("features")
    if not isinstance(features, list):
        return None, Problem(path, "the file itself", None, "has no features list.")
    return features, None


def run(targets=None, boundary_path=geo.BOUNDARY_PATH):
    targets = targets or TARGETS
    polygons = geo.load_boundary(boundary_path)

    problems = []
    by_source = []
    counts = {}

    for rel in targets:
        path = rel if os.path.isabs(rel) else os.path.join(ROOT, rel)
        features, problem = read_features(path)
        if problem:
            problems.append(problem)
            continue
        counts[rel] = len(features)
        by_source.append((rel, features))
        problems.extend(schema_problems(rel, features))
        problems.extend(boundary_problems(rel, features, polygons))

    problems.extend(duplicate_problems(by_source))
    return problems, counts


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Check the corpus against the schema, the gates, the boundary, and itself."
    )
    parser.add_argument("--file", action="append", metavar="PATH",
                        help="Validate this file instead of the corpus. Repeatable.")
    parser.add_argument("--boundary", default=geo.BOUNDARY_PATH)
    parser.add_argument("--quiet", action="store_true",
                        help="Say nothing unless something is wrong.")
    args = parser.parse_args(argv)

    problems, counts = run(args.file or None, args.boundary)

    if problems:
        print("The corpus needs a few things fixed before it can be published.\n")
        current = None
        for problem in problems:
            if problem.where != current:
                if current is not None:
                    print("")
                print(problem.where)
                current = problem.where
            print(problem.detail())
        print("")
        print("%d thing%s to fix." % (len(problems), "" if len(problems) == 1 else "s"))
        return 1

    if not args.quiet:
        total = sum(counts.values())
        print("Corpus is valid. %d place%s." % (total, "" if total == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
