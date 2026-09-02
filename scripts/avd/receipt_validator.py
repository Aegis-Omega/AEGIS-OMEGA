from __future__ import annotations

import re
from typing import Any

from .crypto_util import compute_receipt_digest
from .oracle_evaluator import OracleEvaluationError, OracleEvaluationV1


class ReceiptValidationError(RuntimeError):
    pass


_HEX40 = re.compile(r"^[0-9a-f]{40}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_TOP_LEVEL = {
    "protocol_version", "authority_class", "execution_mode", "trial_id", "arm_id",
    "anchor", "submission", "commitment_digests", "resource_telemetry",
    "oracle_falsifier_outcomes", "isolation_attestation", "gate_outcome", "receipt_digest",
}
_ARMS = {"ARM_A_HUMAN", "ARM_B_AEDR_AUTONOMOUS", "ARM_C_MONOLITHIC_ORACLE"}
_GATES = {"PASS", "FAIL", "REJECTED_VERIFIER_COMPROMISE", "QUARANTINED"}


def _exact_keys(obj: Any, keys: set[str], label: str) -> dict[str, Any]:
    if not isinstance(obj, dict) or set(obj) != keys:
        raise ReceiptValidationError(f"{label}_SCHEMA_MISMATCH")
    return obj


def _nonnegative_int(value: Any, label: str) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ReceiptValidationError(f"INVALID_NONNEGATIVE_INTEGER:{label}")


def validate_trial_receipt(receipt: dict[str, Any]) -> None:
    _exact_keys(receipt, _TOP_LEVEL, "TOP_LEVEL")
    if receipt["protocol_version"] != "AVD_PROTOCOL_V1":
        raise ReceiptValidationError("PROTOCOL_VERSION_MISMATCH")
    if receipt["authority_class"] != "NONE":
        raise ReceiptValidationError("AUTHORITY_CLASS_NOT_NONE")
    if receipt["execution_mode"] != "BENCHMARK_MEASUREMENT_ONLY":
        raise ReceiptValidationError("EXECUTION_MODE_INVALID")
    if receipt["arm_id"] not in _ARMS:
        raise ReceiptValidationError("ARM_ID_INVALID")
    if receipt["gate_outcome"] not in _GATES:
        raise ReceiptValidationError("GATE_OUTCOME_INVALID")

    anchor = _exact_keys(receipt["anchor"], {"commit_sha", "tree_sha", "pr_base_sha", "git_parent_sha"}, "ANCHOR")
    for key, value in anchor.items():
        if not isinstance(value, str) or not _HEX40.fullmatch(value):
            raise ReceiptValidationError(f"INVALID_ANCHOR_SHA:{key}")

    submission = _exact_keys(receipt["submission"], {"patch_sha256", "result_tree_sha256"}, "SUBMISSION")
    commitments = _exact_keys(receipt["commitment_digests"], {"h_problem", "h_verifier", "h_oracle"}, "COMMITMENTS")
    for group, values in (("SUBMISSION", submission), ("COMMITMENT", commitments)):
        for key, value in values.items():
            if not isinstance(value, str) or not _HEX64.fullmatch(value):
                raise ReceiptValidationError(f"INVALID_{group}_DIGEST:{key}")

    telemetry_keys = {
        "wall_nanoseconds", "active_nanoseconds", "human_active_nanoseconds", "machine_active_nanoseconds",
        "cpu_user_microseconds", "cpu_system_microseconds", "input_tokens", "output_tokens", "tool_actions",
        "model_calls", "gpu_seconds", "cached_tokens", "api_cost_usd",
    }
    telemetry = _exact_keys(receipt["resource_telemetry"], telemetry_keys, "RESOURCE_TELEMETRY")
    for key in telemetry_keys - {"gpu_seconds", "cached_tokens", "api_cost_usd"}:
        _nonnegative_int(telemetry[key], key)
    if telemetry["gpu_seconds"] != "UNAVAILABLE" or telemetry["api_cost_usd"] != "UNAVAILABLE":
        raise ReceiptValidationError("UNAVAILABLE_TELEMETRY_CONTRACT_VIOLATION")
    if telemetry["cached_tokens"] != "UNAVAILABLE":
        _nonnegative_int(telemetry["cached_tokens"], "cached_tokens")

    isolation = _exact_keys(
        receipt["isolation_attestation"],
        {"workspace_git_metadata_absent", "candidate_network_mode", "fresh_clean_room_context", "external_repo_tools_disabled", "future_solution_absent_at_start"},
        "ISOLATION",
    )
    required_true = (
        isolation["workspace_git_metadata_absent"], isolation["fresh_clean_room_context"],
        isolation["external_repo_tools_disabled"], isolation["future_solution_absent_at_start"],
    )
    if any(value is not True for value in required_true) or isolation["candidate_network_mode"] != "NONE":
        raise ReceiptValidationError("ISOLATION_ATTESTATION_INVALID")

    try:
        OracleEvaluationV1.from_results(receipt["oracle_falsifier_outcomes"])
    except OracleEvaluationError as exc:
        raise ReceiptValidationError(str(exc)) from exc

    declared = receipt["receipt_digest"]
    if not isinstance(declared, str) or not _HEX64.fullmatch(declared):
        raise ReceiptValidationError("RECEIPT_DIGEST_INVALID")
    payload = dict(receipt)
    payload.pop("receipt_digest")
    computed = compute_receipt_digest(payload)
    if computed != declared:
        raise ReceiptValidationError("RECEIPT_DIGEST_MISMATCH")
