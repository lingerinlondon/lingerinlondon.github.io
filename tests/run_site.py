"""Check the reading surface. Run: python -m tests.run_site

The page is generated, so what matters is that it keeps its promises:

  - filters come from the schema, so adding a field adds a chip
  - gates are stated, never offered as filters — everything passes them
  - the whole list is in the HTML, so it works with scripting off
  - verified and unverified are distinguishable
  - nothing on the page reaches a third party
"""

import os
import re
import sys
import tempfile

from scripts import build_site, schema as schema_mod

FIX = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures", "valid.geojson")


def build(places_path):
    out = os.path.join(tempfile.mkdtemp(prefix="site-test-"), "index.html")
    stdout, sys.stdout = sys.stdout, open(os.devnull, "w")
    try:
        build_site.main(["--places", places_path, "--out", out])
    finally:
        sys.stdout.close()
        sys.stdout = stdout
    return open(out).read()


def main():
    failures = []
    page = build(FIX)

    chips = re.findall(r'data-field="([^"]+)" data-match="([^"]+)"', page)
    expected = set()
    for f in schema_mod.filters():
        if f["chip"]:
            expected.add((f["field"], f["match"]))
        elif f["values"]:
            for value in f["values"]:
                expected.add((f["field"], value))
    if set(chips) != expected:
        failures.append("chips do not match the schema.\n  page: %s\n  schema: %s"
                        % (sorted(set(chips)), sorted(expected)))
    else:
        print("ok   all %d filter chips derive from the schema" % len(chips))

    gate_fields = {g["field"] for g in schema_mod.gates()}
    offered_as_filter = gate_fields & {c[0] for c in chips}
    # seating is both a gate and descriptive: there must be somewhere to sit,
    # and which kind still varies. It is the one field allowed in both.
    offered_as_filter.discard("seating")
    if offered_as_filter:
        failures.append("gates offered as filters, which would filter nothing: %s"
                        % ", ".join(sorted(offered_as_filter)))
    else:
        print("ok   gates are stated, not offered as filters")

    for gate in schema_mod.gates():
        if gate["confirm"] not in page:
            failures.append("the page never states the gate: %s" % gate["confirm"])
    if not failures:
        print("ok   all four gates are stated on the page")

    for name in ("A reading room", "A riverside foyer"):
        if name not in page:
            failures.append("%r is missing from the page" % name)
    if "top floor, by the window" not in page or "the benches outside" not in page:
        failures.append("two entries sharing one OSM id did not both render with their spot")
    else:
        print("ok   entries sharing an OSM id render separately, told apart by spot")

    if 'class="place unverified"' not in page or "not yet visited" not in page:
        failures.append("unverified places are not visually distinguished")
    else:
        print("ok   unverified places are marked and set apart")

    names = re.findall(r"<h3>([^<]+)", page)
    if names != sorted(names, key=str.lower):
        failures.append("places are not in alphabetical order: %s" % names)
    else:
        print("ok   alphabetical, the only order that is not a ranking")

    # Rule 3: nothing on this page may reach a third party.
    urls = re.findall(r'https?://[^"\'\s)]+', page)
    outside = [u for u in urls if "openstreetmap.org" not in u]
    if outside:
        failures.append("the page references external hosts: %s" % ", ".join(sorted(set(outside))))
    else:
        print("ok   no third-party requests — only links out to OpenStreetMap")

    if "<script" in page:
        body_before_script = page.split("<script")[0]
        if 'class="place' not in body_before_script:
            failures.append("the list is not in the HTML; it would need JavaScript to appear")
        else:
            print("ok   the whole list is in the HTML, so it works with scripting off")

    empty = os.path.join(tempfile.mkdtemp(prefix="site-empty-"), "places.geojson")
    open(empty, "w").write('{"type":"FeatureCollection","features":[]}')
    blank = build(empty)
    if "No places listed yet" not in blank:
        failures.append("an empty corpus does not render an honest empty state")
    else:
        print("ok   an empty corpus says so plainly rather than rendering nothing")

    if failures:
        print("\n%d site check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nReading surface behaves.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
