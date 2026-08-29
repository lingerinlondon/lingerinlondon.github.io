"""Check the survey importer. Run: python -m tests.run_survey

Three things matter: ten hand-written rows round-trip into valid GeoJSON,
nothing is ever dropped without saying so, and a row that fails a gate is told
its place does not qualify rather than that its spelling is wrong.
"""

import json
import os
import sys
import tempfile

from scripts import survey_import, validate

HERE = os.path.dirname(os.path.abspath(__file__))
TEN = os.path.join(HERE, "fixtures", "survey_ten_rows.csv")
MESSY = os.path.join(HERE, "fixtures", "survey_messy_rows.csv")

EXPECTED = {
    2: "is not shorthand this recognises",
    3: "no id",
    4: "no name",
    5: "columns the schema does not define: Mood",
    6: "is not a date this understands",
    7: "no location",
    8: "crowdfunding",
    9: "does not qualify",
    10: "does not qualify",
    11: "does not qualify",
}

# shorthand in, canonical value out
SHORTHAND = [
    (("osm:node/3000009", "the far end away from the stalls"), "payment_to_sit", "optional"),
    (("osm:node/3000009", "the far end away from the stalls"), "conversation", "expected"),
    (("osm:node/3000009", "the far end away from the stalls"), "setting", "covered"),
    (("osm:way/3000003", None), "seating", "fixed"),
    (("osm:way/3000003", None), "payment_to_enter", "optional"),
    (("osm:way/3000008", None), "verified_date", "2026-08-21"),
    (("osm:node/3000007", None), "verified_date", "2026-08-22"),
]


def main():
    failures = []

    rows = survey_import.read_rows(TEN)
    features, problems = survey_import.convert(rows)
    if problems:
        failures.append("the ten-row sample should map cleanly, but %d rows did not:\n%s"
                        % (len(problems), problems))
    elif len(features) != 10:
        failures.append("expected 10 features from 10 rows, got %d" % len(features))
    else:
        print("ok   ten hand-written rows became ten features")

    tmp = tempfile.mkdtemp(prefix="survey-test-")
    out = os.path.join(tmp, "survey.geojson")
    with open(out, "w") as fh:
        json.dump({"type": "FeatureCollection", "features": features}, fh)
    schema_problems, _ = validate.run([out])
    if schema_problems:
        failures.append("imported rows do not validate:\n" +
                        "\n".join(p.render() for p in schema_problems))
    else:
        print("ok   the result validates: schema, gates, boundary and uniqueness")

    index = {(f["properties"]["id"], f["properties"].get("spot")): f["properties"]
             for f in features}
    if len(index) != len(features):
        failures.append("two rows collapsed onto one id and spot pair")

    shared = [k for k in index if k[0] == "osm:way/3000004"]
    if len(shared) != 2:
        failures.append("the two entries sharing osm:way/3000004 did not both survive")
    else:
        print("ok   one OSM element carries two entries, told apart by their spot")

    wrong = ["%s.%s = %r, expected %r" % (k[0], f, index[k].get(f), v)
             for k, f, v in SHORTHAND if index.get(k, {}).get(f) != v]
    if wrong:
        failures.append("shorthand was mapped wrongly: " + "; ".join(wrong))
    else:
        print("ok   shorthand and loose dates are understood")

    if not all(p["verified"] for p in index.values()):
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
        print("ok   the three gate failures say the place does not qualify, not that the sheet is wrong")

    # Adding places one trip at a time must never lose the previous trips.
    corpus = os.path.join(tmp, "corpus.geojson")
    trip_one = os.path.join(tmp, "one.csv")
    trip_two = os.path.join(tmp, "two.csv")
    header = ("id,name,spot,lat,lon,date,payment_to_enter,payment_to_sit,time_pressure,"
              "conversation,activity,seating,setting,support_options,why\n")
    open(trip_one, "w").write(header + "osm:way/9000001,A library,,51.5194,-0.1270,"
                              "2026-08-28,free,free,no,quiet,study,chairs,in,,First one.\n")
    open(trip_two, "w").write(header + "osm:node/9000002,A garden,,51.5163,-0.1220,"
                              "2026-08-29,free,free,no,ok,yes,bench,out,,Second one.\n")

    quietly = {"stdout": sys.stdout, "stderr": sys.stderr}
    sys.stdout = open(os.devnull, "w")
    sys.stderr = open(os.devnull, "w")
    try:
        survey_import.main([trip_one, "--out", corpus])
        refused = False
        try:
            survey_import.main([trip_two, "--out", corpus])
        except SystemExit:
            refused = True
        survey_import.main([trip_two, "--out", corpus, "--merge"])
    finally:
        sys.stdout.close(); sys.stderr.close()
        sys.stdout = quietly["stdout"]; sys.stderr = quietly["stderr"]

    if not refused:
        failures.append("importing over a non-empty corpus did not refuse; fieldwork could be lost")
    else:
        print("ok   importing over an existing corpus refuses rather than guessing")

    names = [f["properties"]["name"] for f in json.load(open(corpus))["features"]]
    if sorted(names) != ["A garden", "A library"]:
        failures.append("merging lost or duplicated places: %s" % names)
    else:
        print("ok   --merge adds a trip without losing the trips before it")

    if failures:
        print("\n%d survey check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nSurvey importer behaves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
