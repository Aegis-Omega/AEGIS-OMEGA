"""Fail-closed admission preflight for the Tameion Arc Testnet capability.

This module deliberately does NOT mint authority. It evaluates whether the
minimum evidence needed to even construct an AEGIS AuthorityEvaluator request is
present. Missing hosted/local execution evidence, missing OpenMeter observation,
or missing operator approval keeps the capability NOT_ADMITTED.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass

from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError, canonical_hash

REQUIRED_VALIDATED_RUNS = 3
CAPABILITY = "arc.testnet.transfer"
AUTHORITY_DOMAIN = "treasury.testnet"
ACTION_CLASS = "D3"
TOOL = "arc-plan"


@dataclass(frozen=True)
class TameionAdmissionEvidence:
    schema_version: str
    source_commit: str
    validated_runs: int
    openmeter_observation_root: str | None
    operator_approval_root: str | None
    hosted_replay_executed: bool
    runner_pre_step_failures: int
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TAMEION_ADMISSION_SCHEMA_UNSUPPORTED")
        if not isinstance(self.source_commit, str) or len(self.source_commit) not in (40, 64):
            raise SovereignExecutionError("TAMEION_ADMISSION_SOURCE_COMMIT_INVALID")
        try:
            int(self.source_commit, 16)
        except ValueError as exc:
            raise SovereignExecutionError("TAMEION_ADMISSION_SOURCE_COMMIT_INVALID") from exc
        if (
            not isinstance(self.validated_runs, int)
            or isinstance(self.validated_runs, bool)
            or self.validated_runs < 0
        ):
            raise SovereignExecutionError("TAMEION_ADMISSION_RUN_COUNT_INVALID")
        for name in ("openmeter_observation_root", "operator_approval_root"):
            value = getattr(self, name)
            if value is not None:
                if not isinstance(value, str) or len(value) != 64:
                    raise SovereignExecutionError(f"{name}:INVALID_SHA256")
                try:
                    int(value, 16)
                except ValueError as exc:
                    raise SovereignExecutionError(f"{name}:INVALID_SHA256") from exc
        if not isinstance(self.hosted_replay_executed, bool):
            raise SovereignExecutionError("TAMEION_ADMISSION_HOSTED_REPLAY_INVALID")
        if (
            not isinstance(self.runner_pre_step_failures, int)
            or isinstance(self.runner_pre_step_failures, bool)
            or self.runner_pre_step_failures < 0
        ):
            raise SovereignExecutionError("TAMEION_ADMISSION_RUNNER_FAILURE_COUNT_INVALID")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("TAMEION_ADMISSION_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_ADMISSION_EVIDENCE_V1", asdict(self))


@dataclass(frozen=True)
class TameionAdmissionPreflight:
    schema_version: str
    capability: str
    authority_domain: str
    action_class: str
    tool: str
    evidence_root: str
    outcome: str
    denial_codes: tuple[str, ...]
    authority_effect: str = "NONE"

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_SCHEMA_UNSUPPORTED")
        if self.capability != CAPABILITY:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_CAPABILITY_INVALID")
        if self.authority_domain != AUTHORITY_DOMAIN:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_DOMAIN_INVALID")
        if self.action_class != ACTION_CLASS:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_ACTION_CLASS_INVALID")
        if self.tool != TOOL:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_TOOL_INVALID")
        if not isinstance(self.evidence_root, str) or len(self.evidence_root) != 64:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_EVIDENCE_ROOT_INVALID")
        if self.outcome not in ("READY_FOR_AUTHORITY_EVALUATION", "NOT_ADMITTED"):
            raise SovereignExecutionError("TAMEION_PREFLIGHT_OUTCOME_INVALID")
        if self.outcome == "READY_FOR_AUTHORITY_EVALUATION" and self.denial_codes:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_READY_WITH_DENIALS")
        if self.outcome == "NOT_ADMITTED" and not self.denial_codes:
            raise SovereignExecutionError("TAMEION_PREFLIGHT_DENIED_WITHOUT_CAUSE")
        if self.authority_effect != "NONE":
            raise SovereignExecutionError("TAMEION_PREFLIGHT_AUTHORITY_EFFECT_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TAMEION_ADMISSION_PREFLIGHT_V1", asdict(self))


def evaluate_tameion_admission_preflight(
    evidence: TameionAdmissionEvidence,
) -> TameionAdmissionPreflight:
    evidence.validate()
    reasons: list[str] = []

    if evidence.validated_runs < REQUIRED_VALIDATED_RUNS:
        reasons.append("INSUFFICIENT_VALIDATED_RUNS")
    if evidence.openmeter_observation_root is None:
        reasons.append("OPENMETER_OBSERVATION_MISSING")
    if evidence.operator_approval_root is None:
        reasons.append("OPERATOR_APPROVAL_MISSING")
    if not evidence.hosted_replay_executed:
        reasons.append("HOSTED_REPLAY_NOT_EXECUTED")
    if evidence.runner_pre_step_failures > 0:
        reasons.append("RUNNER_PRE_STEP_FAILURE_OBSERVED")

    reasons = sorted(set(reasons))
    outcome = "READY_FOR_AUTHORITY_EVALUATION" if not reasons else "NOT_ADMITTED"
    preflight = TameionAdmissionPreflight(
        schema_version=SCHEMA_VERSION,
        capability=CAPABILITY,
        authority_domain=AUTHORITY_DOMAIN,
        action_class=ACTION_CLASS,
        tool=TOOL,
        evidence_root=evidence.root,
        outcome=outcome,
        denial_codes=tuple(reasons),
    )
    preflight.validate()
    return preflight
