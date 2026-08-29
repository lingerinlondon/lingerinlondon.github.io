"""Every question the contribution forms ask, defined once.

Both forms are generated from this, and scripts/issue_to_place.py reads issues
back with it. That matters more than it sounds: a question that exists in the
form but not the parser silently loses someone's answer, and a label that
drifts by one word breaks parsing with no error anywhere. One definition means
neither can happen.

Field-level truth still lives in schema/place.schema.json. This says which
questions get asked, in what order, and in what words.
"""

import datetime

from scripts import schema as schema_mod

# A contribution older than this is turned away at the form. Places change, and
# a visit from two years ago is a memory rather than a report. This is NOT decay:
# an entry already in the corpus never expires, and the validator never fails on
# age. It only governs what is accepted at the door.
MAX_AGE_DAYS = 365

DESCRIPTIVE = ("conversation", "activity", "seating", "setting")


def oldest_acceptable(today=None):
    today = today or datetime.date.today()
    return today - datetime.timedelta(days=MAX_AGE_DAYS)


def questions(schema=None):
    """The questions, in the order they are asked."""
    fields = schema_mod.fields(schema)
    out = [
        {
            "key": "gates",
            "kind": "gates",
            "label": "The four things a place has to be",
            "note": ("All four have to be true. If one of them is not, this is not the right "
                     "list for the place — which is a fact about the list, not about the place."),
            "field": None,
        },
        {
            "key": "name",
            "kind": "input",
            "label": "What is it called?",
            "note": None,
            "required": True,
            "field": "name",
        },
        {
            "key": "spot",
            "kind": "input",
            "label": "Which part of it, if the whole place is not the point?",
            "note": ("Optional. Somewhere like “top floor, by the window” or “the benches "
                     "under the canopy”. Leave empty for the place as a whole."),
            "required": False,
            "field": "spot",
        },
        {
            "key": "where",
            "kind": "input",
            "label": "Where is it?",
            "note": "A street and area is plenty.",
            "required": True,
            "field": None,  # context for the reviewer, not a stored field
        },
        {
            "key": "osm_id",
            "kind": "input",
            "label": "Its OpenStreetMap id, if you know it",
            "note": ("Optional. Find the place on openstreetmap.org, click it, and the "
                     "address bar shows something like /way/123456. Paste that, or the whole "
                     "link. Leave it empty and it will be looked up for you."),
            "required": False,
            "field": "id",
        },
        {
            "key": "coordinates",
            "kind": "input",
            "label": "Its coordinates, if you know them",
            "note": ("Optional. Two numbers, latitude first: 51.5194, -0.1270. On "
                     "openstreetmap.org, right-click the spot and choose “show address”."),
            "required": False,
            "field": None,  # becomes the geometry rather than a property
        },
        {
            "key": "last_checked",
            "kind": "date",
            "label": "When were you last there?",
            "note": ("Places change, so a suggestion needs a date. Within the last year, "
                     "please — anything older is a memory rather than a report."),
            "required": True,
            "field": "last_checked",
        },
        {
            "key": "why",
            "kind": "textarea",
            "label": "Why is it here?",
            "note": ("One sentence, up to 200 characters. Why does this place feel like a "
                     "comfortable place to just ‘be’ in London?"),
            "required": True,
            "field": "why",
        },
    ]

    for name in DESCRIPTIVE:
        meta = fields[name].get("x-filter") or {}
        out.append({
            "key": name,
            "kind": "dropdown",
            "label": meta.get("label", name),
            "note": None,
            "required": False,
            "field": name,
            "values": meta.get("values") or {},
            "options": schema_mod.enum_values(name, schema) or [],
        })

    out.append({
        "key": "support_options",
        "kind": "checkboxes",
        "label": "Ways to support the place, if there are any",
        "note": ("Listed on the site and never ranked or ordered by. A place with none of "
                 "these is not worse than a place with four."),
        "required": False,
        "field": "support_options",
        "options": schema_mod.enum_values("support_options", schema) or [],
    })
    out.append({
        "key": "suggested_by",
        "kind": "input",
        "label": "How would you like to be credited?",
        "note": "Optional. Leave empty for no credit.",
        "required": False,
        "field": "suggested_by",
    })
    return out


def option_label(value, described):
    """How an enum value is written in a form, and read back out of one."""
    return "%s — %s" % (value, described) if described else value


def value_from_option(text, allowed):
    """Read a value back from what a form displayed."""
    text = (text or "").strip()
    if not text:
        return None
    head = text.split("—")[0].strip()
    for value in allowed:
        if head == value or text == value:
            return value
    return None
