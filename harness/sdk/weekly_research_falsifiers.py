"""Research-triggered falsifiers for AEGIS boundary properties.

This module does not reopen or expand the frozen UCI research/property scope.
It encodes adversarial reference checks at already-declared boundaries:

- delegated authority contracts under composition,
- decision/effect state freshness,
- memory authority non-amplification and non-revival,
- reconstructible heritage versus copied-skill replication,
- joint-failure evidence before redundancy claims.

The contracts are deliberately narrow. Passing them is implementation evidence
for these specific falsifiers, not a universal security, AGI, or truth claim.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from typing import Any, Iterable, Mapping, Sequence

PERMIT = "PERMIT"
DENY = "DENY"
REVERIFY = "REVERIFY"
ACTIVE = "ACTIVE"
RETRACTED = "RETRACTED"
TRUE_HERITAGE = "TRUE_HERITAGE"
REPLICATION_ONLY = "REPLICATION_ONLY"
INDEPENDENCE_NOT_ESTABLISHED = "INDEPENDENCE_NOT_ESTABLISHED"
JOINT_EVIDENCE_PRESENT = "JOINT_EVIDENCE_PRESENT"

TIER_RANK = {"T2": 0, "T1": 1, "T0": 2}


class BoundaryFalsifierError(ValueError):
    """Stable fail-closed error with a machine-readable code."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _root(domain: str, value: Any) -> str:
    return hashlib.sha256(domain.encode("ascii") + b"\x00" + _canonical(value)).hexdigest()


def _require_nonnegative(name: str, value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise BoundaryFalsifierError(f"{name}:INVALID_NONNEGATIVE_INTEGER")


def _require_tier(tier: str) -> None:
    if tier not in TIER_RANK:
        raise BoundaryFalsifierError("EPISTEMIC_TIER_UNSUPPORTED")


# ---------------------------------------------------------------------------
# 1. Authorization composition / delegation contraction
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DelegatedAuthorityV1:
    principal: str
    task_id: str
    intent_digest: str
    scopes: tuple[str, ...]
    remaining_action_budget: int
    remaining_compute_budget: int
    parent_root: str | None = None

    def __post_init__(self) -> None:
        if not self.principal or not self.task_id or not self.intent_digest:
            raise BoundaryFalsifierError("DELEGATION_IDENTITY_MISSING")
        if not self.scopes or any(not scope for scope in self.scopes):
            raise BoundaryFalsifierError("DELEGATION_SCOPE_EMPTY")
        if len(set(self.scopes)) != len(self.scopes):
            raise BoundaryFalsifierError("DELEGATION_SCOPE_DUPLICATE")
        _require_nonnegative("remaining_action_budget", self.remaining_action_budget)
        _require_nonnegative("remaining_compute_budget", self.remaining_compute_budget)

    @property
    def root(self) -> str:
        return _root("AEGIS_DELEGATED_AUTHORITY_V1", asdict(self))


def delegate_authority(
    parent: DelegatedAuthorityV1,
    *,
    child_principal: str,
    scopes: Iterable[str],
    action_budget: int,
    compute_budget: int,
    task_id: str | None = None,
    intent_digest: str | None = None,
) -> DelegatedAuthorityV1:
    """Create a child grant only if authority monotonically contracts."""

    child_scopes = tuple(sorted(set(scopes)))
    child_task = parent.task_id if task_id is None else task_id
    child_intent = parent.intent_digest if intent_digest is None else intent_digest
    if child_task != parent.task_id:
        raise BoundaryFalsifierError("TASK_BINDING_CHANGED")
    if child_intent != parent.intent_digest:
        raise BoundaryFalsifierError("INTENT_BINDING_CHANGED")
    if not set(child_scopes).issubset(set(parent.scopes)):
        raise BoundaryFalsifierError("SCOPE_EXPANSION_FORBIDDEN")
    if action_budget > parent.remaining_action_budget:
        raise BoundaryFalsifierError("ACTION_BUDGET_EXPANSION_FORBIDDEN")
    if compute_budget > parent.remaining_compute_budget:
        raise BoundaryFalsifierError("COMPUTE_BUDGET_EXPANSION_FORBIDDEN")
    return DelegatedAuthorityV1(
        principal=child_principal,
        task_id=child_task,
        intent_digest=child_intent,
        scopes=child_scopes,
        remaining_action_budget=action_budget,
        remaining_compute_budget=compute_budget,
        parent_root=parent.root,
    )


@dataclass(frozen=True)
class AuthorizedActionV1:
    action_id: str
    required_scope: str
    compute_cost: int
    effect_tags: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if not self.action_id or not self.required_scope:
            raise BoundaryFalsifierError("ACTION_IDENTITY_MISSING")
        _require_nonnegative("compute_cost", self.compute_cost)


@dataclass(frozen=True)
class CompositionDecisionV1:
    outcome: str
    denial_code: str | None
    consumed_actions: int
    consumed_compute: int
    accumulated_effect_tags: tuple[str, ...]
    authority_root: str


def authorize_composition(
    authority: DelegatedAuthorityV1,
    actions: Sequence[AuthorizedActionV1],
    *,
    forbidden_effect_compositions: Iterable[frozenset[str]] = (),
) -> CompositionDecisionV1:
    """Authorize the sequence, not merely each request in isolation."""

    scopes = set(authority.scopes)
    consumed_compute = 0
    tags: set[str] = set()
    forbidden = tuple(forbidden_effect_compositions)

    for index, action in enumerate(actions, start=1):
        if action.required_scope not in scopes:
            return CompositionDecisionV1(
                DENY, "ACTION_SCOPE_NOT_DELEGATED", index - 1, consumed_compute,
                tuple(sorted(tags)), authority.root,
            )
        if index > authority.remaining_action_budget:
            return CompositionDecisionV1(
                DENY, "ACTION_BUDGET_EXHAUSTED", index - 1, consumed_compute,
                tuple(sorted(tags)), authority.root,
            )
        if consumed_compute + action.compute_cost > authority.remaining_compute_budget:
            return CompositionDecisionV1(
                DENY, "COMPUTE_BUDGET_EXHAUSTED", index - 1, consumed_compute,
                tuple(sorted(tags)), authority.root,
            )
        next_tags = tags | set(action.effect_tags)
        if any(rule.issubset(next_tags) for rule in forbidden):
            return CompositionDecisionV1(
                DENY, "FORBIDDEN_ACTION_COMPOSITION", index - 1, consumed_compute,
                tuple(sorted(tags)), authority.root,
            )
        consumed_compute += action.compute_cost
        tags = next_tags

    return CompositionDecisionV1(
        PERMIT, None, len(actions), consumed_compute, tuple(sorted(tags)), authority.root
    )


# ---------------------------------------------------------------------------
# 2. Decision != effect: explicit effect-time freshness check
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DecisionStateBindingV1:
    decision_root: str
    decision_outcome: str
    policy_state_root: str
    authority_epoch: int
    fence_commitment: str


def authorize_effect_now(
    decision: DecisionStateBindingV1,
    *,
    current_policy_state_root: str,
    current_authority_epoch: int,
    current_fence_commitment: str,
) -> str:
    """A prior PERMIT cannot authorize an effect after relevant state drift."""

    if decision.decision_outcome != PERMIT:
        return DENY
    if (
        decision.policy_state_root != current_policy_state_root
        or decision.authority_epoch != current_authority_epoch
        or decision.fence_commitment != current_fence_commitment
    ):
        return REVERIFY
    return PERMIT


# ---------------------------------------------------------------------------
# 3. Memory provenance: non-amplification + non-revival under replay
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class MemoryClaimV1:
    claim_id: str
    content_digest: str
    epistemic_tier: str
    authority_weight_bps: int
    source_ids: tuple[str, ...]
    derived_from: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        _require_tier(self.epistemic_tier)
        if not 0 <= self.authority_weight_bps <= 10_000:
            raise BoundaryFalsifierError("AUTHORITY_WEIGHT_BPS_INVALID")
        if not self.source_ids:
            raise BoundaryFalsifierError("MEMORY_SOURCE_BINDING_REQUIRED")


@dataclass(frozen=True)
class MemoryEventV1:
    sequence: int
    operation: str
    claim: MemoryClaimV1 | None = None
    target_claim_id: str | None = None

    def __post_init__(self) -> None:
        _require_nonnegative("sequence", self.sequence)
        if self.operation not in {"WRITE", "RETRACT"}:
            raise BoundaryFalsifierError("MEMORY_OPERATION_UNSUPPORTED")
        if self.operation == "WRITE" and self.claim is None:
            raise BoundaryFalsifierError("MEMORY_WRITE_CLAIM_REQUIRED")
        if self.operation == "RETRACT" and not self.target_claim_id:
            raise BoundaryFalsifierError("MEMORY_RETRACT_TARGET_REQUIRED")


@dataclass(frozen=True)
class ReplayedMemoryV1:
    claims: Mapping[str, MemoryClaimV1]
    statuses: Mapping[str, str]
    root: str

    def releasable(self, claim_id: str) -> bool:
        return self.statuses.get(claim_id) == ACTIVE


def derive_memory_claim(
    *,
    claim_id: str,
    content_digest: str,
    source_claims: Sequence[MemoryClaimV1],
    source_ids: Iterable[str],
    requested_tier: str | None = None,
    requested_authority_weight_bps: int | None = None,
) -> MemoryClaimV1:
    if not source_claims:
        raise BoundaryFalsifierError("DERIVED_MEMORY_SOURCE_CLAIM_REQUIRED")
    weakest_tier = min(source_claims, key=lambda item: TIER_RANK[item.epistemic_tier]).epistemic_tier
    max_weight = min(item.authority_weight_bps for item in source_claims)
    tier = weakest_tier if requested_tier is None else requested_tier
    weight = max_weight if requested_authority_weight_bps is None else requested_authority_weight_bps
    _require_tier(tier)
    if TIER_RANK[tier] > TIER_RANK[weakest_tier]:
        raise BoundaryFalsifierError("MEMORY_AUTHORITY_TIER_AMPLIFICATION_FORBIDDEN")
    if weight > max_weight:
        raise BoundaryFalsifierError("MEMORY_AUTHORITY_WEIGHT_AMPLIFICATION_FORBIDDEN")
    return MemoryClaimV1(
        claim_id=claim_id,
        content_digest=content_digest,
        epistemic_tier=tier,
        authority_weight_bps=weight,
        source_ids=tuple(sorted(set(source_ids))),
        derived_from=tuple(item.claim_id for item in source_claims),
    )


def replay_memory(events: Sequence[MemoryEventV1]) -> ReplayedMemoryV1:
    claims: dict[str, MemoryClaimV1] = {}
    statuses: dict[str, str] = {}
    expected_seq = 0
    for event in events:
        if event.sequence != expected_seq:
            raise BoundaryFalsifierError("MEMORY_EVENT_SEQUENCE_GAP")
        expected_seq += 1
        if event.operation == "WRITE":
            assert event.claim is not None
            claims[event.claim.claim_id] = event.claim
            source_claim_ids = set(event.claim.derived_from)
            if any(statuses.get(source_id) == RETRACTED for source_id in source_claim_ids):
                statuses[event.claim.claim_id] = RETRACTED
            elif statuses.get(event.claim.claim_id) == RETRACTED:
                statuses[event.claim.claim_id] = RETRACTED
            else:
                statuses[event.claim.claim_id] = ACTIVE
        else:
            target = event.target_claim_id
            assert target is not None
            statuses[target] = RETRACTED
            changed = True
            while changed:
                changed = False
                for claim_id, claim in claims.items():
                    if statuses.get(claim_id) != RETRACTED and any(
                        statuses.get(source_id) == RETRACTED for source_id in claim.derived_from
                    ):
                        statuses[claim_id] = RETRACTED
                        changed = True

    payload = {
        "claims": {key: asdict(claims[key]) for key in sorted(claims)},
        "statuses": {key: statuses[key] for key in sorted(statuses)},
    }
    return ReplayedMemoryV1(claims, statuses, _root("AEGIS_REPLAYED_MEMORY_V1", payload))


# ---------------------------------------------------------------------------
# 4. Replication != heritage: reconstructible Parent + Delta -> Child
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GenomeV1:
    genes: Mapping[str, str]

    @property
    def root(self) -> str:
        return _root("AEGIS_GENOME_V1", dict(sorted(self.genes.items())))


@dataclass(frozen=True)
class GenomeDeltaV1:
    parent_root: str
    set_genes: Mapping[str, str] = field(default_factory=dict)
    delete_genes: tuple[str, ...] = ()

    @property
    def root(self) -> str:
        return _root(
            "AEGIS_GENOME_DELTA_V1",
            {
                "parent_root": self.parent_root,
                "set_genes": dict(sorted(self.set_genes.items())),
                "delete_genes": sorted(self.delete_genes),
            },
        )


def reconstruct_child(parent: GenomeV1, delta: GenomeDeltaV1) -> GenomeV1:
    if delta.parent_root != parent.root:
        raise BoundaryFalsifierError("HERITAGE_PARENT_ROOT_MISMATCH")
    genes = dict(parent.genes)
    for key in delta.delete_genes:
        genes.pop(key, None)
    genes.update(delta.set_genes)
    return GenomeV1(dict(sorted(genes.items())))


@dataclass(frozen=True)
class HeritageProofV1:
    classification: str
    parent_root: str
    delta_root: str | None
    claimed_child_root: str
    reconstructed_child_root: str | None
    is_reconstructible: bool


def verify_heritage(
    *,
    parent: GenomeV1,
    claimed_child: GenomeV1,
    delta: GenomeDeltaV1 | None,
) -> HeritageProofV1:
    if delta is None:
        return HeritageProofV1(
            REPLICATION_ONLY,
            parent.root,
            None,
            claimed_child.root,
            None,
            False,
        )
    reconstructed = reconstruct_child(parent, delta)
    ok = reconstructed.root == claimed_child.root
    return HeritageProofV1(
        TRUE_HERITAGE if ok else REPLICATION_ONLY,
        parent.root,
        delta.root,
        claimed_child.root,
        reconstructed.root,
        ok,
    )


# ---------------------------------------------------------------------------
# 5. Multiple agents != independent evidence: joint co-execution ledger
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class PairedLaneOutcomeV1:
    trial_id: str
    lane_a_failed: bool
    lane_b_failed: bool


@dataclass(frozen=True)
class JointFailureCertificateV1:
    status: str
    trial_count: int
    a_failures: int
    b_failures: int
    joint_failures: int
    either_failures: int
    joint_given_either_micros: int | None
    empirical_joint_micros: int | None
    product_of_marginals_micros: int | None
    independence_claim_admissible: bool


def joint_failure_certificate(
    trials: Sequence[PairedLaneOutcomeV1],
) -> JointFailureCertificateV1:
    if not trials:
        return JointFailureCertificateV1(
            INDEPENDENCE_NOT_ESTABLISHED, 0, 0, 0, 0, 0,
            None, None, None, False,
        )
    if len({trial.trial_id for trial in trials}) != len(trials):
        raise BoundaryFalsifierError("JOINT_TRIAL_ID_DUPLICATE")
    n = len(trials)
    a = sum(1 for t in trials if t.lane_a_failed)
    b = sum(1 for t in trials if t.lane_b_failed)
    joint = sum(1 for t in trials if t.lane_a_failed and t.lane_b_failed)
    either = sum(1 for t in trials if t.lane_a_failed or t.lane_b_failed)
    joint_given_either = None if either == 0 else (joint * 1_000_000) // either
    empirical_joint = (joint * 1_000_000) // n
    product = ((a * 1_000_000) // n) * ((b * 1_000_000) // n) // 1_000_000
    return JointFailureCertificateV1(
        JOINT_EVIDENCE_PRESENT,
        n,
        a,
        b,
        joint,
        either,
        joint_given_either,
        empirical_joint,
        product,
        False,
    )
