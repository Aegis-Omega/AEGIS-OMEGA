from __future__ import annotations

import pytest

from harness.sdk.weekly_research_falsifiers import (
    ACTIVE,
    DENY,
    INDEPENDENCE_NOT_ESTABLISHED,
    JOINT_EVIDENCE_PRESENT,
    PERMIT,
    REPLICATION_ONLY,
    RETRACTED,
    REVERIFY,
    TRUE_HERITAGE,
    AuthorizedActionV1,
    BoundaryFalsifierError,
    DecisionStateBindingV1,
    DelegatedAuthorityV1,
    GenomeDeltaV1,
    GenomeV1,
    MemoryClaimV1,
    MemoryEventV1,
    PairedLaneOutcomeV1,
    authorize_composition,
    authorize_effect_now,
    delegate_authority,
    derive_memory_claim,
    joint_failure_certificate,
    reconstruct_child,
    replay_memory,
    verify_heritage,
)


def root_authority() -> DelegatedAuthorityV1:
    return DelegatedAuthorityV1(
        principal="A",
        task_id="task-42",
        intent_digest="intent:ship-release",
        scopes=("read", "stage", "publish"),
        remaining_action_budget=8,
        remaining_compute_budget=1_000,
    )


def test_individually_permitted_actions_can_be_forbidden_in_composition():
    authority = root_authority()
    read_secret = AuthorizedActionV1("read-secret", "read", 10, ("secret-read",))
    external_send = AuthorizedActionV1("external-send", "publish", 10, ("external-send",))
    forbidden = (frozenset({"secret-read", "external-send"}),)

    assert authorize_composition(authority, [read_secret], forbidden_effect_compositions=forbidden).outcome == PERMIT
    assert authorize_composition(authority, [external_send], forbidden_effect_compositions=forbidden).outcome == PERMIT

    combined = authorize_composition(
        authority,
        [read_secret, external_send],
        forbidden_effect_compositions=forbidden,
    )
    assert combined.outcome == DENY
    assert combined.denial_code == "FORBIDDEN_ACTION_COMPOSITION"
    assert combined.consumed_actions == 1


def test_delegation_a_to_b_to_c_monotonically_contracts_scope_and_budgets():
    a = root_authority()
    b = delegate_authority(
        a,
        child_principal="B",
        scopes=("read", "stage"),
        action_budget=5,
        compute_budget=700,
    )
    c = delegate_authority(
        b,
        child_principal="C",
        scopes=("read",),
        action_budget=2,
        compute_budget=250,
    )

    assert set(c.scopes) <= set(b.scopes) <= set(a.scopes)
    assert c.remaining_action_budget <= b.remaining_action_budget <= a.remaining_action_budget
    assert c.remaining_compute_budget <= b.remaining_compute_budget <= a.remaining_compute_budget
    assert b.parent_root == a.root
    assert c.parent_root == b.root
    assert c.task_id == a.task_id
    assert c.intent_digest == a.intent_digest


@pytest.mark.parametrize(
    ("kwargs", "code"),
    [
        ({"scopes": ("read", "admin"), "action_budget": 1, "compute_budget": 1}, "SCOPE_EXPANSION_FORBIDDEN"),
        ({"scopes": ("read",), "action_budget": 9, "compute_budget": 1}, "ACTION_BUDGET_EXPANSION_FORBIDDEN"),
        ({"scopes": ("read",), "action_budget": 1, "compute_budget": 1_001}, "COMPUTE_BUDGET_EXPANSION_FORBIDDEN"),
        ({"scopes": ("read",), "action_budget": 1, "compute_budget": 1, "task_id": "other"}, "TASK_BINDING_CHANGED"),
        ({"scopes": ("read",), "action_budget": 1, "compute_budget": 1, "intent_digest": "other"}, "INTENT_BINDING_CHANGED"),
    ],
)
def test_delegation_expansion_or_rebinding_fails_closed(kwargs, code):
    with pytest.raises(BoundaryFalsifierError) as exc:
        delegate_authority(root_authority(), child_principal="B", **kwargs)
    assert exc.value.code == code


def test_action_and_compute_budget_are_accumulated_across_sequence():
    authority = DelegatedAuthorityV1(
        principal="A",
        task_id="task",
        intent_digest="intent",
        scopes=("read",),
        remaining_action_budget=2,
        remaining_compute_budget=15,
    )
    actions = [
        AuthorizedActionV1("a1", "read", 8),
        AuthorizedActionV1("a2", "read", 8),
    ]
    decision = authorize_composition(authority, actions)
    assert decision.outcome == DENY
    assert decision.denial_code == "COMPUTE_BUDGET_EXHAUSTED"
    assert decision.consumed_actions == 1
    assert decision.consumed_compute == 8


def test_permit_at_decision_time_becomes_reverify_after_policy_state_advance():
    decision = DecisionStateBindingV1(
        decision_root="d" * 64,
        decision_outcome=PERMIT,
        policy_state_root="1" * 64,
        authority_epoch=7,
        fence_commitment="f" * 64,
    )

    assert authorize_effect_now(
        decision,
        current_policy_state_root="1" * 64,
        current_authority_epoch=7,
        current_fence_commitment="f" * 64,
    ) == PERMIT

    assert authorize_effect_now(
        decision,
        current_policy_state_root="2" * 64,
        current_authority_epoch=7,
        current_fence_commitment="f" * 64,
    ) == REVERIFY


def test_epoch_or_fence_drift_also_requires_reverification():
    decision = DecisionStateBindingV1("d" * 64, PERMIT, "1" * 64, 7, "f" * 64)
    assert authorize_effect_now(
        decision,
        current_policy_state_root="1" * 64,
        current_authority_epoch=8,
        current_fence_commitment="f" * 64,
    ) == REVERIFY
    assert authorize_effect_now(
        decision,
        current_policy_state_root="1" * 64,
        current_authority_epoch=7,
        current_fence_commitment="e" * 64,
    ) == REVERIFY


def test_prior_deny_never_becomes_effect_authority():
    decision = DecisionStateBindingV1("d" * 64, DENY, "1" * 64, 7, "f" * 64)
    assert authorize_effect_now(
        decision,
        current_policy_state_root="1" * 64,
        current_authority_epoch=7,
        current_fence_commitment="f" * 64,
    ) == DENY


def t2_source() -> MemoryClaimV1:
    return MemoryClaimV1(
        claim_id="source",
        content_digest="a" * 64,
        epistemic_tier="T2",
        authority_weight_bps=0,
        source_ids=("sensorium:event:1",),
    )


def test_memory_consolidation_cannot_amplify_t2_to_t1_or_t0():
    source = t2_source()
    with pytest.raises(BoundaryFalsifierError) as exc:
        derive_memory_claim(
            claim_id="summary",
            content_digest="b" * 64,
            source_claims=[source],
            source_ids=("summary:1",),
            requested_tier="T1",
        )
    assert exc.value.code == "MEMORY_AUTHORITY_TIER_AMPLIFICATION_FORBIDDEN"


def test_memory_consolidation_cannot_increase_authority_weight():
    source = MemoryClaimV1("source", "a" * 64, "T1", 2500, ("source:1",))
    with pytest.raises(BoundaryFalsifierError) as exc:
        derive_memory_claim(
            claim_id="summary",
            content_digest="b" * 64,
            source_claims=[source],
            source_ids=("summary:1",),
            requested_authority_weight_bps=2501,
        )
    assert exc.value.code == "MEMORY_AUTHORITY_WEIGHT_AMPLIFICATION_FORBIDDEN"


def test_retracted_source_cannot_revive_through_old_summary_or_later_rewrite():
    source = t2_source()
    summary = derive_memory_claim(
        claim_id="summary",
        content_digest="b" * 64,
        source_claims=[source],
        source_ids=("summary:1",),
    )
    events = [
        MemoryEventV1(0, "WRITE", claim=source),
        MemoryEventV1(1, "WRITE", claim=summary),
        MemoryEventV1(2, "RETRACT", target_claim_id="source"),
        MemoryEventV1(3, "WRITE", claim=summary),
    ]

    first = replay_memory(events)
    second = replay_memory(events)
    assert first.root == second.root
    assert first.statuses["source"] == RETRACTED
    assert first.statuses["summary"] == RETRACTED
    assert first.releasable("summary") is False


def test_retraction_propagates_transitively_across_derived_memory_chain():
    source = t2_source()
    summary = derive_memory_claim(
        claim_id="summary",
        content_digest="b" * 64,
        source_claims=[source],
        source_ids=("summary:1",),
    )
    summary2 = derive_memory_claim(
        claim_id="summary2",
        content_digest="c" * 64,
        source_claims=[summary],
        source_ids=("summary:2",),
    )
    replayed = replay_memory([
        MemoryEventV1(0, "WRITE", claim=source),
        MemoryEventV1(1, "WRITE", claim=summary),
        MemoryEventV1(2, "WRITE", claim=summary2),
        MemoryEventV1(3, "RETRACT", target_claim_id="source"),
    ])
    assert replayed.statuses == {
        "source": RETRACTED,
        "summary": RETRACTED,
        "summary2": RETRACTED,
    }


def test_normal_memory_write_is_active_before_retraction():
    source = t2_source()
    replayed = replay_memory([MemoryEventV1(0, "WRITE", claim=source)])
    assert replayed.statuses["source"] == ACTIVE
    assert replayed.releasable("source") is True


def test_parent_plus_committed_delta_reconstructs_child_exactly():
    parent = GenomeV1({"planner": "v1", "memory": "v2", "skill:sheet": "v1"})
    delta = GenomeDeltaV1(
        parent_root=parent.root,
        set_genes={"planner": "v2", "skill:sheet": "v2"},
    )
    child = reconstruct_child(parent, delta)
    proof = verify_heritage(parent=parent, claimed_child=child, delta=delta)
    assert proof.classification == TRUE_HERITAGE
    assert proof.is_reconstructible is True
    assert proof.reconstructed_child_root == child.root


def test_copied_skill_without_parent_delta_proof_is_replication_not_heritage():
    parent = GenomeV1({"skill:sheet": "v1"})
    copied = GenomeV1({"skill:sheet": "v1"})
    proof = verify_heritage(parent=parent, claimed_child=copied, delta=None)
    assert proof.classification == REPLICATION_ONLY
    assert proof.is_reconstructible is False


def test_wrong_child_fails_heritage_classification_even_with_a_delta():
    parent = GenomeV1({"skill": "v1"})
    delta = GenomeDeltaV1(parent_root=parent.root, set_genes={"skill": "v2"})
    unrelated_child = GenomeV1({"skill": "v3"})
    proof = verify_heritage(parent=parent, claimed_child=unrelated_child, delta=delta)
    assert proof.classification == REPLICATION_ONLY
    assert proof.is_reconstructible is False


def test_delta_is_bound_to_exact_parent_root():
    parent = GenomeV1({"skill": "v1"})
    wrong_parent = GenomeV1({"skill": "other"})
    delta = GenomeDeltaV1(parent_root=wrong_parent.root, set_genes={"skill": "v2"})
    with pytest.raises(BoundaryFalsifierError) as exc:
        reconstruct_child(parent, delta)
    assert exc.value.code == "HERITAGE_PARENT_ROOT_MISMATCH"


def test_no_joint_trials_means_independence_is_not_established():
    cert = joint_failure_certificate([])
    assert cert.status == INDEPENDENCE_NOT_ESTABLISHED
    assert cert.independence_claim_admissible is False


def test_joint_coexecution_certificate_measures_dependence_without_claiming_independence():
    trials = [
        PairedLaneOutcomeV1("t1", True, True),
        PairedLaneOutcomeV1("t2", True, True),
        PairedLaneOutcomeV1("t3", True, False),
        PairedLaneOutcomeV1("t4", False, True),
        PairedLaneOutcomeV1("t5", False, False),
    ]
    cert = joint_failure_certificate(trials)
    assert cert.status == JOINT_EVIDENCE_PRESENT
    assert cert.trial_count == 5
    assert cert.a_failures == 3
    assert cert.b_failures == 3
    assert cert.joint_failures == 2
    assert cert.either_failures == 4
    assert cert.joint_given_either_micros == 500_000
    assert cert.empirical_joint_micros == 400_000
    assert cert.product_of_marginals_micros == 360_000
    assert cert.independence_claim_admissible is False


def test_joint_trials_require_unique_trial_identity():
    with pytest.raises(BoundaryFalsifierError) as exc:
        joint_failure_certificate([
            PairedLaneOutcomeV1("same", True, False),
            PairedLaneOutcomeV1("same", False, True),
        ])
    assert exc.value.code == "JOINT_TRIAL_ID_DUPLICATE"
