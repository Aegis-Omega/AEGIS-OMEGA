#!/usr/bin/env python3
"""Audit complete Lean `#print axioms` output for an exact target surface.

This parses an axiom log, not a proof object. The caller must separately require
successful Lean execution and bind the log to the exact source/environment.
Only records and whitespace are accepted; diagnostics and malformed output fail.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
from typing import Iterable


ALLOWED_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})
RECORD = re.compile(
    r"'(?P<name>[^'\r\n]+)'[ \t]+(?:"
    r"does not depend on any axioms"
    r"|depends on axioms:[ \t\r\n]*\[(?P<axioms>[^\]]*)\])"
    r"(?=\s|\Z)"
)


class AuditError(ValueError):
    """Missing, malformed, duplicate, or disallowed axiom evidence."""


def audit_axiom_log(log: str, theorems: Iterable[str]) -> dict[str, list[str]]:
    """Return the exact theorem-to-axioms mapping or raise AuditError.

    Supports Lean's multiline bracket lists, empty bracket lists, and
    `does not depend on any axioms`. No `assert` controls acceptance.
    """
    targets = list(theorems)
    if not targets:
        raise AuditError("at least one exact theorem is required")
    if any(not isinstance(n, str) or not n or any(c in n for c in "'\r\n")
           or n != n.strip() for n in targets):
        raise AuditError("invalid theorem name")
    if len(set(targets)) != len(targets):
        raise AuditError("duplicate requested theorem")

    expected = set(targets)
    found: dict[str, list[str]] = {}
    position = 0
    while position < len(log):
        whitespace = re.match(r"\s*", log[position:])
        # re.match always succeeds for this pattern; an explicit check keeps
        # all acceptance logic active under Python's -O mode.
        if whitespace is None:
            raise AuditError("cannot parse whitespace")
        position += whitespace.end()
        if position == len(log):
            break
        record = RECORD.match(log, position)
        if record is None:
            raise AuditError(f"unparsed or malformed log at character {position}")
        name = record.group("name")
        if name not in expected:
            raise AuditError(f"unexpected theorem record: {name}")
        if name in found:
            raise AuditError(f"duplicate theorem record: {name}")

        body = record.group("axioms")
        axioms = [] if body is None or not body.strip() else [
            item.strip() for item in body.split(",")
        ]
        if any(not axiom for axiom in axioms):
            raise AuditError(f"malformed axiom list: {name}")
        if len(set(axioms)) != len(axioms):
            raise AuditError(f"duplicate axiom in list: {name}")
        unexpected = set(axioms) - ALLOWED_AXIOMS
        if unexpected:
            raise AuditError(f"unexpected axioms for {name}: {sorted(unexpected)!r}")
        found[name] = sorted(axioms)
        position = record.end()

    missing = expected - found.keys()
    if missing:
        raise AuditError(f"missing theorem records: {sorted(missing)!r}")
    return {name: found[name] for name in targets}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", required=True, type=Path)
    parser.add_argument("--theorem", action="append", required=True)
    args = parser.parse_args(argv)
    try:
        surface = audit_axiom_log(args.log.read_text(encoding="utf-8"), args.theorem)
    except (AuditError, OSError, UnicodeError) as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    print(json.dumps({"axiom_audit": "PASS", "theorems": surface}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
