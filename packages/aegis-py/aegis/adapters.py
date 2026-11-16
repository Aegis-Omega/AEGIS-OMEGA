"""Typed evidence adapters: each one says exactly what it proves.

A green check is not evidence until it is bound to an artifact, a verifier and
an exact source head. Every adapter here returns one machine-readable receipt:

    receipt = lean_axioms(output, theorem="Foo.bar", claim="unconditional",
                          verifier={"name": "lean", "version": "4.12.0"},
                          environment={"os": "linux"}, source_head="<40-hex sha>")
    is_receipt_consistent(receipt, expected_head="<40-hex sha>")

Status is one of:
    verified  the output supplied to the adapter satisfied the check, within `scope`
    rejected  the check failed, or the evidence contradicts its binding
    unknown   the evidence is missing, unparsable or unbound

A receipt is informational. It is NOT authentication: the caller supplies the
verifier name, environment and head, and `receipt_digest` only detects edits to a
receipt, not fabrication of one. Nothing here runs a verifier or signs anything.
`can_promote` therefore denies unless the host passes an external `admission`
callback (signature, runner observation, operator approval) that returns True.

Not covered (open on #751): browser/DOM, production probes, research
citations, and wiring into the #746/#747 issue gate, which is not on main.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
from typing import Any

from .receipts import digest

VERIFIED, REJECTED, UNKNOWN = "verified", "rejected", "unknown"
SCHEMA = "AEGIS_EVIDENCE_RECEIPT_V1"
STANDARD_AXIOMS = frozenset({"propext", "Classical.choice", "Quot.sound"})
_HEAD = re.compile(r"[0-9a-f]{40}")


def _receipt(kind: str, artifact: bytes, *, verifier: dict | None, environment: dict | None,
             source_head: str | None, expected_digest: str | None, status: str,
             reasons: list[str], scope: str, details: dict) -> dict:
    raw = hashlib.sha256(artifact).hexdigest()
    reasons = list(reasons)
    if not (isinstance(verifier, dict) and verifier.get("name") and verifier.get("version")):
        reasons.append("verifier_unidentified")
    if not isinstance(source_head, str) or not _HEAD.fullmatch(source_head):
        reasons.append("source_head_unbound")
    if not environment:
        reasons.append("environment_missing")
    if expected_digest is not None and expected_digest != raw:
        reasons.append("artifact_digest_mismatch")
        status = REJECTED
    elif any(r in reasons for r in ("verifier_unidentified", "source_head_unbound",
                                    "environment_missing")) and status == VERIFIED:
        status = UNKNOWN
    body = {"schema": SCHEMA, "kind": kind, "status": status, "reasons": reasons,
            "scope": scope, "artifact_sha256": raw, "verifier": verifier,
            "environment": environment, "source_head": source_head, "details": details}
    return {**body, "receipt_digest": digest(body)}


def is_receipt_consistent(receipt: dict, *, expected_head: str) -> bool:
    """True if the receipt is internally consistent, `verified` and names `expected_head`.

    This is self-consistency only. Anyone can fabricate a receipt that passes it,
    because the digest is computed from the receipt's own fields. It is a necessary
    condition for promotion, never a sufficient one.
    """
    try:
        body = {k: v for k, v in receipt.items() if k != "receipt_digest"}
        return (receipt["receipt_digest"] == digest(body)
                and receipt["schema"] == SCHEMA
                and receipt["status"] == VERIFIED
                and bool(_HEAD.fullmatch(expected_head))
                and receipt["source_head"] == expected_head)
    except (KeyError, TypeError):
        return False


def can_promote(receipt: dict, *, expected_head: str, admission=None) -> bool:
    """Deny by default.

    Promotion needs an `admission(receipt) -> bool` supplied by the host that
    authenticates the receipt outside this module (signature, runner observation,
    operator approval; see #746). Without it, or if it does not return exactly
    True, the answer is False, even for a consistent `verified` receipt.
    """
    if admission is None or not is_receipt_consistent(receipt, expected_head=expected_head):
        return False
    return admission(receipt) is True


# --- formal proof -----------------------------------------------------------

_AXIOMS = re.compile(r"'(?P<name>[^']+)' depends on axioms: \[(?P<axs>[^\]]*)\]")
_NO_AXIOMS = re.compile(r"'(?P<name>[^']+)' does not depend on any axioms")


def lean_axioms(output: str, *, theorem: str, claim: str, verifier: dict | None,
                environment: dict | None, source_head: str | None,
                declared_assumptions: list[str] | None = None,
                expected_digest: str | None = None) -> dict:
    """Judge the output of `#print axioms <theorem>`.

    claim="unconditional": only the standard axioms are allowed.
    claim="conditional":   extra axioms are allowed only if each is listed in
                           `declared_assumptions`; the receipt says so.
    `sorryAx` is always rejected. Compiling is not the same as proving the
    intended statement: the scope below says what this does not establish.
    """
    scope = (f"kernel-checked relative to the listed axioms ({claim}); does not show that "
             f"the statement of {theorem!r} is the intended target")
    details: dict[str, Any] = {"theorem": theorem, "claim": claim, "axioms": None}
    if claim not in ("conditional", "unconditional"):
        return _receipt("lean_axioms", output.encode(), verifier=verifier, environment=environment,
                        source_head=source_head, expected_digest=expected_digest, status=UNKNOWN,
                        reasons=["claim_must_be_conditional_or_unconditional"], scope=scope,
                        details=details)
    m = _AXIOMS.search(output) or _NO_AXIOMS.search(output)
    if m is None or m.group("name") != theorem:
        return _receipt("lean_axioms", output.encode(), verifier=verifier, environment=environment,
                        source_head=source_head, expected_digest=expected_digest, status=UNKNOWN,
                        reasons=["axiom_report_missing_or_for_other_theorem"], scope=scope,
                        details=details)
    axioms = [a.strip() for a in m.groupdict().get("axs", "").split(",") if a.strip()]
    details["axioms"] = axioms
    extra = [a for a in axioms if a not in STANDARD_AXIOMS]
    reasons: list[str] = []
    status = VERIFIED
    if "sorryAx" in axioms:
        status, reasons = REJECTED, ["sorryAx_present"]
    elif extra and claim == "unconditional":
        status, reasons = REJECTED, [f"nonstandard_axioms:{','.join(extra)}"]
    elif extra and not set(extra) <= set(declared_assumptions or []):
        status, reasons = REJECTED, ["undeclared_axioms:" + ",".join(
            sorted(set(extra) - set(declared_assumptions or [])))]
    return _receipt("lean_axioms", output.encode(), verifier=verifier, environment=environment,
                    source_head=source_head, expected_digest=expected_digest, status=status,
                    reasons=reasons, scope=scope, details=details)


# --- code tests -------------------------------------------------------------

def check_test_run(summary: dict, *, verifier: dict | None, environment: dict | None,
                   source_head: str | None, expected_digest: str | None = None) -> dict:
    """Judge a test-run summary {command, collected, passed, failed, errors, skipped}.

    Proves only that this command, on this head, reported these counts. It does
    not show the tests are adequate or that the code is correct.
    """
    scope = "reported counts of one test command on one head; not test adequacy or correctness"
    keys = ("collected", "passed", "failed", "errors", "skipped")
    raw = json.dumps(summary, sort_keys=True).encode()
    ok = (isinstance(summary, dict) and summary.get("command")
          and all(isinstance(summary.get(k), int) and not isinstance(summary.get(k), bool)
                  and summary[k] >= 0 for k in keys))
    if not ok:
        return _receipt("test_run", raw, verifier=verifier, environment=environment,
                        source_head=source_head, expected_digest=expected_digest, status=UNKNOWN,
                        reasons=["summary_malformed"], scope=scope, details={})
    details = {k: summary[k] for k in ("command", *keys)}
    reasons: list[str] = []
    if summary["failed"] or summary["errors"]:
        status, reasons = REJECTED, ["failures_or_errors"]
    elif summary["passed"] == 0:
        status, reasons = UNKNOWN, ["no_tests_passed"]
    elif summary["passed"] + summary["skipped"] != summary["collected"]:
        status, reasons = UNKNOWN, ["counts_do_not_add_up"]
    else:
        status = VERIFIED
    return _receipt("test_run", raw, verifier=verifier, environment=environment,
                    source_head=source_head, expected_digest=expected_digest, status=status,
                    reasons=reasons, scope=scope, details=details)


# --- data -------------------------------------------------------------------

def data_snapshot(data: bytes, contract: dict, *, verifier: dict | None,
                  environment: dict | None, source_head: str | None) -> dict:
    """Check a CSV snapshot against {sha256, columns, rows}.

    Proves the snapshot has the pinned bytes, header and row count. It does not
    show the data is correct, unbiased or fit for any purpose.
    """
    scope = "pinned bytes, header and row count of one snapshot; not data quality"
    try:
        rows = list(csv.reader(io.StringIO(data.decode("utf-8"))))
        _ = (contract["sha256"], contract["columns"], contract["rows"])  # KeyError if incomplete
    except (UnicodeDecodeError, KeyError, TypeError, csv.Error):
        return _receipt("data_snapshot", data if isinstance(data, bytes) else b"", verifier=verifier,
                        environment=environment, source_head=source_head, expected_digest=None,
                        status=UNKNOWN, reasons=["snapshot_or_contract_unreadable"], scope=scope,
                        details={})
    details = {"rows": max(len(rows) - 1, 0), "columns": rows[0] if rows else []}
    reasons = []
    if rows[:1] != [list(contract["columns"])]:
        reasons.append("header_mismatch")
    if details["rows"] != contract["rows"]:
        reasons.append("row_count_mismatch")
    return _receipt("data_snapshot", data, verifier=verifier, environment=environment,
                    source_head=source_head, expected_digest=contract["sha256"],
                    status=REJECTED if reasons else VERIFIED, reasons=reasons, scope=scope,
                    details=details)
