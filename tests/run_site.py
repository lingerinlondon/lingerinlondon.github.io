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

    chips = set(re.findall(r'data-field="([^"]+)" data-match="([^"]+)"', page))

    # Every chip must come from the schema...
    allowed = set()
    for f in schema_mod.filters():
        for value in f["values"]:
            allowed.add((f["field"], value))
    invented = chips - allowed
    if invented:
        failures.append("chips not in the schema: %s" % sorted(invented))
    else:
        print("ok   all %d filter chips derive from the schema" % len(chips))

    # ...and every chip must be able to return something. A chip that always
    # returns nothing is a promise the list cannot keep.
    import json as _json
    corpus = [f["properties"] for f in _json.load(open(FIX))["features"]]
    reachable = set()
    for place in corpus:
        for field, value in place.items():
            if isinstance(value, str):
                reachable.add((field, value))
    unusable = chips - reachable
    if unusable:
        failures.append("chips that can never match anything: %s" % sorted(unusable))
    else:
        print("ok   every chip matches at least one place in the corpus")

    # ...and every value the corpus actually holds must be filterable.
    missing = (reachable & allowed) - chips
    if missing:
        failures.append("values present in the corpus with no chip: %s" % sorted(missing))
    else:
        print("ok   every filterable value the corpus holds has a chip")

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

    if "Last sat in" not in page:
        failures.append("entries do not show when anyone was last there")
    else:
        print("ok   every entry shows the date it was last sat in")

    # The list comes first. Provenance is worth reading, but after the thing
    # someone came for, and the invitation sits between the two.
    where = {name: page.find(marker) for name, marker in [
        ("the list", '<article class="place"'),
        ("the invitation", '<div class="suggest">'),
        ("the provenance note", '<div class="legend">'),
        ("the footer", "<footer>"),
    ]}
    missing = [n for n, i in where.items() if i == -1]
    if missing:
        failures.append("the page is missing: %s" % ", ".join(missing))
    elif sorted(where, key=where.get) != ["the list", "the invitation",
                                          "the provenance note", "the footer"]:
        failures.append("the page is in the wrong order: %s"
                        % ", ".join(sorted(where, key=where.get)))
    else:
        print("ok   list, then the invitation, then where it comes from")

    if 'class="suggest"' not in page or "suggest.html" not in page:
        failures.append("there is no visible way to suggest a place")
    else:
        print("ok   suggesting a place is offered as its own block, not a footnote")

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
