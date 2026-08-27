"""Prove each validation check actually fires. Run: python -m tests.run_fixtures

A check nobody has watched fail is a check you do not have. Each fixture below
breaks exactly one rule, and this asserts that the failure names the right
field and reads plainly.
"""

import os
import sys

from scripts import validate

HERE = os.path.dirname(os.path.abspath(__file__))
FIX = os.path.join(HERE, "fixtures")

# fixture, profile, must-appear-in-output
CASES = [
    ("bad_schema.geojson", "place", ["time_pressure", "not one of", "none, implied, enforced"]),
    ("outside_boundary.geojson", "place", ["outside the project boundary", "not a judgement"]),
    ("duplicate_id.geojson", "place", ["id", "already used by"]),
    ("verified_without_date.geojson", "place", ["verified_date", "missing"]),
    ("why_missing.geojson", "place", ["why", "missing"]),
    ("why_too_long.geojson", "place", ["why", "215 characters", "limit is 200"]),
]


def render(problems):
    return "\n".join(p.render() for p in problems)


def main():
    failures = []

    problems, _ = validate.run([(os.path.join(FIX, "valid.geojson"), "place")])
    if problems:
        failures.append("valid.geojson should pass but reported:\n%s" % render(problems))
    else:
        print("ok   valid.geojson passes")

    for name, profile, expected in CASES:
        problems, _ = validate.run([(os.path.join(FIX, name), profile)])
        text = render(problems)
        if not problems:
            failures.append("%s should fail, but passed" % name)
            continue
        missing = [e for e in expected if e not in text]
        if missing:
            failures.append(
                "%s failed, but the message did not mention %s.\nGot:\n%s"
                % (name, ", ".join(repr(m) for m in missing), text)
            )
        else:
            first = text.splitlines()[1].strip()
            print("ok   %-32s fails with: %s" % (name, first))

    # A candidate with no why is fine; the same feature as a published place is not.
    problems, _ = validate.run([(os.path.join(FIX, "why_missing.geojson"), "candidate")])
    if problems:
        failures.append(
            "why_missing.geojson should pass under the candidate profile, but reported:\n%s"
            % render(problems)
        )
    else:
        print("ok   why_missing.geojson passes as a candidate, as intended")

    if failures:
        print("\n%d fixture check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nAll validation checks fire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
