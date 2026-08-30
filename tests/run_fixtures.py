"""Prove each validation check actually fires. Run: python -m tests.run_fixtures

A check nobody has watched fail is a check you do not have. Each fixture breaks
exactly one rule, and this asserts the failure names the right field and reads
plainly — gate failures especially, since those are read by someone who has
just been told their suggestion does not fit.
"""

import os
import sys

from scripts import validate

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")

CASES = [
    ("bad_schema.geojson",
     ["conversation", "not one of", "discouraged, possible"]),
    ("gate_payment_to_enter.geojson",
     ["payment_to_enter", "does not pass", "without paying", "not a mark against"]),
    ("gate_time_pressure.geojson",
     ["time_pressure", "does not pass", "not a place you can stay in"]),
    ("gate_no_seating.geojson",
     ["seating", "does not pass", "only stand"]),
    ("outside_boundary.geojson",
     ["outside the project boundary", "not a judgement"]),
    ("duplicate_id.geojson",
     ["id", "already used by", "different spots"]),
    ("missing_date.geojson",
     ["last_checked", "missing"]),
    ("future_date.geojson",
     ["last_checked", "in the future"]),
    ("why_missing.geojson",
     ["why", "missing"]),
    ("why_too_long.geojson",
     ["why", "215 characters", "limit is 200"]),
]


def render(problems):
    return "\n".join(p.render() for p in problems)


def main():
    failures = []

    problems, _ = validate.run([os.path.join(FIX, "valid.geojson")])
    if problems:
        failures.append("valid.geojson should pass but reported:\n%s" % render(problems))
    else:
        print("ok   valid.geojson passes, including two entries sharing one OSM id")

    for name, expected in CASES:
        problems, _ = validate.run([os.path.join(FIX, name)])
        text = render(problems)
        if not problems:
            failures.append("%s should fail, but passed" % name)
            continue
        missing = [e for e in expected if e not in text]
        if missing:
            failures.append("%s failed, but the message did not mention %s.\nGot:\n%s"
                            % (name, ", ".join(repr(m) for m in missing), text))
        else:
            print("ok   %-34s fails on %s" % (name, text.splitlines()[1].strip().split(":")[0]))

    if failures:
        print("\n%d fixture check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nAll validation checks fire.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
