"""Check suggestions become places correctly. Run: python -m tests.run_issue

The risk this guards is silent loss. A relabelled question, a reworded option,
a date format nobody thought of — each one quietly drops an answer somebody
took the trouble to give, and nothing anywhere reports it.

So the fixture issue body is built from the same question definitions the form
is generated from. If a question is renamed and this is not updated, the test
notices rather than the contributor.
"""

import datetime
import sys

from scripts import form_spec, issue_to_place, schema as schema_mod

ANSWERS = {
    "name": "The Barbican Conservatory",
    "spot": "the upper walkway",
    "where": "Silk Street, Barbican",
    "osm_id": "https://www.openstreetmap.org/way/26382524",
    "coordinates": "51.5200, -0.0937",
    "last_checked": "12/08/2026",
    "why": "Warm, humid and almost empty on a weekday, with benches nobody asks you to leave.",
    "conversation": None,   # filled from the schema below, so wording cannot drift
    "activity": None,
    "seating": None,
    "setting": None,
    "table": None,
    "suggested_by": "A. Contributor",
}
TICKED_SUPPORT = ("donation", "shop")
TODAY = datetime.date(2026, 8, 29)

# Which value each dropdown is answered with, written exactly as the form
# renders it. Taken from the schema so a reworded option cannot silently pass.
CHOSEN = {"conversation": "possible", "activity": "possible",
          "seating": "fixed", "setting": "indoor", "table": "some"}
for _field, _value in CHOSEN.items():
    ANSWERS[_field] = form_spec.option_label(
        _value, (schema_mod.fields()[_field].get("x-filter") or {}).get("values", {}).get(_value))


def build_body(overrides=None):
    """An issue body exactly as GitHub renders one, from the real questions."""
    overrides = overrides or {}
    out = []
    for q in form_spec.questions():
        out.append("### %s" % q["label"])
        out.append("")
        if q["kind"] == "gates":
            for gate in schema_mod.gates():
                out.append("- [X] %s" % gate["confirm"])
        elif q["kind"] == "checkboxes":
            for value in q["options"]:
                mark = "X" if value in TICKED_SUPPORT else " "
                out.append("- [%s] %s" % (mark, value.replace("_", " ")))
        else:
            value = overrides.get(q["key"], ANSWERS.get(q["key"], "_No response_"))
            out.append(value)
        out.append("")
    return "\n".join(out)


def main():
    failures = []

    feature, notes = issue_to_place.convert(build_body(), TODAY)
    props = feature["properties"]

    expected = {
        "id": "osm:way/26382524",
        "spot": "the upper walkway",
        "name": "The Barbican Conservatory",
        "conversation": "possible",
        "activity": "possible",
        "seating": "fixed",
        "setting": "indoor",
        "table": "some",
        "last_checked": "2026-08-12",
        "suggested_by": "A. Contributor",
    }
    wrong = ["%s = %r, expected %r" % (k, props.get(k), v)
             for k, v in expected.items() if props.get(k) != v]
    if wrong:
        failures.append("answers were read wrongly: " + "; ".join(wrong))
    else:
        print("ok   a complete suggestion becomes a place, every answer carried across")

    if sorted(props.get("support_options") or []) != sorted(TICKED_SUPPORT):
        failures.append("ticked support options came out as %r" % props.get("support_options"))
    else:
        print("ok   ticked boxes are read, unticked ones are not")

    if notes:
        failures.append("a complete suggestion produced reviewer notes: %s" % notes)
    else:
        print("ok   a complete suggestion needs nothing from the reviewer")

    if feature["geometry"]["coordinates"] != [-0.0937, 51.52]:
        failures.append("coordinates came out as %r" % feature["geometry"]["coordinates"])

    # The expected case: no id, no coordinates.
    feature, notes = issue_to_place.convert(
        build_body({"osm_id": "_No response_", "coordinates": "_No response_"}), TODAY)
    if feature["properties"]["id"] != issue_to_place.UNKNOWN_ID:
        failures.append("a missing id did not become the placeholder")
    elif len(notes) < 2:
        failures.append("a missing id and coordinates did not both produce reviewer notes")
    else:
        print("ok   a suggestion without an OSM id still opens, flagged for the reviewer")

    # ...and that placeholder must not be mergeable.
    validator = schema_mod.validator()
    if not list(validator.iter_errors(feature["properties"])):
        failures.append("the placeholder id passes validation; an incomplete entry could merge")
    else:
        print("ok   the placeholder fails validation, so it cannot merge unnoticed")

    for label, override, needle in [
        ("a visit over a year old", {"last_checked": "12/08/2024"}, "more than a year ago"),
        ("a date in the future", {"last_checked": "12/08/2027"}, "in the future"),
        ("a date that is not a date", {"last_checked": "last summer"}, "not a date"),
        ("no date at all", {"last_checked": "_No response_"}, "needs the date"),
        ("no sentence", {"why": "_No response_"}, "sentence"),
        ("no name", {"name": "_No response_"}, "name"),
    ]:
        try:
            issue_to_place.convert(build_body(override), TODAY)
        except issue_to_place.Rejected as exc:
            if needle not in str(exc):
                failures.append("%s was rejected, but not for %r: %s" % (label, needle, exc))
        else:
            failures.append("%s was accepted when it should not have been" % label)
    if not failures:
        print("ok   old, future, missing and malformed answers are each turned away with a reason")

    # A reworded question must be noticed, not silently dropped.
    body = build_body().replace("### When were you last there?", "### When did you go?")
    try:
        issue_to_place.convert(body, TODAY)
    except issue_to_place.Rejected as exc:
        if "date" not in str(exc).lower():
            failures.append("a renamed question failed for the wrong reason: %s" % exc)
        else:
            print("ok   a question renamed out from under the parser fails loudly")

    # An ordinary issue must be ignored, not misread as a place.
    for label, body in [
        ("an empty issue", ""),
        ("a bug report", "The site looks wrong on my phone.\n\n### Steps\n\n1. Open it"),
    ]:
        try:
            issue_to_place.convert(body, TODAY)
        except issue_to_place.NotASuggestion:
            pass
        except issue_to_place.Rejected as exc:
            failures.append("%s was answered as a rejected suggestion: %s" % (label, exc))
        else:
            failures.append("%s was turned into a place" % label)
    if not failures:
        print("ok   issues that are not suggestions are left alone entirely")

    if failures:
        print("\n%d suggestion check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nSuggestions become places correctly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
