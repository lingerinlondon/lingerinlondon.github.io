"""Check the survey importer. Run: python -m tests.run_survey

Two things matter: ten hand-written rows round-trip into valid GeoJSON, and
nothing is ever dropped without saying so.
"""

import json
import os
import sys
import tempfile

from scripts import survey_import, validate

HERE = os.path.dirname(os.path.abspath(__file__))
TEN = os.path.join(HERE, "fixtures", "survey_ten_rows.csv")
MESSY = os.path.join(HERE, "fixtures", "survey_messy_rows.csv")

# Each messy row breaks one thing, and the report must name it.
EXPECTED = {
    2: "time_pressure",
    3: "no id",
    4: "no name",
    5: "columns the schema does not define: Mood",
    6: "is not a date this understands",
    7: "not in data/candidates.geojson",
    8: "crowdfunding",
    9: "is not a number",
}


def main():
    failures = []

    rows = survey_import.read_rows(TEN)
    features, problems = survey_import.convert(rows)
    if problems:
        failures.append("the ten-row sample should map cleanly, but %d rows did not" % len(problems))
    elif len(features) != 10:
        failures.append("expected 10 features from 10 rows, got %d" % len(features))
    else:
        print("ok   ten hand-written rows became ten features")

    tmp = tempfile.mkdtemp(prefix="survey-test-")
    out = os.path.join(tmp, "survey.geojson")
    with open(out, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)
    schema_problems, _ = validate.run([(out, "place")])
    if schema_problems:
        failures.append("imported rows do not validate:\n" +
                        "\n".join(p.render() for p in schema_problems))
    else:
        print("ok   the result validates as published places, boundary included")

    shorthand = {f["properties"]["id"]: f["properties"] for f in features}
    checks = [
        ("osm:node/3000005", "payment_to_sit", "optional"),   # "tolerated"
        ("osm:node/3000005", "conversation", "expected"),     # "loud"
        ("osm:node/3000005", "setting", "covered"),           # "arcade"
        ("osm:way/3000003", "seating", "fixed"),              # "pews"
        ("osm:way/3000008", "verified_date", "2026-08-21"),   # "21 August 2026"
        ("osm:node/3000007", "verified_date", "2026-08-22"),  # "22/08/2026"
    ]
    wrong = ["%s.%s = %r, expected %r" % (i, f, shorthand[i].get(f), v)
             for i, f, v in checks if shorthand[i].get(f) != v]
    if wrong:
        failures.append("shorthand was mapped wrongly: " + "; ".join(wrong))
    else:
        print("ok   shorthand and loose dates are understood")

    if not all(p["verified"] for p in shorthand.values()):
        failures.append("a visit came out unverified; a survey row is a visit")
    else:
        print("ok   a survey row counts as a visit")

    rows = survey_import.read_rows(MESSY)
    features, problems = survey_import.convert(rows)
    if features:
        failures.append("%d messy rows were mapped when none should have been" % len(features))
    reported = {number: " ".join(reasons) for number, _, reasons in problems}
    for number, needle in EXPECTED.items():
        if number not in reported:
            failures.append("row %d was dropped without being reported" % number)
        elif needle not in reported[number]:
            failures.append("row %d was reported, but not for %r. Got: %s"
                            % (number, needle, reported[number]))
    if len(reported) == len(EXPECTED) and not failures:
        print("ok   all %d unmappable rows reported, each naming its own problem" % len(reported))

    if failures:
        print("\n%d survey check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nSurvey importer behaves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
