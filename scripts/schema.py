"""Loading and introspecting schema/place.schema.json.

Everything that needs to know what a field is asks this module. Nothing — not
the validator, not the contribution forms, not the site — keeps its own copy of
the field list.

Two kinds of field, and the difference matters:

  gates       what a place must be to belong here at all. Their enums are
              pinned to the passing values, so failing one is a schema error.
              These are the questions the contribution form asks first.
  descriptive true things about a place that is already in. These vary, so
              these are what the site filters on.
"""

import json
import os

SCHEMA_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "schema", "place.schema.json"
)


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


def gates(schema=None):
    """The eligibility criteria, in the order the form should ask them."""
    out = []
    for name, f in fields(schema).items():
        meta = f.get("x-gate")
        if not meta:
            continue
        out.append(
            {
                "field": name,
                "confirm": meta["confirm"],
                "excluded": meta.get("excluded"),
                "reason": meta.get("excluded_reason"),
                "allowed": enum_values(name, schema),
            }
        )
    return out


def filters(schema=None):
    """Filter definitions for the reading surface, derived from x-filter.

    Adding a descriptive field to the schema must add a filter to the site
    without anyone editing JavaScript. This function is that promise. Gates are
    absent on purpose: every place passes them, so a chip would filter nothing.
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
                "multi": f.get("type") in (["array", "null"], "array"),
            }
        )
    return out


def validator(schema=None):
    from jsonschema import Draft202012Validator, FormatChecker

    return Draft202012Validator(schema or load_schema(), format_checker=FormatChecker())
