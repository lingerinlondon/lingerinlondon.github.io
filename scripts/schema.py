"""Loading and introspecting schema/place.schema.json.

Everything that needs to know what a field is asks this module. Nothing —
not the validator, not the seeder, not the site — keeps its own copy of the
field list.
"""

import json
import os

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema", "place.schema.json"
)

PROFILES = ("place", "candidate")


def load_schema(path=SCHEMA_PATH):
    with open(path) as fh:
        return json.load(fh)


def fields(schema=None):
    """Field name -> field subschema, in declaration order."""
    schema = schema or load_schema()
    return schema["$defs"]["common"]["properties"]


def enum_values(field_name, schema=None):
    """Allowed non-null values for an enum field, or None if it isn't one."""
    f = fields(schema).get(field_name)
    if not f:
        return None
    if "enum" in f:
        return [v for v in f["enum"] if v is not None]
    items = f.get("items") or {}
    if "enum" in items:
        return [v for v in items["enum"] if v is not None]
    return None


def filters(schema=None):
    """Filter definitions for the reading surface, derived from x-filter.

    Adding a filterable field to the schema must add a filter to the site
    without anyone editing JavaScript. This function is that promise.
    """
    schema = schema or load_schema()
    out = []
    for name, f in fields(schema).items():
        meta = f.get("x-filter")
        if not meta:
            continue
        out.append(
            {
                "field": name,
                "label": meta.get("label", name),
                "chip": meta.get("chip"),
                "match": meta.get("match"),
                "values": meta.get("values", {}),
                "multi": f.get("type") == ["array", "null"] or f.get("type") == "array",
            }
        )
    return out


def validator(profile="place", schema=None):
    """A jsonschema validator for one profile.

    place     — the published corpus, which must carry a why sentence.
    candidate — desk-seeded and unvisited, where nearly everything is null.
    """
    from jsonschema import Draft202012Validator, FormatChecker

    if profile not in PROFILES:
        raise ValueError("unknown profile %r, expected one of %s" % (profile, ", ".join(PROFILES)))
    schema = schema or load_schema()
    rooted = dict(schema)
    rooted["$ref"] = "#/$defs/%s" % profile
    return Draft202012Validator(rooted, format_checker=FormatChecker())
