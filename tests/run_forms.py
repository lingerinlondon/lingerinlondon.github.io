"""Check the contribution forms still match the schema. Run: python -m tests.run_forms

Two risks. Drift: a form asking questions the validator does not check, or
checking gates the form never asked about — someone fills it in honestly and is
rejected for it. And malformation: GitHub does not report a broken issue form,
it silently serves no form at all, so the first symptom is a contributor who
cannot find how to contribute.

The issue form is therefore parsed and checked against GitHub's structure, not
eyeballed. It was eyeballed once, and shipped with `options` one level too high,
which is invalid and invisible.
"""

import os
import sys

from scripts import build_forms, form_spec, schema as schema_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


# What GitHub accepts in an issue form. Only what this project uses.
BODY_TYPES = ("markdown", "input", "textarea", "dropdown", "checkboxes")


def check_issue_form_structure(path):
    """Parse the issue form and hold it to GitHub's shape."""
    import yaml

    problems = []
    try:
        doc = yaml.safe_load(open(path))
    except yaml.YAMLError as exc:
        return ["the issue form is not valid YAML, so GitHub will serve no form at all:\n"
                "  %s" % str(exc).replace("\n", "\n  ")]
    if not isinstance(doc, dict):
        return ["the issue form does not parse to a mapping"]

    for key in ("name", "description", "body"):
        if key not in doc:
            problems.append("the issue form has no top-level %r" % key)
    if problems:
        return problems

    for i, item in enumerate(doc["body"]):
        where = "body item %d (%s)" % (i, item.get("id") or item.get("type"))
        kind = item.get("type")
        if kind not in BODY_TYPES:
            problems.append("%s has type %r, which GitHub does not accept" % (where, kind))
            continue
        attributes = item.get("attributes")
        if not isinstance(attributes, dict):
            problems.append("%s has no attributes block" % where)
            continue
        if kind == "markdown":
            if "value" not in attributes:
                problems.append("%s is markdown with no value" % where)
            continue
        if "label" not in attributes:
            problems.append("%s has no label" % where)

        # The mistake that silently kills the whole form: options must live
        # inside attributes, not beside it.
        if "options" in item:
            problems.append("%s puts options beside attributes; GitHub needs it inside, "
                            "and rejects the entire form otherwise" % where)
        if kind in ("dropdown", "checkboxes"):
            options = attributes.get("options")
            if not isinstance(options, list) or not options:
                problems.append("%s is a %s with no options inside attributes" % (where, kind))
            elif kind == "checkboxes":
                bad = [o for o in options if not isinstance(o, dict) or "label" not in o]
                if bad:
                    problems.append("%s has checkbox options that are not label entries" % where)
            elif kind == "dropdown":
                bad = [o for o in options if not isinstance(o, str)]
                if bad:
                    problems.append("%s has dropdown options that are not plain strings" % where)
        if kind == "checkboxes" and "validations" in item:
            problems.append("%s puts validations on a checkboxes block; required goes on "
                            "each option instead" % where)
    return problems


def main():
    failures = []
    gates = schema_mod.gates()

    structure = check_issue_form_structure(build_forms.ISSUE_FORM)
    if structure:
        failures.extend(structure)
    else:
        print("ok   the issue form parses and matches GitHub's structure")

    if build_forms.main(["--check"]) != 0:
        failures.append("the committed forms are out of date — run python -m scripts.build_forms")
    else:
        print("ok   both forms match the current schema")

    issue = open(build_forms.ISSUE_FORM).read()
    page = open(build_forms.HTML_FORM).read()

    for gate in gates:
        confirm = gate["confirm"]
        if confirm not in issue:
            failures.append("the issue form never asks: %s" % confirm)
        else:
            block = issue.split(confirm, 1)[1][:80]
            if "required: true" not in block:
                failures.append("the issue form asks %r but does not require it" % confirm)
        if confirm not in page:
            failures.append("the email form never asks: %s" % confirm)
        elif 'id="gate_%s" name="gate_%s" required' % (gate["field"], gate["field"]) not in page:
            failures.append("the email form asks %r but does not require it" % confirm)
    if not failures:
        print("ok   all %d gates are asked first and required in both forms" % len(gates))

    # Descriptive fields must be offered, but never as a requirement — a
    # contributor who does not know whether talking is allowed should still
    # be able to suggest the place.
    for name in form_spec.DESCRIPTIVE:
        for value in schema_mod.enum_values(name) or []:
            if value not in issue:
                failures.append("the issue form omits %s=%s" % (name, value))
            if value not in page:
                failures.append("the email form omits %s=%s" % (name, value))
    if 'name="conversation" required' in page:
        failures.append("a descriptive field is required in the email form; only gates may be")
    if not failures:
        print("ok   every descriptive value is offered, and none of them are required")

    # The date question is the one the good-faith model depends on.
    date_question = next(q for q in form_spec.questions() if q["key"] == "last_checked")
    if date_question["label"] not in issue or date_question["label"] not in page:
        failures.append("neither form asks when the contributor was last there")
    elif 'type="date"' not in page or 'min="%s"' % form_spec.oldest_acceptable().isoformat() not in page:
        failures.append("the email form does not stop a visit older than a year")
    else:
        print("ok   both forms ask when, and the browser refuses a visit over a year old")

    # Someone with a GitHub account should be sent to the better route, not
    # left transcribing into an email because the page never mentioned it.
    if build_forms.ISSUE_FORM_URL not in page:
        failures.append("the email form does not offer the GitHub route to people who have one")
    else:
        print("ok   the page points GitHub users at the issue form instead")

    if build_forms.SUGGESTIONS_EMAIL not in page:
        failures.append("the email form gives no address to send the message to")
    else:
        print("ok   the email form says where to send the message")

    if failures:
        print("\n%d form check(s) failed:\n" % len(failures))
        for f in failures:
            print(f + "\n")
        return 1
    print("\nContribution forms match the schema.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
