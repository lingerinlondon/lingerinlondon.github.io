# Fixtures

Test data, not corpus data. Nothing in this directory is a real entry, and
`scripts/validate.py` never reads it unless pointed at it with `--file`.

`valid.geojson` must pass. Every other file must fail, and must fail on the
check its name gives. `tests/run_fixtures.py` is what asserts that.
