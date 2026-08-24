#!/usr/bin/env python3
"""Validate an exact Automaton-3 candidate and emit deterministic evidence.

The emitted admission receipt is scoped to repository-candidate validation. It is
not an AdmissionRecord for an external effect-bound state transition.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SHA_RE = re.compile(r"^[0-9a-f]{40,64}$")

KEY_FILES = (
    "harness/sdk/sovereign_execution.py",
    "harness/sdk/authority_client.py",
    "harness/sdk/transition_receipts.py",
    "harness/sdk/effect_adapters.py",
    "harness/sdk/effect_verifier.py",
    "harness/sdk/complete_verifier.py",
    "harness/sdk/operator_visibility.py",
    "harness/policies/consequence-policy.v1.json",
    "harness/policies/capability-map.v1.json",
    "scripts/automaton3-authority.py",
    "scripts/run-automaton3-tests.py",
    "scripts/validate-automaton3.py",
    "agents/coordinator.py",
    "sovereign-omega-v2/mcp-server/src/index.ts",
    "sovereign-omega-v2/mcp-server/test/automaton3-authority.mjs",
    "sovereign-omega-v2/python/tests/test_automaton3.py",
    "sovereign-omega-v2/python/tests/test_operator_visibility.py",
    "sovereign-omega-v2/python/tests/test_transition_receipts_pr1.py",
    "sovereign-omega-v2/python/tests/test_transition_receipts_cli_pr1.py",
    "sovereign-omega-v2/python/tests/test_effect_adapters_pr2.py",
    "sovereign-omega-v2/python/tests/test_effect_verifier_pr3.py",
    "sovereign-omega-v2/python/tests/test_complete_verifier_pr4.py",
    "sovereign-omega-v2/python/tests/test_complete_verifier_pr4_receipt_binding.py",
    "sovereign-omega-v2/python/tests/test_effect_chain_main_integration.py",
    "sovereign-omega-v2/python/tests/test_effect_chain_evidence_integration.py",
    "schemas/execution-identity-envelope.v1.schema.json",
    "schemas/transition-identity-envelope.v1.schema.json",
    "schemas/mutation-receipt.v1.schema.json",
    "schemas/decision-receipt.v1.schema.json",
    "schemas/execution-receipt.v1.schema.json",
    "schemas/effect-receipt.v1.schema.json",
    "schemas/effect-witness.v1.schema.json",
    "schemas/complete-verification-result.v1.schema.json",
    "schemas/event-envelope.v1.schema.json",
    "schemas/writer-lease.v1.schema.json",
    "docs/adr/ADR-0021-automaton-3-sovereign-execution.md",
    "docs/security/AUTOMATON3_THREAT_MODEL.md",
    "docs/operations/LAW_OF_SILENCE_V2.md",
    "docs/operations/BRANCH_RULESET_AUTOMATON3.md",
    "docs/claims.json",
    "docs/CLAIMS_LEDGER.md",
    ".github/workflows/automaton-3.yml",
)

REQUIRED_REPOSITORY_CONTROLS = (
    ".github/workflows/automaton-2.yml",
    ".github/workflows/experiment-admission.yml",
    ".github/workflows/osv-scanner.yml",
    ".github/workflows/integration-ledger.yml",
    ".github/workflows/ci.yml",
    "scripts/validate-claims.mjs",
    "scripts/integration_ledger.py",
)

EXPECTED_TEST_COUNT = 129
EXPECTED_PROOFLINE_SCOPE = "PR1_THROUGH_PR4_MAIN_INTEGRATION"
PR2_REQUIRED_ASSERTIONS = (
    "pr2_effect_adapter_protocol_asserted",
    "pr2_filesystem_effect_adapter_asserted",
    "pr2_independent_pre_post_observation_asserted",
    "pr2_adapter_bound_effect_evidence_production_asserted",
    "pr2_verify_effect_not_implemented_asserted",
    "pr2_authorization_artifact_effect_evidence_forbidden_asserted",
    "pr2_caller_post_state_effect_authority_forbidden_asserted",
    "pr2_verifier_policy_commitment_current_asserted",
    "pr2_complete_verification_unavailable_asserted",
    "pr2_atomic_admission_unavailable_asserted",
    "pr2_effect_bound_admission_unavailable_asserted",
    "pr2_effect_receipt_production_unavailable_asserted",
)
CURRENT_EFFECT_CHAIN_REQUIRED_ASSERTIONS = (
    "verify_effect_asserted",
    "effect_receipt_verifier_gated_asserted",
    "complete_verification_asserted",
    "complete_verification_receipt_binding_asserted",
    "complete_verification_authority_evidence_only_asserted",
    "effect_chain_security_guards_asserted",
    "concurrent_file_mutation_snapshot_proof_not_established_asserted",
    "atomic_admission_unavailable_asserted",
    "effect_bound_admission_unavailable_asserted",
    "production_admission_not_established_asserted",
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def file_record(path: Path) -> dict[str, Any]:
    data = path.read_bytes()
    return {
        "path": path.relative_to(ROOT).as_posix(),
        "sha256": sha256(data),
        "size_bytes": len(data),
    }


def evaluate(
    *,
    candidate_sha: str,
    expected_parent_sha: str,
    test_summary_path: Path,
    mcp_log_path: Path,
    require_oidc: bool,
) -> tuple[dict[str, Any], dict[str, Any]]:
    violations: list[str] = []
    if not SHA_RE.fullmatch(candidate_sha):
        violations.append("candidate_sha invalid")
    if not SHA_RE.fullmatch(expected_parent_sha):
        violations.append("expected_parent_sha invalid")

    files: list[dict[str, Any]] = []
    for rel in KEY_FILES:
        path = ROOT / rel
        if not path.is_file():
            violations.append(f"required file missing: {rel}")
        else:
            files.append(file_record(path))
    for rel in REQUIRED_REPOSITORY_CONTROLS:
        if not (ROOT / rel).is_file():
            violations.append(f"repository control missing: {rel}")

    try:
        policy_raw = json.loads(
            (ROOT / "harness/policies/consequence-policy.v1.json").read_text(encoding="utf-8")
        )
        classes = policy_raw["classes"]
        if sorted(classes) != ["D0", "D1", "D2", "D3", "D4"]:
            violations.append("consequence classes incomplete")
        for level in ("D2", "D3", "D4"):
            if classes[level].get("approval") != "EXPLICIT":
                violations.append(f"{level} does not require explicit approval")
        policy_root = sha256(
            canonical_bytes({"domain": "AEGIS_CONSEQUENCE_POLICY_V1", "value": classes})
        )
    except Exception as exc:
        violations.append(f"policy invalid: {type(exc).__name__}")
        policy_root = "0" * 64

    try:
        summary = json.loads(test_summary_path.read_text(encoding="utf-8"))
        if summary.get("schema_version") != "1.1.0":
            violations.append("Automaton-3 summary schema version mismatch")
        if summary.get("proofline_scope") != EXPECTED_PROOFLINE_SCOPE:
            violations.append("Automaton-3 proofline scope mismatch")
        if summary.get("return_code") != 0:
            violations.append("Automaton-3 tests failed")
        if summary.get("bypasses") != 0:
            violations.append("authority bypass detected")
        if summary.get("adaptive_attempts") != [1, 10, 100]:
            violations.append("adaptive attempt matrix incomplete")
        if summary.get("expected_test_count") != EXPECTED_TEST_COUNT:
            violations.append("Automaton-3 expected test count mismatch")
        if summary.get("actual_test_count") != EXPECTED_TEST_COUNT:
            violations.append("Automaton-3 actual test count incomplete")
        if summary.get("test_count_complete") is not True:
            violations.append("Automaton-3 per-file test count unavailable")
        if summary.get("test_count_matches_expected") is not True:
            violations.append("Automaton-3 actual test count mismatch")
        if summary.get("operator_visibility_asserted") is not True:
            violations.append("operator visibility invariant not asserted")
        if summary.get("state_preservation_asserted") is not True:
            violations.append("state preservation not asserted")
        if summary.get("external_side_effect_absence_asserted") is not True:
            violations.append("uncontrolled external side-effect absence not asserted")
        if summary.get("transition_binding_asserted") is not True:
            violations.append("transition binding not asserted")
        if summary.get("receipt_separation_asserted") is not True:
            violations.append("receipt separation not asserted")
        if summary.get("effect_receipt_schema_defined") is not True:
            violations.append("effect receipt schema not defined")
        if summary.get("generic_effect_receipt_production_forbidden_asserted") is not True:
            violations.append("generic effect receipt production is not forbidden")
        if summary.get("legacy_receipt_effect_evidence_forbidden_asserted") is not True:
            violations.append("legacy mutation receipt may satisfy effect evidence")
        if summary.get("legacy_fallback_forbidden_asserted") is not True:
            violations.append("legacy effect-evidence fallback not forbidden")
        if summary.get("effect_bound_admission_unavailable_asserted") is not True:
            violations.append("effect-bound admission availability exceeds PR-2 scope")
        for key in PR2_REQUIRED_ASSERTIONS:
            if summary.get(key) is not True:
                violations.append(f"PR-2 assertion missing or false: {key}")
        for key in CURRENT_EFFECT_CHAIN_REQUIRED_ASSERTIONS:
            if summary.get(key) is not True:
                violations.append(f"current effect-chain assertion missing or false: {key}")
        if summary.get("pr2_adapter_bound_effect_receipt_production_asserted") is True:
            violations.append("stale PR-2 pre-VerifyEffect receipt-production assertion survived")
        test_summary_root = summary.get("summary_root", "0" * 64)
    except Exception as exc:
        violations.append(f"test summary unavailable: {type(exc).__name__}")
        test_summary_root = "0" * 64

    try:
        mcp_log = mcp_log_path.read_text(encoding="utf-8")
        if "AUTOMATON3_MCP_PASS" not in mcp_log:
            violations.append("MCP fail-closed integration not proven")
        mcp_log_root = sha256(mcp_log.encode("utf-8"))
    except Exception as exc:
        violations.append(f"MCP log unavailable: {type(exc).__name__}")
        mcp_log_root = "0" * 64

    integration_expectations = (
        ("agents/coordinator.py", "authorize_from_environment"),
        ("sovereign-omega-v2/mcp-server/src/index.ts", "automaton3-authority.py"),
        ("harness/sdk/operator_visibility.py", "OPERATOR_VISIBILITY_CANNOT_BE_SUPPRESSED"),
        ("harness/sdk/authority_client.py", "decision_receipt_from_policy"),
        ("scripts/automaton3-authority.py", "decision_receipt_from_policy"),
        ("harness/sdk/transition_receipts.py", "DECISION_RECEIPT_V1"),
        ("harness/sdk/transition_receipts.py", "EFFECT_RECEIPT_V1"),
        ("harness/sdk/transition_receipts.py", "AEGIS_PR2_VERIFIER_POLICY_V2"),
        ("harness/sdk/transition_receipts.py", '"effect_evidence_production": "ADAPTER_BOUND_ONLY"'),
        ("harness/sdk/transition_receipts.py", '"verify_effect": "NOT_IMPLEMENTED"'),
        ("harness/sdk/transition_receipts.py", '"effect_receipt_production": "UNAVAILABLE"'),
        ("harness/sdk/effect_adapters.py", "FilesystemEffectAdapter"),
        ("harness/sdk/effect_adapters.py", "AEGIS_EFFECT_WITNESS_V1"),
        ("harness/sdk/effect_adapters.py", "does not implement VerifyEffect"),
        ("harness/sdk/effect_verifier.py", "AEGIS_EFFECT_VERIFICATION_RESULT_V1"),
        ("harness/sdk/effect_verifier.py", "issue_effect_receipt"),
        ("harness/sdk/complete_verifier.py", "AEGIS_COMPLETE_VERIFICATION_RESULT_V1"),
        ("harness/sdk/complete_verifier.py", "effect_bound_admission"),
        (".github/workflows/automaton-3.yml", "aegis / automaton-3"),
    )
    for rel, needle in integration_expectations:
        path = ROOT / rel
        if path.is_file() and needle not in path.read_text(encoding="utf-8"):
            violations.append(f"integration missing: {rel}:{needle}")

    for forbidden_symbol in (
        "_issue_adapter_bound_effect_receipt",
        "_EFFECT_RECEIPT_PRODUCER_CAPABILITY",
    ):
        path = ROOT / "harness/sdk/transition_receipts.py"
        if path.is_file() and forbidden_symbol in path.read_text(encoding="utf-8"):
            violations.append(f"EffectReceipt producer exists before VerifyEffect: {forbidden_symbol}")

    prohibited = re.compile(r"fail[- ]open|temporary bypass|silent fallback", re.IGNORECASE)
    for rel in (
        "harness/sdk/sovereign_execution.py",
        "harness/sdk/authority_client.py",
        "harness/sdk/transition_receipts.py",
        "harness/sdk/effect_adapters.py",
        "harness/sdk/effect_verifier.py",
        "harness/sdk/complete_verifier.py",
        "harness/sdk/operator_visibility.py",
        "agents/coordinator.py",
        "sovereign-omega-v2/mcp-server/src/index.ts",
    ):
        path = ROOT / rel
        if path.is_file() and prohibited.search(path.read_text(encoding="utf-8")):
            violations.append(f"prohibited bypass language in executable path: {rel}")

    if require_oidc and not (
        os.environ.get("GITHUB_ACTIONS") == "true"
        and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_URL")
        and os.environ.get("ACTIONS_ID_TOKEN_REQUEST_TOKEN")
    ):
        violations.append("OIDC execution identity unavailable")

    files.sort(key=lambda item: item["path"])
    candidate_manifest = {
        "schema_version": "1.1.0",
        "manifest_kind": "AEGIS_AUTOMATON3_CANDIDATE_MANIFEST_V1",
        "repository": "Aegis-Omega/AEGIS-OMEGA",
        "candidate_sha": candidate_sha,
        "expected_parent_sha": expected_parent_sha,
        "policy_root": policy_root,
        "test_summary_root": test_summary_root,
        "mcp_log_root": mcp_log_root,
        "admission_scope": "REPOSITORY_CANDIDATE_VALIDATION_ONLY",
        "proofline_scope": EXPECTED_PROOFLINE_SCOPE,
        "effect_observation_scope": "REFERENCE_FILESYSTEM_PROCESS_LOCAL_ONLY",
        "effect_evidence_production": "ADAPTER_ISSUED_PROCESS_LOCAL_REFERENCE",
        "effect_witness_issuance_scope": "PROCESS_LOCAL_OBJECT_IDENTITY_ONLY",
        "adapter_scope_binding": "PROCESS_LOCAL_ISSUING_INSTANCE_ONLY",
        "filesystem_stability_guard": "DEV_INO_SIZE_MTIME_CTIME_DOUBLE_FSTAT_REFERENCE",
        "concurrent_file_mutation_snapshot_proof": "NOT_ESTABLISHED",
        "cross_process_witness_replay": "NOT_SUPPORTED",
        "verify_effect": "IMPLEMENTED_VERSION_BOUND_REFERENCE",
        "effect_receipt_production": "VERIFY_EFFECT_TRUE_GATED_REFERENCE",
        "verifier_policy_scope": "PR3_CURRENT_POLICY_COMMITMENT_REQUIRED",
        "complete_verification": "IMPLEMENTED_EXACT_BUNDLE_REFERENCE",
        "complete_verification_authority": "EVIDENCE_ONLY_NOT_ADMISSION",
        "atomic_admission": "NOT_IMPLEMENTED",
        "effect_bound_admission": "UNAVAILABLE",
        "production_admission": "NOT_ESTABLISHED",
        "files": files,
    }
    candidate_manifest["candidate_manifest_root"] = sha256(canonical_bytes(candidate_manifest))

    violations = sorted(set(violations))
    body = {
        "schema_version": "1.1.0",
        "receipt_kind": "AEGIS_AUTOMATON3_ADMISSION_RECEIPT_V1",
        "admission_scope": "REPOSITORY_CANDIDATE_ADMISSION_NOT_EFFECT_BOUND_STATE_ADMISSION",
        "candidate_sha": candidate_sha,
        "expected_parent_sha": expected_parent_sha,
        "candidate_manifest_root": candidate_manifest["candidate_manifest_root"],
        "policy_root": policy_root,
        "test_summary_root": test_summary_root,
        "mcp_log_root": mcp_log_root,
        "proofline_scope": EXPECTED_PROOFLINE_SCOPE,
        "effect_observation_scope": "REFERENCE_FILESYSTEM_PROCESS_LOCAL_ONLY",
        "effect_evidence_production": "ADAPTER_ISSUED_PROCESS_LOCAL_REFERENCE",
        "effect_witness_issuance_scope": "PROCESS_LOCAL_OBJECT_IDENTITY_ONLY",
        "adapter_scope_binding": "PROCESS_LOCAL_ISSUING_INSTANCE_ONLY",
        "filesystem_stability_guard": "DEV_INO_SIZE_MTIME_CTIME_DOUBLE_FSTAT_REFERENCE",
        "concurrent_file_mutation_snapshot_proof": "NOT_ESTABLISHED",
        "cross_process_witness_replay": "NOT_SUPPORTED",
        "verify_effect": "IMPLEMENTED_VERSION_BOUND_REFERENCE",
        "effect_receipt_production": "VERIFY_EFFECT_TRUE_GATED_REFERENCE",
        "verifier_policy_scope": "PR3_CURRENT_POLICY_COMMITMENT_REQUIRED",
        "complete_verification": "IMPLEMENTED_EXACT_BUNDLE_REFERENCE",
        "complete_verification_authority": "EVIDENCE_ONLY_NOT_ADMISSION",
        "atomic_admission": "NOT_IMPLEMENTED",
        "effect_bound_admission": "UNAVAILABLE",
        "production_admission": "NOT_ESTABLISHED",
        "signature_mode": (
            "GITHUB_OIDC_ATTESTATION"
            if require_oidc
            else "DETERMINISTIC_VALIDATION_ONLY"
        ),
        "outcome": "ADMITTED" if not violations else "DENIED",
        "violation_count": len(violations),
        "violations": violations,
    }
    receipt = dict(body)
    receipt["receipt_hash"] = sha256(
        canonical_bytes({"domain": "AEGIS_AUTOMATON3_ADMISSION_RECEIPT_V1", "receipt": body})
    )
    return receipt, candidate_manifest


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--candidate-sha", required=True)
    parser.add_argument("--expected-parent-sha", required=True)
    parser.add_argument("--test-summary", required=True)
    parser.add_argument("--mcp-log", required=True)
    parser.add_argument("--receipt-output", required=True)
    parser.add_argument("--manifest-output", required=True)
    parser.add_argument("--require-oidc", action="store_true")
    args = parser.parse_args()
    receipt, manifest = evaluate(
        candidate_sha=args.candidate_sha,
        expected_parent_sha=args.expected_parent_sha,
        test_summary_path=Path(args.test_summary),
        mcp_log_path=Path(args.mcp_log),
        require_oidc=args.require_oidc,
    )
    Path(args.receipt_output).write_text(
        json.dumps(receipt, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    Path(args.manifest_output).write_text(
        json.dumps(manifest, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(receipt, indent=2, sort_keys=True))
    return 0 if receipt["outcome"] == "ADMITTED" else 3


if __name__ == "__main__":
    raise SystemExit(main())
