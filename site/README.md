# The reading surface

`suggest.html` is built. The list itself is not, and is the next thing.

## What exists

`suggest.html` — the contribution form for people without a GitHub account.
**Generated from the schema** by `scripts/build_forms.py`; do not edit it by
hand, because the next run will overwrite it. It asks the four gates first with
the answers required, so someone whose place does not qualify finds out in
fifteen seconds rather than after writing a paragraph. It posts nothing
anywhere: it writes out a message for the contributor to email, which is the
only way to collect a suggestion with no server involved.

Before the site goes up, set `SUGGESTIONS_EMAIL` in `scripts/build_forms.py`
and rerun it. It currently holds a placeholder, because putting a real address
into a public page is a decision to publish it rather than a detail.

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
