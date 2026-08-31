"""Generate the reading surface from the schema and the corpus.

Run as: python -m scripts.build_site

Writes site/index.html. Not committed — the deploy workflow runs this, so a
contributor changing data/places.geojson never has to regenerate a build
artefact, and their pull request cannot fail on drift they did not cause.

Everything is decided by the schema:

  filters      come from x-filter. A field with a `chip` becomes one toggle; a
               field with `values` and no chip becomes one chip per value.
               Adding a filterable field to the schema adds chips here without
               anyone editing this file.
  gates        come from x-gate, and are NOT filters. Every place passes them,
               so a chip would filter nothing. They are the masthead instead:
               the statement of what the list is.

The whole list renders as plain HTML. JavaScript only hides rows when a chip is
pressed, so with scripting off you get every place and no filtering, which is
the right way round.

No map, no tiles, no fonts to fetch, no third-party anything.
"""

import argparse
import html
import json
import os
import shutil
import sys

from scripts import schema as schema_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACES = os.path.join(ROOT, "data", "places.geojson")
OUT = os.path.join(ROOT, "site", "index.html")

# Published next to the page so anyone can take the data without cloning, and
# so the schema's $id resolves to the schema. Copied here rather than in the
# deploy workflow, so that building locally gives you the same site the deploy
# does, working footer links and all.
ALONGSIDE = [
    (os.path.join(ROOT, "data", "places.geojson"), "data"),
    (os.path.join(ROOT, "data", "boundary.geojson"), "data"),
    (os.path.join(ROOT, "schema", "place.schema.json"), "schema"),
]


def copy_alongside(site_dir):
    copied = 0
    for source, folder in ALONGSIDE:
        if not os.path.exists(source):
            continue
        target_dir = os.path.join(site_dir, folder)
        if not os.path.isdir(target_dir):
            os.makedirs(target_dir)
        shutil.copy(source, target_dir)
        copied += 1
    return copied


TITLE = "Linger in London"
# {scope} is where the superscript citation goes. The prose stays one readable
# string, and the marker is replaced with a link rather than being escaped.
SCOPE_MARKER = "{scope}"
STANDFIRST = (
    "A list of places in 'central'{scope} London you can spend time in, doing what you want, without time or financial pressure. "
    "Use these places to study, read, do laptop work, take a call, listen to music, play chess, chill with friends, etc. "
    "Think of what London's public living rooms would be."
)

SCOPE_NOTE = (
    "Central London is here taken to mean, roughly, Olympia in the west, Spitalfields in "
    "the east, Southwark in the south, and Regent's Park in the north. You can get the "
    '<a href="data/boundary.geojson">boundary file here</a>.'
)


def esc(text):
    return html.escape(str(text), quote=True)


def standfirst_html():
    """The standfirst, with a superscript citation where the marker sits."""
    before, _, after = STANDFIRST.partition(SCOPE_MARKER)
    citation = '<sup><a href="#scope" id="scope-ref" aria-describedby="scope">1</a></sup>'
    return esc(before) + citation + esc(after)


def osm_url(ident):
    if not ident.startswith("osm:"):
        return None
    kind, _, number = ident[4:].partition("/")
    if kind not in ("node", "way", "relation") or not number.isdigit():
        return None
    return "https://www.openstreetmap.org/%s/%s" % (kind, number)


def load_places(path):
    if not os.path.exists(path):
        return []
    with open(path) as fh:
        doc = json.load(fh)
    places = [f.get("properties") or {} for f in doc.get("features", [])]
    # Alphabetical. There is no other defensible order: anything that looked
    # like ranking would be the thing this project exists not to do.
    return sorted(places, key=lambda p: (p.get("name") or "").lower())


def chip_definitions(places=None):
    """Filter chips, derived from the schema, narrowed to what the corpus holds.

    Every value of a filterable field gets a chip — filtering for one value and
    silently excluding a stronger one was a bug, not a simplification.

    A chip is only drawn if some place actually has that value. A chip that can
    only ever return nothing is a promise the list cannot keep, and at forty
    places most values will be unused for a while.
    """
    present = None
    if places is not None:
        present = {}
        for place in places:
            for field, value in place.items():
                if isinstance(value, str):
                    present.setdefault(field, set()).add(value)

    chips = []
    for f in schema_mod.filters():
        if not f["values"]:
            continue
        for value in f["values"]:
            if present is not None and value not in present.get(f["field"], ()):
                continue
            chips.append({
                "field": f["field"],
                "match": value,
                "label": schema_mod.value_label(f["field"], value),
                "title": schema_mod.value_help(f["field"], value),
            })
    return chips


def render(places, gates, chips):
    fields = schema_mod.fields()
    parts = [
        "<!-- Generated by scripts/build_site.py. Do not edit by hand. -->",
        "<!doctype html>",
        '<html lang="en-GB">',
        "<head>",
        '<meta charset="utf-8">',
        '<meta name="viewport" content="width=device-width, initial-scale=1">',
        "<title>%s</title>" % esc(TITLE),
        '<meta name="description" content="%s">' % esc(STANDFIRST),
        "<style>",
        "  :root { color-scheme: light dark; --ink: #1a1a1a; --paper: #fdfdfb; --quiet: #5c5c5c;",
        "          --rule: #d8d8d2; --mark: #7a3b12; }",
        "  @media (prefers-color-scheme: dark) {",
        "    :root { --ink: #e8e6e1; --paper: #161614; --quiet: #a3a099; --rule: #34322e;",
        "            --mark: #d9a273; }",
        "  }",
        "  * { box-sizing: border-box; }",
        "  body { background: var(--paper); color: var(--ink); margin: 0 auto; max-width: 40rem;",
        "         padding: 2.5rem 1.25rem 6rem; line-height: 1.55;",
        "         font-family: Georgia, 'Times New Roman', serif; }",
        "  h1 { font-size: 1.6rem; font-weight: normal; margin: 0 0 0.6rem; }",
        "  h2 { font-size: 1.05rem; font-weight: normal; margin: 2.2rem 0 0.4rem; }",
        "  p { color: var(--quiet); margin: 0.6rem 0; }",
        "  .gates { margin: 2rem 0; padding-left: 1.1rem; }",
        "  .gates li { color: var(--ink); margin: 0.3rem 0; }",
        "  .filters { border-top: 1px solid var(--rule); border-bottom: 1px solid var(--rule);",
        "             padding: 1.1rem 0; margin: 2rem 0; }",
        "  .filters h2, .legend h2 { font-size: 0.95rem; font-weight: normal; margin: 0 0 0.6rem;",
        "                            color: var(--quiet); }",
        "  .chips { display: flex; flex-wrap: wrap; gap: 0.4rem; padding: 0; margin: 0.5rem 0 0;",
        "           list-style: none; }",
        "  .chip { font: inherit; font-size: 0.9rem; padding: 0.3rem 0.7rem; cursor: pointer;",
        "          border: 1px solid var(--rule); border-radius: 1rem; background: transparent;",
        "          color: var(--ink); }",
        "  .chip[aria-pressed=true] { border-color: var(--ink); background: var(--ink);",
        "                             color: var(--paper); }",
        "  .group { margin-top: 0.9rem; }",
        "  .group-label { font-size: 0.85rem; color: var(--quiet); }",
        "  .noscript { font-size: 0.9rem; }",
        "  .legend { margin: 2rem 0; font-size: 0.92rem; }",
        "  .count { color: var(--quiet); font-size: 0.9rem; margin: 1.5rem 0 0.5rem; }",
        "  .place { border-top: 1px solid var(--rule); padding: 1.4rem 0; }",
        "  .place h3 { font-size: 1.1rem; font-weight: normal; margin: 0; }",
        "  .spot { color: var(--quiet); font-style: italic; }",
        "  .why { color: var(--ink); margin: 0.5rem 0 0.8rem; }",
        "  .attrs { display: flex; flex-wrap: wrap; gap: 0.25rem 1rem; padding: 0; margin: 0;",
        "           list-style: none; font-size: 0.88rem; color: var(--quiet); }",
        "  .meta { font-size: 0.85rem; color: var(--quiet); margin-top: 0.8rem; }",
        "  a { color: inherit; }",
        "  .empty { border-top: 1px solid var(--rule); padding-top: 1.5rem; }",
        "  .suggest { border: 1px solid var(--ink); padding: 1.3rem 1.4rem; margin: 3rem 0 2rem; }",
        "  .suggest p { color: var(--ink); margin: 0; }",
        "  .suggest p + p { margin-top: 1rem; }",
        "  .suggest a { display: inline-block; padding: 0.55rem 1.2rem; text-decoration: none;",
        "               border: 1px solid var(--ink); }",
        "  .suggest a:hover, .suggest a:focus { background: var(--ink); color: var(--paper); }",
        "  footer { border-top: 1px solid var(--rule); margin-top: 2.5rem; padding-top: 1.2rem; }",
        "  footer .note { color: var(--quiet); font-size: 0.9rem; }",
        "  sup a { text-decoration: none; padding: 0 0.1em; }",
        "  #scope:target { background: color-mix(in srgb, var(--ink) 8%, transparent); }",
        "</style>",
        "</head>",
        "<body>",
        "<h1>%s</h1>" % esc(TITLE),
        "<p>%s</p>" % standfirst_html(),
        "<p>There are no ratings here, no review counts and no ordering by popularity</p>",
    ]

    parts.append("<h2>What every place on this list has in common</h2>")
    parts.append('<ul class="gates">')
    for gate in gates:
        parts.append("  <li>%s</li>" % esc(gate["confirm"]))
    parts.append("</ul>")
    parts.append(
        "<p>These four are not scores. A place that fails one of them is not a worse place "
        "&mdash; it is a place this particular list is not for. That is why they are stated "
        "once here rather than offered as things to filter by.</p>"
    )

    if chips:
        parts += [
            '<div class="filters">',
            "<h2>Narrow it down</h2>",
            '<noscript><p class="noscript">Filtering needs JavaScript. The whole list is '
            "below regardless.</p></noscript>",
            '<ul class="chips">',
        ]
        grouped = {}
        for chip in chips:
            grouped.setdefault(chip["field"], []).append(chip)

        def button(chip):
            title = ' title="%s"' % esc(chip["title"]) if chip.get("title") else ""
            return ('  <li><button type="button" class="chip" aria-pressed="false" '
                    'data-field="%s" data-match="%s"%s>%s</button></li>'
                    % (esc(chip["field"]), esc(chip["match"]), title, esc(chip["label"])))

        # Fields offering one chip share a row; fields offering a set of values
        # get their own labelled group, so "indoor / outdoor / covered" reads as
        # a choice rather than three unrelated toggles.
        parts.append("</ul>")

        for field, group in grouped.items():
            label = (fields[field].get("x-filter") or {}).get("label", field)
            parts.append('<div class="group"><span class="group-label">%s</span>' % esc(label))
            parts.append('<ul class="chips">')
            for chip in group:
                parts.append(button(chip))
            parts.append("</ul></div>")
        parts.append("</div>")


    if not places:
        parts += [
            '<div class="empty">',
            "<p>No places listed yet. The corpus fills up on foot, one visit at a time, "
            "and nothing goes in that nobody has sat in.</p>",
            "</div>",
        ]
    else:
        parts.append('<p class="count" id="count">%d place%s.</p>'
                     % (len(places), "" if len(places) == 1 else "s"))
        for place in places:
            parts.append(render_place(place, fields))

    parts += [
        '<div class="suggest">',
        "<p>Know somewhere in central London that clears all four? The list only grows by "
        "people adding places they have sat in themselves.</p>",
        '<p><a href="suggest.html">Suggest a place</a></p>',
        "</div>",
        '<div class="legend">',
        "<h2>Where this comes from</h2>",
        "<p>Every place here was suggested by somebody who had been sitting in it, and read "
        "by a person before it was listed. Each entry carries the date it was last sat in, "
        "because places change &mdash; a cafe puts a time limit on the tables, a garden "
        "starts locking its gate. An old date does not mean an entry is wrong. It means "
        "nobody has been recently, and that is worth knowing rather than hiding.</p>",
        "</div>",
        "<footer>",
        '<p class="note" id="scope"><sup>1</sup> %s</p>' % SCOPE_NOTE,
        '<p class="count">The whole list is <a href="data/places.geojson">a GeoJSON file</a> '
        'you can download, fork or load into anything else, described by '
        '<a href="schema/place.schema.json">its schema</a>. The project boundary is '
        '<a href="data/boundary.geojson">here</a>. Everything is CC0 &mdash; no permission '
        "needed.</p>",
        "</footer>",
    ]

    parts += [
        "<script>",
        "  // Chips hide rows; they never reorder them. With scripting off the whole",
        "  // list is already on the page, which is the right way round.",
        "  var chips = document.querySelectorAll('.chip');",
        "  var places = document.querySelectorAll('.place');",
        "  var count = document.getElementById('count');",
        "  function apply() {",
        "    var active = [];",
        "    chips.forEach(function (c) {",
        "      if (c.getAttribute('aria-pressed') === 'true') {",
        "        active.push([c.dataset.field, c.dataset.match]);",
        "      }",
        "    });",
        "    var shown = 0;",
        "    places.forEach(function (p) {",
        "      var ok = active.every(function (pair) {",
        "        var value = p.dataset[pair[0]] || '';",
        "        return value.split('|').indexOf(pair[1]) !== -1;",
        "      });",
        "      p.hidden = !ok;",
        "      if (ok) { shown += 1; }",
        "    });",
        "    if (count) {",
        "      count.textContent = shown === places.length",
        "        ? count.dataset.all",
        "        : shown + ' of ' + places.length + ' places match.';",
        "    }",
        "  }",
        "  chips.forEach(function (c) {",
        "    c.addEventListener('click', function () {",
        "      c.setAttribute('aria-pressed',",
        "        c.getAttribute('aria-pressed') === 'true' ? 'false' : 'true');",
        "      apply();",
        "    });",
        "  });",
        "  if (count) { count.dataset.all = count.textContent; }",
        "</script>",
        "</body>",
        "</html>",
        "",
    ]
    return "\n".join(parts)


DESCRIPTIVE_ORDER = ("conversation", "seating", "table", "setting")


def render_place(place, fields):
    data = []
    for name in DESCRIPTIVE_ORDER:
        value = place.get(name)
        if value:
            data.append('data-%s="%s"' % (name, esc(value)))
    support = place.get("support_options") or []
    if support:
        data.append('data-support_options="%s"' % esc("|".join(support)))

    out = ['<article class="place" %s>' % " ".join(data)]
    name = esc(place.get("name", "Unnamed"))
    spot = place.get("spot")
    heading = name if not spot else '%s <span class="spot">&mdash; %s</span>' % (name, esc(spot))
    out.append("  <h3>%s</h3>" % heading)
    if place.get("why"):
        out.append('  <p class="why">%s</p>' % esc(place["why"]))

    attrs = []
    for field in DESCRIPTIVE_ORDER:
        value = place.get(field)
        if not value:
            continue
        label = schema_mod.value_label(field, value)
        note = schema_mod.value_help(field, value)
        title = ' title="%s"' % esc(note) if note else ""
        attrs.append("<li%s>%s</li>" % (title, esc(label)))
    if attrs:
        out.append('  <ul class="attrs">%s</ul>' % "".join(attrs))

    meta_bits = []
    if support:
        meta_bits.append("Ways to support: %s" % esc(", ".join(s.replace("_", " ") for s in support)))
    if place.get("last_checked"):
        meta_bits.append("Last sat in %s" % esc(place["last_checked"]))
    url = osm_url(place.get("id", ""))
    if url:
        meta_bits.append('<a href="%s">On OpenStreetMap</a>' % esc(url))
    if place.get("suggested_by"):
        meta_bits.append("Suggested by %s" % esc(place["suggested_by"]))
    if meta_bits:
        out.append('  <p class="meta">%s</p>' % " &middot; ".join(meta_bits))

    out.append("</article>")
    return "\n".join(out)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--places", default=PLACES, help="Corpus to render.")
    parser.add_argument("--out", default=OUT)
    args = parser.parse_args(argv)

    places = load_places(args.places)
    page = render(places, schema_mod.gates(), chip_definitions(places))
    with open(args.out, "w") as fh:
        fh.write(page)
    copied = copy_alongside(os.path.dirname(os.path.abspath(args.out)))
    print("wrote %s — %d place%s, %d filter chips, %d file%s published alongside"
          % (os.path.relpath(args.out, ROOT), len(places),
             "" if len(places) == 1 else "s", len(chip_definitions(places)),
             copied, "" if copied == 1 else "s"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
