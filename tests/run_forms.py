"""Check the contribution forms still match the schema. Run: python -m tests.run_forms

The risk these guard against is drift: a form asking questions the validator
does not check, or checking gates the form never asked about. Someone fills it
in honestly and gets rejected for it.

The YAML is not parsed here — that would cost a second dependency for a
one-time syntax risk, and GitHub reports a malformed issue form itself. What is
checked is that every gate reaches both forms, marked required.
"""

import os
import sys

from scripts import build_forms, schema as schema_mod

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def main():
    failures = []
    gates = schema_mod.gates()

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
    for name in build_forms.DESCRIPTIVE:
        for value in schema_mod.enum_values(name) or []:
            if value not in issue:
                failures.append("the issue form omits %s=%s" % (name, value))
            if value not in page:
                failures.append("the email form omits %s=%s" % (name, value))
    if 'name="conversation" required' in page:
        failures.append("a descriptive field is required in the email form; only gates may be")
    if not failures:
        print("ok   every descriptive value is offered, and none of them are required")

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
