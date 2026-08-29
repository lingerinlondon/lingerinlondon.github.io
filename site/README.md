# The reading surface

Two pages, both generated. Neither should be edited by hand.

## index.html — the list

Built by `scripts/build_site.py` from the schema and `data/places.geojson`.
**Not committed**: the deploy workflow generates it. That way adding a place is
a one-file change, and a contributor's pull request can never fail on a build
artefact they had no way of regenerating. Build it locally to look at it:

```bash
python3 -m scripts.build_site
```

Everything on it is decided by the schema. Filter chips come from `x-filter` —
a field with a `chip` becomes one toggle, a field with `values` becomes a group
of them — so adding a filterable field adds chips without anyone editing
JavaScript. The four gates come from `x-gate` and are deliberately *not*
filters: every place passes them, so a chip would filter nothing. They are the
masthead instead.

The whole list is in the HTML. JavaScript only hides rows when a chip is
pressed, so with scripting off you get every place and no filtering, which is
the right way round. No map, no tiles, no fonts to fetch, nothing that reaches
a third party — `tests/run_site.py` fails the build if any of that changes.

## What exists

`suggest.html` — the contribution form for people without a GitHub account.
**Generated from the schema** by `scripts/build_forms.py`; do not edit it by
hand, because the next run will overwrite it. It asks the four gates first with
the answers required, so someone whose place does not qualify finds out in
fifteen seconds rather than after writing a paragraph. It posts nothing
anywhere: it writes out a message for the contributor to email, which is the
only way to collect a suggestion with no server involved.

The contact address is a plain `mailto:` in `scripts/build_forms.py`. It is not
obfuscated, deliberately: that address is already public wherever the apps list
it, so hiding it here would buy nothing real while making the page odd to read.
Spam filtering happens at the mail provider, which is where it belongs.

## What is decided for the list

- **A list, not a map.** No Leaflet, no tile layer, no basemap. A tile server is
  a third-party request from every visitor's browser, and the alternatives cost
  more than the list does.
- **Filter chips generated from the schema at load time**, the same way the
  forms are generated. `scripts/schema.py:filters()` already derives them.
  Note that gates are deliberately absent: every place passes them, so a chip
  would filter nothing. "Free to enter" and "no time pressure" belong at the top
  of the page as the statement of what the list is, not as things to toggle.
- Verified and unverified must be visually distinct, with the difference
  explained rather than implied. Unverified now means *suggested and reviewed,
  but not yet sat in*.
- Each entry: name, `spot` where there is one, the `why` sentence, the
  descriptive fields, `verified_date`, a link to the OSM element, and support
  options listed plainly and never ordered by.

## Still open

What the list sorts by, given that popularity ordering is out by rule.
Alphabetical is the boring answer and probably the right one.
