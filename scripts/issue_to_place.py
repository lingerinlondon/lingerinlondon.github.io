"""Turn a suggestion issue into a place, ready for review as a pull request.

Run as: python -m scripts.issue_to_place --body issue.md --out data/places.geojson --merge

Reads the body GitHub produces from the issue form, using the same question
definitions the form was generated from, so a reworded label can never silently
stop matching.

What it will not do is guess. If a contributor left the OpenStreetMap id blank —
which is expected, and fine — the entry is written with a placeholder id and the
corpus fails validation until a human fills it in during review. A visibly
incomplete pull request is much better than a plausible wrong one: nobody ever
goes back to check an entry that looked finished.

Nothing here merges anything. It prepares a change for a person to read.
"""

import argparse
import datetime
import json
import os
import re
import sys

from scripts import form_spec, schema as schema_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# What an id looks like when nobody supplied one. Deliberately fails the
# schema's pattern, so the pull request cannot be merged until it is replaced.
UNKNOWN_ID = "osm:UNKNOWN"

NO_RESPONSE = ("_no response_", "none", "n/a", "")


class Rejected(Exception):
    """The suggestion cannot become an entry, and the contributor should be told why."""


class NotASuggestion(Exception):
    """This issue is not a suggestion at all. Nothing to say, nothing to do."""


def looks_like_a_suggestion(sections):
    """Is this issue the suggestion form, or somebody reporting a bug?

    Decided here rather than by a label on the issue, because GitHub only
    applies a template's labels if the label already exists, and a missing
    label made the whole workflow skip in silence.
    """
    labels = {q["label"] for q in form_spec.questions()}
    return len(labels & set(sections)) >= 3


def parse_body(body):
    """Split a GitHub issue-form body into {question label: answer}."""
    sections = {}
    current = None
    buffer = []
    for line in body.splitlines():
        heading = re.match(r"^###\s+(.*?)\s*$", line)
        if heading:
            if current is not None:
                sections[current] = "\n".join(buffer).strip()
            current = heading.group(1)
            buffer = []
        elif current is not None:
            buffer.append(line)
    if current is not None:
        sections[current] = "\n".join(buffer).strip()
    return sections


def answered(text):
    return text is not None and text.strip().lower() not in NO_RESPONSE


def parse_osm_id(text):
    """Accept a bare id, an osm: id, or a whole openstreetmap.org link."""
    if not answered(text):
        return None
    match = re.search(r"(node|way|relation)[/ ]+(\d+)", text.strip(), re.I)
    if not match:
        return None
    return "osm:%s/%s" % (match.group(1).lower(), match.group(2))


def parse_coordinates(text):
    if not answered(text):
        return None
    numbers = re.findall(r"-?\d+\.\d+", text)
    if len(numbers) < 2:
        return None
    lat, lon = float(numbers[0]), float(numbers[1])
    if not (-90 <= lat <= 90 and -180 <= lon <= 180):
        return None
    return [round(lon, 6), round(lat, 6)]


def parse_date(text, today=None):
    if not answered(text):
        raise Rejected("No date. Every suggestion needs the date you were last there.")
    cleaned = text.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d/%m/%y", "%d %b %Y", "%d %B %Y"):
        try:
            when = datetime.datetime.strptime(cleaned, fmt).date()
            break
        except ValueError:
            continue
    else:
        raise Rejected("%r is not a date this understands. Try 2026-08-27 or 27/08/2026."
                       % cleaned)

    today = today or datetime.date.today()
    if when > today:
        raise Rejected("That date is in the future.")
    if when < form_spec.oldest_acceptable(today):
        raise Rejected(
            "That visit was on %s, which is more than a year ago. Places change, so this "
            "list only takes recent visits — it is not a judgement on the place, and a "
            "suggestion is welcome again after you have been back." % when.isoformat()
        )
    return when.isoformat()


def convert(body, today=None):
    """Issue body -> (feature, notes). Raises Rejected if it cannot be one."""
    sections = parse_body(body)
    if not looks_like_a_suggestion(sections):
        raise NotASuggestion()
    questions = {q["label"]: q for q in form_spec.questions()}

    missing_labels = [label for label in questions if label not in sections]
    props = {}
    notes = []

    def answer(key):
        for label, q in questions.items():
            if q["key"] == key:
                return sections.get(label)
        return None

    for q in form_spec.questions():
        if q["kind"] in ("gates", "checkboxes") or not q.get("field"):
            continue
        raw = answer(q["key"])
        if q["key"] == "osm_id" or q["key"] == "last_checked":
            continue
        if not answered(raw):
            continue
        if q["kind"] == "dropdown":
            value = form_spec.value_from_option(raw, q["options"])
            if value:
                props[q["field"]] = value
            continue
        props[q["field"]] = raw.strip()

    name = props.get("name")
    if not name:
        raise Rejected("No name. Without one there is nothing to look up.")

    props["last_checked"] = parse_date(answer("last_checked"), today)

    ident = parse_osm_id(answer("osm_id"))
    if ident:
        props["id"] = ident
    else:
        props["id"] = UNKNOWN_ID
        notes.append(
            "No OpenStreetMap id was given, so this needs one before it can be merged. "
            "The contributor said it is at: %s" % (answer("where") or "(no location given)")
        )

    coordinates = parse_coordinates(answer("coordinates"))
    if coordinates is None:
        notes.append("No coordinates were given, so these need filling in too.")
        coordinates = [0.0, 0.0]

    support = []
    for question in form_spec.questions():
        if question["kind"] != "checkboxes":
            continue
        raw = sections.get(question["label"], "")
        for value in question["options"]:
            if re.search(r"^\s*-\s*\[[xX]\]\s*%s\s*$" % re.escape(value.replace("_", " ")),
                         raw, re.M):
                support.append(value)
    if support:
        props["support_options"] = support

    if not props.get("why"):
        raise Rejected("No sentence saying why this place is here.")

    if missing_labels:
        notes.append("The issue did not contain these questions, so they may have been "
                     "removed or reworded: %s" % ", ".join(sorted(missing_labels)))

    fields = list(schema_mod.fields())
    ordered = dict((k, props[k]) for k in fields if k in props)
    return ({"type": "Feature",
             "geometry": {"type": "Point", "coordinates": coordinates},
             "properties": ordered}, notes)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--body", required=True, help="File holding the issue body.")
    parser.add_argument("--out", default=os.path.join(ROOT, "data", "places.geojson"))
    parser.add_argument("--notes", help="Write reviewer notes here, for the pull request body.")
    args = parser.parse_args(argv)

    body = open(args.body).read()
    try:
        feature, notes = convert(body)
    except NotASuggestion:
        sys.stderr.write("Not a suggestion issue. Nothing to do.\n")
        return 3
    except Rejected as exc:
        sys.stderr.write("REJECTED: %s\n" % exc)
        if args.notes:
            open(args.notes, "w").write(str(exc))
        return 2

    with open(args.out) as fh:
        doc = json.load(fh)
    features = doc.get("features", [])
    key = (feature["properties"]["id"], feature["properties"].get("spot") or None)
    features = [f for f in features
                if ((f["properties"].get("id"), f["properties"].get("spot") or None) != key
                    or key[0] == UNKNOWN_ID)]
    features.append(feature)
    features.sort(key=lambda f: ((f["properties"].get("name") or "").lower(),
                                 f["properties"].get("spot") or ""))
    with open(args.out, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh,
                  indent=2, ensure_ascii=False)
        fh.write("\n")

    print("Added %s" % feature["properties"].get("name"))
    if args.notes:
        open(args.notes, "w").write("\n".join("- %s" % n for n in notes) if notes else "")
    for note in notes:
        print("  note: %s" % note)
    return 0


if __name__ == "__main__":
    sys.exit(main())
