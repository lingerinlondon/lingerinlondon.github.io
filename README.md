# Linger in London

An open, forkable directory of central London places you can turn up to, stay a while, and
pay nothing. It records what a place *doesn't* ask of you - no payment to enter or sit, no
time pressure, no obligation to talk or take part. The scope is central London: `data/boundary.geojson` is the authoritative outline,
and anything outside it fails validation.

There are no ratings, no review counts and no popularity ordering, and there never will be.

## The four gates

A place belongs here only if all four of these are true. They are not scores — a place that
fails one is not a worse place, it is a place this particular list is not for.

1. **There is nothing you have to pay to get in.** A donation box passes: it is an option to
   support the place, not a price.
2. **You can sit down without buying anything.**
3. **You could stay for hours without anyone minding.** No stated limit, and no atmospheric
   pressure either — the feeling that you have been there a while is enough to fail.
4. **There is somewhere to sit down.**

They live in `schema/place.schema.json` as pinned enum values, which is why the validator
rejects a place that fails one and why both contribution forms ask exactly these four
questions first. Everything else in the schema is description, and only description gets a
filter on the site: filtering on a gate would return the whole list.

The corpus is expected to stay small. Very few places actually clear all four.

## What is here

| Path | |
|---|---|
| `data/boundary.geojson` | The project boundary. Authoritative. |
| `data/places.geojson` | The corpus. |
| `schema/place.schema.json` | The single source of truth. Validation, both forms and the site's filters all derive from it. |
| `scripts/` | Validation, form generation, building the list. Python 3, two dependencies. |
| `site/suggest.html` | The contribution form for people without a GitHub account. Generated — do not edit. |
| `.github/ISSUE_TEMPLATE/` | The contribution form for people with one. Generated — do not edit. |

## Suggesting a place

Two ways in, and both end with a person reading the suggestion before anything is published.

- **With a GitHub account:** open an issue using the *Suggest a place* form.
- **Without one:** fill in `suggest.html`, which writes out a message to email. The page
  sends nothing itself and collects nothing about you, because there is no server.

Both forms put the four gates first and require them, so nobody writes a paragraph before
finding out the place is out of scope.

## Running things

Install the one dependency:

```bash
python3 -m pip install -r requirements.txt
```

Check the corpus — schema, gates, boundary, duplicate entries. CI runs this on every pull
request, which just means a robot re-runs it automatically and marks the request pass or fail:

```bash
python3 -m scripts.validate
```

Regenerate both contribution forms after changing the schema. They are generated rather than
hand-written so that a form can never ask different questions from the ones the validator
checks:

```bash
python3 -m scripts.build_forms
```

Rebuild the list after adding a place, and open it to check before pushing:

```bash
python3 -m scripts.build_site && open site/index.html
```

Run every check:

```bash
python3 -m tests.run_fixtures && python3 -m tests.run_forms && python3 -m tests.run_site && python3 -m tests.run_issue
```

## Identity, and why an entry can share an OSM id

Every place is keyed to the OpenStreetMap element it sits in or on — `osm:way/123456` —
which gives each entry a link a reader can follow to a map somebody else maintains.

The key is the **pair** of `id` and `spot`, not the id alone. The benches under the canopy
and the top floor by the window can be genuinely different places to sit inside one
building, and the corpus should be able to say so. `spot` names a location and nothing else;
judgement belongs in the one `why` sentence.

Overture GERS ids stay valid in the schema, but are not used. GERS solves stable identity at
machine scale, which is not a problem this project has at forty-ish places.

## Verified and unverified

**Verified** means someone has physically sat there. **Unverified** means a suggestion has
been read and accepted, but nobody has been yet. Both live in `data/places.geojson`, and the
two must never be silently mixed when displayed.

## State of things

The schema is **v0 and provisional**. It was written before the survey, which is fieldwork
rather than code: roughly fifty visits, whose actual output is the schema rather than the
data. Expect fields to be merged, split or dropped afterwards. Everything here is built to
make that change cheap — including the forms, which are regenerated rather than rewritten.

