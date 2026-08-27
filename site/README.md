# The reading surface — not built yet

Decided so far:

- **A list, not a map.** No Leaflet, no tile layer, no basemap. A tile server is
  a third-party request from every visitor's browser, which sits badly with the
  no-third-party rule, and the alternatives (no basemap at all, or shipping a
  self-hosted street layer) each cost more than the list does.
- The filter chips must be generated from `schema/place.schema.json` at load
  time. Adding a field to the schema adds a filter without anyone editing
  JavaScript. `scripts/schema.py:filters()` already derives them from the
  `x-filter` metadata each field carries, and is the shape the site should read.
- Verified and unverified places must be visually distinct, with the difference
  explained rather than implied.
- Each entry: name, the `why` sentence, the structured fields, `verified_date`,
  a link to the OSM element, and support options listed plainly and never
  ordered by.

Left open until the survey has run, since the schema it renders is expected to
change: whether the boundary is drawn at all without a map, and what a list
sorts by given that popularity ordering is out by rule.
