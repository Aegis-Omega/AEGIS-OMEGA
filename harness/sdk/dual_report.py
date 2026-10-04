"""Deterministic dual-report contract for AEGIS authority decisions.

The authority result remains the source of truth. This module adds two bound
presentations of that result:
- a canonical machine-readable JSON payload; and
- a deterministic human-readable Markdown rendering.

It does not grant authority, alter policy outcomes, or perform side effects.
"""
from __future__ import annotations

import copy
import re
from typing import Any, Mapping, Sequence

from harness.sdk.sovereign_execution import (
    ADMITTED,
    DENIED,
    SovereignExecutionError,
    canonical_bytes,
    canonical_hash,
    deterministic_redaction,
    sha256_hex,
)

REPORT_SCHEMA_VERSION = "1.0.0"
REPORT_KIND = "AUTOMATON3_AUTHORITY_DECISION"
MACHINE_CONTENT_TYPE = "application/vnd.aegis.authority-report+json;version=1"
HUMAN_CONTENT_TYPE = "text/markdown; charset=utf-8"
CANONICALIZATION = "utf-8;json-sort-keys;compact-separators;allow-nan=false"
UNAVAILABLE = "UNAVAILABLE"

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")


def _mapping(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _inline(value: Any) -> str:
    if value is None:
        return UNAVAILABLE
    text = str(value).replace("\r", " ").replace("\n", " ")
    return text.replace("|", "\\|").replace("`", "\\`")


def _sha_or_unavailable(value: Any) -> str:
    return value if isinstance(value, str) and _SHA256_RE.fullmatch(value) else UNAVAILABLE


def _denial_codes(payload: Mapping[str, Any]) -> tuple[str, ...]:
    policy = _mapping(payload.get("policy_decision"))
    raw = policy.get("denial_codes", payload.get("denial_codes", ()))
    if isinstance(raw, str):
        values: Sequence[Any] = (raw,)
    elif isinstance(raw, Sequence):
        values = raw
    else:
        values = ()
    return tuple(sorted({str(item) for item in values if str(item)}))


def _bind_source_commit(source_commit: Any, outcome: str) -> tuple[str, str]:
    if isinstance(source_commit, str) and _GIT_RE.fullmatch(source_commit):
        return "BOUND", source_commit
    if outcome == ADMITTED:
        raise SovereignExecutionError("ADMITTED_REPORT_REQUIRES_EXACT_SOURCE_COMMIT")
    return "UNAVAILABLE", UNAVAILABLE


def _facts(payload: Mapping[str, Any]) -> dict[str, Any]:
    policy = _mapping(payload.get("policy_decision"))
    return {
        "outcome": payload.get("outcome", UNAVAILABLE),
        "source_commit_state": payload.get("source_commit_state", UNAVAILABLE),
        "source_commit": payload.get("source_commit", UNAVAILABLE),
        "authority_score": policy.get("authority_score", payload.get("authority_score", "0.000000")),
        "action_class": policy.get("action_class", UNAVAILABLE),
        "authority_domain": policy.get("authority_domain", UNAVAILABLE),
        "requested_capability": policy.get("requested_capability", UNAVAILABLE),
        "tool": policy.get("tool", UNAVAILABLE),
        "target_digest": _sha_or_unavailable(policy.get("target_digest")),
        "execution_identity_root": _sha_or_unavailable(payload.get("execution_identity_root")),
        "workspace_binding": _sha_or_unavailable(payload.get("workspace_binding")),
        "workspace_decision_root": _sha_or_unavailable(payload.get("workspace_decision_root")),
        "policy_decision_root": _sha_or_unavailable(
            policy.get("decision_root", payload.get("decision_root"))
        ),
        "mutation_receipt_root": _sha_or_unavailable(payload.get("mutation_receipt_root")),
        "denial_receipt_root": _sha_or_unavailable(payload.get("denial_receipt_root")),
        "denial_codes": list(_denial_codes(payload)),
    }


def _validate_admitted_facts(facts: Mapping[str, Any]) -> None:
    if facts["source_commit_state"] != "BOUND":
        raise SovereignExecutionError("ADMITTED_REPORT_EXACT_HEAD_UNBOUND")
    required_roots = (
        "execution_identity_root",
        "workspace_binding",
        "workspace_decision_root",
        "policy_decision_root",
        "mutation_receipt_root",
    )
    for name in required_roots:
        if facts[name] == UNAVAILABLE:
            raise SovereignExecutionError(f"ADMITTED_REPORT_MISSING_{name.upper()}")
    if facts["denial_codes"]:
        raise SovereignExecutionError("ADMITTED_REPORT_CONTAINS_DENIAL_CODES")


def _render_human(
    facts: Mapping[str, Any],
    *,
    machine_payload_sha256: str,
    attestation_root: str,
) -> str:
    denial_codes = tuple(facts.get("denial_codes", ()))
    lines = [
        "# AEGIS Authority Decision Report",
        "",
        "This is the human-readable view of the same evidence payload emitted for machines.",
        "It is presentation-only and cannot grant or expand authority.",
        "",
        "## Decision",
        "",
        f"- **Outcome:** `{_inline(facts.get('outcome'))}`",
        f"- **Authority score:** `{_inline(facts.get('authority_score'))}`",
        f"- **Exact-head state:** `{_inline(facts.get('source_commit_state'))}`",
        f"- **Source commit:** `{_inline(facts.get('source_commit'))}`",
        f"- **Action class:** `{_inline(facts.get('action_class'))}`",
        f"- **Authority domain:** `{_inline(facts.get('authority_domain'))}`",
        f"- **Requested capability:** `{_inline(facts.get('requested_capability'))}`",
        f"- **Tool:** `{_inline(facts.get('tool'))}`",
        "",
        "## Evidence roots",
        "",
        f"- **Execution identity:** `{_inline(facts.get('execution_identity_root'))}`",
        f"- **Workspace binding:** `{_inline(facts.get('workspace_binding'))}`",
        f"- **Workspace decision:** `{_inline(facts.get('workspace_decision_root'))}`",
        f"- **Policy decision:** `{_inline(facts.get('policy_decision_root'))}`",
        f"- **Mutation receipt:** `{_inline(facts.get('mutation_receipt_root'))}`",
        f"- **Denial receipt:** `{_inline(facts.get('denial_receipt_root'))}`",
        "",
        "## Denial codes",
        "",
    ]
    if denial_codes:
        lines.extend(f"- `{_inline(code)}`" for code in denial_codes)
    else:
        lines.append("- None.")
    lines.extend(
        [
            "",
            "## Integrity",
            "",
            f"- **Machine payload SHA-256:** `{machine_payload_sha256}`",
            f"- **Report attestation root:** `{attestation_root}`",
            "",
            "The machine payload hash covers the full redacted authority result, including the exact-head binding,",
            "but excludes this `reports` presentation envelope to avoid self-reference.",
            "",
        ]
    )
    return "\n".join(lines)


def build_dual_report(result: Mapping[str, Any], *, source_commit: Any = None) -> dict[str, Any]:
    """Return a redacted machine document carrying a bound human rendering."""
    if not isinstance(result, Mapping):
        raise SovereignExecutionError("REPORT_RESULT_NOT_MAPPING")

    machine_payload = deterministic_redaction(copy.deepcopy(dict(result)))
    if "reports" in machine_payload:
        raise SovereignExecutionError("REPORTS_FIELD_RESERVED")

    outcome = machine_payload.get("outcome")
    if outcome not in (ADMITTED, DENIED):
        raise SovereignExecutionError("REPORT_OUTCOME_INVALID")

    source_state, normalized_commit = _bind_source_commit(source_commit, outcome)
    machine_payload["source_commit_state"] = source_state
    machine_payload["source_commit"] = normalized_commit

    facts = _facts(machine_payload)
    if outcome == ADMITTED:
        _validate_admitted_facts(facts)

    machine_sha = sha256_hex(canonical_bytes(machine_payload))
    attestation_body = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "machine_payload_sha256": machine_sha,
        "facts": facts,
    }
    attestation_root = canonical_hash(
        "AEGIS_DUAL_REPORT_ATTESTATION_V1", attestation_body
    )
    human = _render_human(
        facts,
        machine_payload_sha256=machine_sha,
        attestation_root=attestation_root,
    )
    human_sha = sha256_hex(human.encode("utf-8"))
    bundle_root = canonical_hash(
        "AEGIS_DUAL_REPORT_BUNDLE_V1",
        {
            "attestation_root": attestation_root,
            "human_sha256": human_sha,
        },
    )

    document = copy.deepcopy(machine_payload)
    document["reports"] = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_kind": REPORT_KIND,
        "machine": {
            "content_type": MACHINE_CONTENT_TYPE,
            "canonicalization": CANONICALIZATION,
            "payload_sha256": machine_sha,
        },
        "human": {
            "content_type": HUMAN_CONTENT_TYPE,
            "sha256": human_sha,
            "markdown": human,
        },
        "binding": {
            "attestation_root": attestation_root,
            "bundle_root": bundle_root,
        },
    }
    verify_dual_report(document)
    return document


def verify_dual_report(document: Mapping[str, Any]) -> bool:
    """Verify that machine and human views are bound to one authority result."""
    if not isinstance(document, Mapping):
        raise SovereignExecutionError("REPORT_DOCUMENT_NOT_MAPPING")

    payload = copy.deepcopy(dict(document))
    reports = payload.pop("reports", None)
    if not isinstance(reports, Mapping):
        raise SovereignExecutionError("REPORT_ENVELOPE_MISSING")

    machine = _mapping(reports.get("machine"))
    human = _mapping(reports.get("human"))
    binding = _mapping(reports.get("binding"))

    if reports.get("schema_version") != REPORT_SCHEMA_VERSION:
        raise SovereignExecutionError("REPORT_SCHEMA_UNSUPPORTED")
    if reports.get("report_kind") != REPORT_KIND:
        raise SovereignExecutionError("REPORT_KIND_UNSUPPORTED")
    if machine.get("content_type") != MACHINE_CONTENT_TYPE:
        raise SovereignExecutionError("REPORT_MACHINE_CONTENT_TYPE_INVALID")
    if machine.get("canonicalization") != CANONICALIZATION:
        raise SovereignExecutionError("REPORT_CANONICALIZATION_INVALID")
    if human.get("content_type") != HUMAN_CONTENT_TYPE:
        raise SovereignExecutionError("REPORT_HUMAN_CONTENT_TYPE_INVALID")

    outcome = payload.get("outcome")
    if outcome not in (ADMITTED, DENIED):
        raise SovereignExecutionError("REPORT_OUTCOME_INVALID")

    source_state, normalized_commit = _bind_source_commit(
        payload.get("source_commit"), outcome
    )
    if payload.get("source_commit_state") != source_state:
        raise SovereignExecutionError("REPORT_SOURCE_COMMIT_STATE_MISMATCH")
    if payload.get("source_commit") != normalized_commit:
        raise SovereignExecutionError("REPORT_SOURCE_COMMIT_MISMATCH")

    facts = _facts(payload)
    if outcome == ADMITTED:
        _validate_admitted_facts(facts)

    machine_sha = sha256_hex(canonical_bytes(payload))
    if machine.get("payload_sha256") != machine_sha:
        raise SovereignExecutionError("REPORT_MACHINE_PAYLOAD_HASH_MISMATCH")

    attestation_root = canonical_hash(
        "AEGIS_DUAL_REPORT_ATTESTATION_V1",
        {
            "schema_version": REPORT_SCHEMA_VERSION,
            "report_kind": REPORT_KIND,
            "machine_payload_sha256": machine_sha,
            "facts": facts,
        },
    )
    if binding.get("attestation_root") != attestation_root:
        raise SovereignExecutionError("REPORT_ATTESTATION_ROOT_MISMATCH")

    expected_human = _render_human(
        facts,
        machine_payload_sha256=machine_sha,
        attestation_root=attestation_root,
    )
    if human.get("markdown") != expected_human:
        raise SovereignExecutionError("REPORT_HUMAN_RENDERING_MISMATCH")

    human_sha = sha256_hex(expected_human.encode("utf-8"))
    if human.get("sha256") != human_sha:
        raise SovereignExecutionError("REPORT_HUMAN_HASH_MISMATCH")

    bundle_root = canonical_hash(
        "AEGIS_DUAL_REPORT_BUNDLE_V1",
        {
            "attestation_root": attestation_root,
            "human_sha256": human_sha,
        },
    )
    if binding.get("bundle_root") != bundle_root:
        raise SovereignExecutionError("REPORT_BUNDLE_ROOT_MISMATCH")

    return True
