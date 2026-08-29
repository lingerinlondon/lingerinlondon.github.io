# Fixtures

Test data, not corpus data. Nothing here is a real place, and
`scripts/validate.py` never reads this directory unless pointed at it with
`--file`.

`valid.geojson` must pass — it also carries two entries sharing one OSM id,
told apart by their `spot`, since that is the case most likely to break.
Every other `.geojson` must fail, on the check its name gives.
`tests/run_fixtures.py` asserts that.

The four `gate_*.geojson` files are the eligibility criteria. They matter more
than the rest: their error messages are read by someone who has just been told
their suggestion does not fit, and the wording is part of what is being tested.
