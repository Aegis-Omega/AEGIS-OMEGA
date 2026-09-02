from __future__ import annotations

from typing import Any

from .oracle_evaluator import OracleEvaluationV1


class TrialExecutionError(RuntimeError):
    pass


class AVDTrialRunner:
    """Pure gate logic for AVD trials.

    This object cannot grant authority or perform canonical admission. It maps
    verifier/oracle/isolation evidence to benchmark measurement outcomes only.
    Actual candidate execution and fixture mutation remain separate components.
    """

    AUTHORITY_CLASS = "NONE"
    EXECUTION_MODE = "BENCHMARK_MEASUREMENT_ONLY"

    @staticmethod
    def map_commitment_failure_to_outcome(reason: str) -> str:
        if reason.startswith(("H_P_MISMATCH", "H_V_MISMATCH", "H_O_MISMATCH", "COMMITMENT_DRIFT")):
            return "REJECTED_VERIFIER_COMPROMISE"
        return "QUARANTINED"

    def determine_gate_outcome(
        self,
        *,
        verifier_passed: bool,
        oracle_evaluation: OracleEvaluationV1,
        isolation_attestation: dict[str, Any],
        os_network_none_attested: bool,
    ) -> str:
        required_keys = {
            "workspace_git_metadata_absent",
            "candidate_network_mode",
            "fresh_clean_room_context",
            "external_repo_tools_disabled",
            "future_solution_absent_at_start",
        }
        if set(isolation_attestation) != required_keys:
            raise TrialExecutionError("ISOLATION_ATTESTATION_SCHEMA_MISMATCH")
        if isolation_attestation["candidate_network_mode"] != "NONE":
            raise TrialExecutionError("CANDIDATE_NETWORK_MODE_NOT_NONE")
        for key in required_keys - {"candidate_network_mode"}:
            if isolation_attestation[key] is not True:
                raise TrialExecutionError(f"ISOLATION_INVARIANT_FAILED:{key}")
        if not os_network_none_attested:
            raise TrialExecutionError("NETWORK_NONE_ATTESTATION_REQUIRED")
        if not verifier_passed:
            return "FAIL"
        if not oracle_evaluation.all_required_passed:
            return "FAIL"
        return "PASS"
