# Central London Third Places

An open, forkable directory of central London places you can turn up to, stay a while, and
pay nothing. It records what a place *doesn't* ask of you — no payment to enter or sit, no
time pressure, no obligation to talk or take part — because that is the axis nothing else
indexes and the reason these places are hard to search for. The scope is central London and
it is stated in the name on purpose: `data/boundary.geojson` is the authoritative outline,
and anything outside it fails validation.

There are no ratings, no review counts and no popularity ordering, and there never will be.
Ranking by popularity is the specific failure this project exists to avoid.

## What is here

| Path | |
|---|---|
| `data/boundary.geojson` | The project boundary. Authoritative; the prose in the plan is commentary. |
| `data/places.geojson` | The corpus. Currently empty — it fills up on foot. |
| `data/candidates.geojson` | Desk-seeded from OpenStreetMap, unverified, a list of places to go and sit in. |
| `schema/place.schema.json` | The single source of truth for fields. Validation and the site's filters both derive from it. |
| `scripts/` | Seeding, validation, and survey import. Python 3, one dependency. |
| `site/` | The reading surface. Not built yet — see `site/README.md`. |
| `docs/PLAN.md` | Why the project is shaped this way. Read before proposing architecture changes. |

## Running things

Install the one dependency:

```bash
python3 -m pip install -r requirements.txt
```

Check the corpus — schema, boundary, duplicate ids. CI runs this on every pull request:

```bash
python3 -m scripts.validate
```

Seed candidates from OpenStreetMap. Responses are cached under `.cache/`, reruns are
idempotent, and it never overwrites a field someone filled in by hand:

```bash
python3 -m scripts.seed_overpass
```

Turn a survey sheet into features. Rows it cannot map are reported rather than dropped:

```bash
python3 -m scripts.survey_import visits.csv --out data/places.geojson
```

Print a blank capture sheet to fill in on a phone or on paper:

```bash
python3 -m scripts.survey_import --template
```

Run the checks that prove the validation, seeding and import all still behave:

```bash
python3 -m tests.run_fixtures && python3 -m tests.run_seed && python3 -m tests.run_survey
```

## Verified and unverified

**Verified** means someone has physically sat there. **Unverified** means it came from a
desk search of OpenStreetMap and nobody has been yet. The two are kept in separate files
and must never be silently mixed when displayed.

Most fields on an unverified candidate are `null`, and that is correct rather than
incomplete. A null is a prompt to go and look. A guessed value is indistinguishable from an
observed one a year later, which is the one mistake the corpus cannot recover from.

## State of things

The schema is **v0 and provisional**. It was written before the survey, which is fieldwork
rather than code: roughly fifty visits, whose actual output is the schema rather than the
data. Expect fields to be merged, split or dropped afterwards — `payment_to_enter` and
`payment_to_sit` most likely of all. Everything here is built to make that change cheap.

The licence is undecided; see `LICENCE` for why it waits.
