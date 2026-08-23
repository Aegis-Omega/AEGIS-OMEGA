from dataclasses import replace

import pytest

from harness.sdk.proof_trace import NO_AUTHORITY, T2, VERIFIER, TraceSDK
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import (
    ASSUME_GLOBAL_WEIL_POSITIVITY,
    ASSUME_RH,
    ExactRationalV1,
    WeilBridgeError,
    WeilFamilyEvidenceV1,
    WeilInstanceEvidenceV1,
    bind_weil_instance_verification,
    request_global_weil_claim,
    verify_weil_family,
    verify_weil_instance,
)


def h(label: str) -> str:
    return canonical_hash("TEST_WEIL_BRIDGE_V1", {"label": label})


def r(n: int, d: int = 1) -> ExactRationalV1:
    return ExactRationalV1(numerator=n, denominator=d)


def evidence(*, test_id: str = "f-1", q=(3, 2), norm=(2, 1), eps=(1, 4), delta=(1, 2), assumptions=()):
    return WeilInstanceEvidenceV1(
        test_function_digest=h(test_id),
        cutoff=13,
        q_r=r(*q),
        norm_sq=r(*norm),
        epsilon_r=r(*eps),
        approximation_delta=r(*delta),
        finite_evaluator_root=h(f"finite:{test_id}"),
        approximation_bound_root=h(f"approx:{test_id}"),
        assumption_tags=tuple(assumptions),
    )


def test_exact_rational_normalizes_sign_and_reduces():
    x = ExactRationalV1(6, -8)
    assert (x.numerator, x.denominator) == (-3, 4)


def test_local_kernel_verifies_finite_lower_bound_and_conditional_target_bound():
    result = verify_weil_instance(evidence())
    assert result.valid is True
    assert result.finite_lower_bound_verified is True
    assert result.conditional_target_nonnegative is True
    assert result.premises_independently_verified is False
    assert result.rh_proven is False
    assert result.status == "LOCAL_ALGEBRAIC_INFERENCE_VERIFIED"
    assert "APPROXIMATION_PREMISE_REQUIRES_INDEPENDENT_VERIFIER" in result.open_obligations


def test_finite_lower_bound_violation_fails_closed():
    result = verify_weil_instance(evidence(q=(-2, 1), norm=(1, 1), eps=(1, 2), delta=(0, 1)))
    assert result.valid is False
    assert result.finite_lower_bound_verified is False
    assert "FINITE_LOWER_BOUND_VIOLATED" in result.errors
    assert result.rh_proven is False


def test_circular_rh_assumption_is_rejected():
    result = verify_weil_instance(evidence(assumptions=(ASSUME_RH,)))
    assert result.valid is False
    assert result.circular is True
    assert "CIRCULAR_ASSUMPTION_FORBIDDEN" in result.errors


def test_circular_global_weil_assumption_is_rejected():
    result = verify_weil_instance(evidence(assumptions=(ASSUME_GLOBAL_WEIL_POSITIVITY,)))
    assert result.valid is False
    assert result.circular is True


def test_family_root_is_order_independent_and_never_claims_globality():
    a = evidence(test_id="a")
    b = evidence(test_id="b", q=(5, 2), delta=(1, 4))
    left = verify_weil_family(WeilFamilyEvidenceV1(family_id="family-1", members=(a, b)))
    right = verify_weil_family(WeilFamilyEvidenceV1(family_id="family-1", members=(b, a)))
    assert left.family_root == right.family_root
    assert left.member_count == 2
    assert left.global_weil_positivity_proven is False
    assert left.rh_proven is False


def test_global_claim_gate_stays_open_without_machine_verified_globalizer():
    family = verify_weil_family(WeilFamilyEvidenceV1(family_id="family-1", members=(evidence(),)))
    gate = request_global_weil_claim(
        family,
        density_proof_root=h("density"),
        continuity_proof_root=h("continuity"),
        universal_coverage_proof_root=h("coverage"),
    )
    assert gate.closed is False
    assert gate.rh_proven is False
    assert gate.status == "OPEN_KERNEL_GLOBALIZATION_REQUIRED"
    assert "GLOBALIZATION_THEOREMS_NOT_MACHINE_VERIFIED" in gate.open_obligations


def test_trace_binding_is_verifier_t2_evidence_only_and_does_not_move_control_state():
    trace = TraceSDK.start_trace(
        workflow_name="weil-bridge-test",
        source_commit="a" * 40,
        policy_commitment=h("policy"),
        genesis_control_state_root=h("state"),
        deterministic_nonce="test-1",
    )
    binding = bind_weil_instance_verification(trace, evidence())
    bundle = trace.close()
    assert binding.span.span_kind == VERIFIER
    assert binding.span.authority_class == NO_AUTHORITY
    assert binding.span.epistemic_tier == T2
    assert bundle.final_control_state_root == h("state")
    assert binding.verification.rh_proven is False


def test_receipt_root_changes_under_semantic_tamper():
    original = verify_weil_instance(evidence())
    tampered = verify_weil_instance(evidence(delta=(1, 4)))
    assert original.receipt_root != tampered.receipt_root


def test_invalid_hash_and_nonpositive_denominator_fail_closed_at_construction():
    with pytest.raises(WeilBridgeError, match="DENOMINATOR_INVALID"):
        ExactRationalV1(1, 0)
    with pytest.raises(WeilBridgeError, match="INVALID_SHA256"):
        replace(evidence(), test_function_digest="not-a-hash")
