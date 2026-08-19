"""Transition identity and epistemically separated receipt types.

PR-1 establishes receipt separation and safe incompleteness. PR-2 adds only a
module-private adapter-bound EffectReceipt issuance path. Complete transition
verification and authoritative admission remain unavailable.
"""
from __future__ import annotations

import re
from dataclasses import asdict, dataclass, is_dataclass
from typing import Any, Mapping

from harness.sdk.sovereign_execution import SCHEMA_VERSION, canonical_hash

DECISION_RECEIPT_KIND = "DECISION_RECEIPT_V1"
EXECUTION_RECEIPT_KIND = "EXECUTION_RECEIPT_V1"
EFFECT_RECEIPT_KIND = "EFFECT_RECEIPT_V1"

PERMIT = "PERMIT"
DENY = "DENY"
DEFER = "DEFER"
DECISION_OUTCOMES = (PERMIT, DENY, DEFER)

EXECUTION_SUCCEEDED = "SUCCEEDED"
EXECUTION_FAILED = "FAILED"
EXECUTION_CANCELLED = "CANCELLED"
EXECUTION_OUTCOMES = (EXECUTION_SUCCEEDED, EXECUTION_FAILED, EXECUTION_CANCELLED)

AUTHORIZED = "AUTHORIZED"
DENIED_STATE = "DENIED"
WAITING = "WAITING"

SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
GIT_RE = re.compile(r"^[0-9a-f]{40,64}$")
SAFE_ID_RE = re.compile(r"^[A-Za-z0-9._:/@+#=-]+$")

PR1_VERIFIER_POLICY = {
    "policy_id": "AEGIS_PR1_VERIFIER_POLICY_V1",
    "safe_incompleteness": True,
    "required_semantics": ["V_decision", "V_binding", "V_effect"],
    "effect_evidence_required": True,
    "effect_receipt_production": "UNAVAILABLE",
}

PR1_ADMISSION_POLICY = {
    "policy_id": "AEGIS_PR1_ADMISSION_POLICY_V1",
    "safe_incompleteness": True,
    "effect_bound_admission": "UNAVAILABLE",
    "legacy_fallback": "FORBIDDEN",
    "defer_authority": "NOT_ADMITTED",
}


class TransitionReceiptError(ValueError):
    """Raised when a transition or receipt violates its nominal contract."""


def _require_hash(name: str, value: str) -> None:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise TransitionReceiptError(f"{name}:INVALID_SHA256")


def _require_git(name: str, value: str) -> None:
    if not isinstance(value, str) or not GIT_RE.fullmatch(value):
        raise TransitionReceiptError(f"{name}:INVALID_GIT_OBJECT")


def _require_id(name: str, value: str) -> None:
    if not isinstance(value, str) or not value or not SAFE_ID_RE.fullmatch(value):
        raise TransitionReceiptError(f"{name}:INVALID_ID")


@dataclass(frozen=True)
class TransitionIdentity:
    """Canonical transition binding whose root is the TransitionID tau."""

    schema_version: str
    source_commit: str
    pre_state_commitment: str
    identity_root: str
    delegation_commitment: str
    capability_commitment: str
    action_digest: str
    deterministic_nonce: str
    fence_commitment: str
    verifier_policy_commitment: str
    admission_policy_commitment: str

    def validate(self) -> None:
        if self.schema_version != SCHEMA_VERSION:
            raise TransitionReceiptError("TRANSITION_SCHEMA_UNSUPPORTED")
        _require_git("source_commit", self.source_commit)
        for name in (
            "pre_state_commitment",
            "identity_root",
            "delegation_commitment",
            "capability_commitment",
            "action_digest",
            "fence_commitment",
            "verifier_policy_commitment",
            "admission_policy_commitment",
        ):
            _require_hash(name, getattr(self, name))
        _require_id("deterministic_nonce", self.deterministic_nonce)

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_TRANSITION_ID_V1", asdict(self))


@dataclass(frozen=True)
class DecisionReceipt:
    receipt_kind: str
    transition_id: str
    decision_outcome: str
    policy_decision_root: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.receipt_kind != DECISION_RECEIPT_KIND:
            raise ValueError("DECISION_RECEIPT_KIND_MISMATCH")
        _require_hash("transition_id", self.transition_id)
        _require_hash("policy_decision_root", self.policy_decision_root)
        if self.decision_outcome not in DECISION_OUTCOMES:
            raise TransitionReceiptError("DECISION_OUTCOME_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_DECISION_RECEIPT_V1", asdict(self))


@dataclass(frozen=True)
class ExecutionReceipt:
    receipt_kind: str
    transition_id: str
    execution_instance_id: str
    outcome: str
    result_digest: str

    def __post_init__(self) -> None:
        self.validate()

    def validate(self) -> None:
        if self.receipt_kind != EXECUTION_RECEIPT_KIND:
            raise ValueError("EXECUTION_RECEIPT_KIND_MISMATCH")
        _require_hash("transition_id", self.transition_id)
        _require_id("execution_instance_id", self.execution_instance_id)
        _require_hash("result_digest", self.result_digest)
        if self.outcome not in EXECUTION_OUTCOMES:
            raise TransitionReceiptError("EXECUTION_OUTCOME_INVALID")

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EXECUTION_RECEIPT_V1", asdict(self))


@dataclass(frozen=True, init=False)
class EffectReceipt:
    """Effect evidence target type; direct public construction remains forbidden."""

    receipt_kind: str
    transition_id: str
    execution_instance_id: str
    effect_witness_digest: str
    pre_state_commitment: str
    post_state_commitment: str
    observation_provenance: str
    adapter_identity: str
    adapter_version: str

    def validate(self) -> None:
        if getattr(self, "receipt_kind", None) != EFFECT_RECEIPT_KIND:
            raise TransitionReceiptError("EFFECT_RECEIPT_KIND_MISMATCH")
        for name in (
            "transition_id",
            "effect_witness_digest",
            "pre_state_commitment",
            "post_state_commitment",
            "observation_provenance",
        ):
            _require_hash(name, getattr(self, name))
        _require_id("execution_instance_id", self.execution_instance_id)
        _require_id("adapter_identity", self.adapter_identity)
        _require_id("adapter_version", self.adapter_version)

    @property
    def root(self) -> str:
        self.validate()
        return canonical_hash("AEGIS_EFFECT_RECEIPT_V1", asdict(self))


# PR-2 canonical adapter issuance capability. This is deliberately private and is
# not an authorization primitive; it prevents a generic public constructor from
# becoming the canonical EffectReceipt path. Python module privacy is not a crypto
# boundary, so downstream verification must still validate witness provenance.
_EFFECT_RECEIPT_PRODUCER_CAPABILITY = object()


def _issue_adapter_bound_effect_receipt(*, witness: Any, producer_capability: object) -> EffectReceipt:
    if producer_capability is not _EFFECT_RECEIPT_PRODUCER_CAPABILITY:
        raise TransitionReceiptError("EFFECT_RECEIPT_PRODUCER_UNAUTHORIZED")

    receipt = object.__new__(EffectReceipt)
    values = {
        "receipt_kind": EFFECT_RECEIPT_KIND,
        "transition_id": witness.transition_id,
        "execution_instance_id": witness.execution_instance_id,
        "effect_witness_digest": witness.root,
        "pre_state_commitment": witness.observed_pre_state_commitment,
        "post_state_commitment": witness.observed_post_state_commitment,
        "observation_provenance": canonical_hash(
            "AEGIS_EFFECT_OBSERVATION_BUNDLE_V1",
            {
                "pre": witness.pre_observation_provenance,
                "post": witness.post_observation_provenance,
            },
        ),
        "adapter_identity": witness.adapter_identity,
        "adapter_version": witness.adapter_version,
    }
    for name, value in values.items():
        object.__setattr__(receipt, name, value)
    receipt.validate()
    return receipt


def decision_satisfies_authority(outcome: str) -> bool:
    """Only PERMIT carries decision authority; DENY and DEFER do not."""

    return outcome == PERMIT


def decision_execution_allowed(outcome: str) -> bool:
    return decision_satisfies_authority(outcome)


def decision_route(outcome: str) -> str:
    if outcome == PERMIT:
        return AUTHORIZED
    if outcome == DENY:
        return DENIED_STATE
    if outcome == DEFER:
        return WAITING
    raise TransitionReceiptError("DECISION_OUTCOME_INVALID")


def verify_transition_binding(transition: TransitionIdentity, *receipts: Any) -> bool:
    """V_binding: every receipt must carry the exact recomputed tau."""

    try:
        expected = transition.root
        if not receipts:
            return False
        for receipt in receipts:
            validate = getattr(receipt, "validate", None)
            if not callable(validate):
                return False
            validate()
            if getattr(receipt, "transition_id", None) != expected:
                return False
        return True
    except (TransitionReceiptError, ValueError, TypeError, AttributeError):
        return False


def accept_effect_evidence(_artifact: Any) -> bool:
    """Complete V_effect acceptance remains unavailable in PR-2.

    Adapter-bound EffectReceipt production is now possible, but this function is
    deliberately false for every artifact because PR-2 does not implement the
    complete verifier or authoritative admission path.
    """

    return False


def _plain(value: Any) -> Any:
    if value is None:
        return None
    if is_dataclass(value):
        return asdict(value)
    if isinstance(value, Mapping):
        return dict(value)
    return value


def delegation_commitment(approval: Any | None) -> str:
    return canonical_hash(
        "AEGIS_DELEGATION_COMMITMENT_V1",
        {"state": "NONE"} if approval is None else {"state": "BOUND", "approval": _plain(approval)},
    )


def capability_commitment(*, requested_capability: str, registry_root: str) -> str:
    _require_id("requested_capability", requested_capability)
    _require_hash("registry_root", registry_root)
    return canonical_hash(
        "AEGIS_CAPABILITY_COMMITMENT_V1",
        {"requested_capability": requested_capability, "registry_root": registry_root},
    )


def fence_commitment(fence_token: str | None) -> str:
    return canonical_hash(
        "AEGIS_TRANSITION_FENCE_COMMITMENT_V1",
        {"fence_token": fence_token if fence_token else "NONE"},
    )


def verifier_policy_commitment() -> str:
    return canonical_hash("AEGIS_VERIFIER_POLICY_COMMITMENT_V1", PR1_VERIFIER_POLICY)


def admission_policy_commitment() -> str:
    return canonical_hash("AEGIS_ADMISSION_POLICY_COMMITMENT_V1", PR1_ADMISSION_POLICY)


def build_transition_identity(
    *,
    source_commit: str,
    pre_state_commitment: str,
    identity_root: str,
    approval: Any | None,
    requested_capability: str,
    registry_root: str,
    action_digest: str,
    deterministic_nonce: str,
    fence_token: str | None = None,
) -> TransitionIdentity:
    return TransitionIdentity(
        schema_version=SCHEMA_VERSION,
        source_commit=source_commit,
        pre_state_commitment=pre_state_commitment,
        identity_root=identity_root,
        delegation_commitment=delegation_commitment(approval),
        capability_commitment=capability_commitment(
            requested_capability=requested_capability,
            registry_root=registry_root,
        ),
        action_digest=action_digest,
        deterministic_nonce=deterministic_nonce,
        fence_commitment=fence_commitment(fence_token),
        verifier_policy_commitment=verifier_policy_commitment(),
        admission_policy_commitment=admission_policy_commitment(),
    )


def decision_receipt_from_policy(*, transition: TransitionIdentity, decision: Any) -> DecisionReceipt:
    legacy_outcome = getattr(decision, "outcome", None)
    if legacy_outcome == "ADMITTED":
        outcome = PERMIT
    elif legacy_outcome == "DENIED":
        outcome = DENY
    else:
        outcome = DEFER
    return DecisionReceipt(
        receipt_kind=DECISION_RECEIPT_KIND,
        transition_id=transition.root,
        decision_outcome=outcome,
        policy_decision_root=getattr(decision, "decision_root"),
    )
