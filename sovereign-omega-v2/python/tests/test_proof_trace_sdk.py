from __future__ import annotations

import json
from dataclasses import replace

import pytest

from harness.sdk.proof_trace import (
    ADMISSION,
    ADMISSION_AUTHORITY,
    CUSTOM,
    DECISION,
    DECISION_AUTHORITY,
    DENIED,
    EFFECT,
    ERROR,
    EXTERNAL,
    MODEL,
    NO_AUTHORITY,
    OK,
    T1,
    T2,
    TOOL,
    TRACE_SEMANTICS,
    ZERO_HASH,
    ProofTraceBundleV1,
    ProofTraceError,
    TraceCommitV1,
    TraceSDK,
    bundle_from_json,
    digest_payload,
    openai_trace_metadata,
    trace_id_from_nonce,
    verify_trace_bundle,
)

COMMIT = "a" * 40
POLICY = "b" * 64
STATE0 = "c" * 64
STATE1 = "d" * 64
STATE2 = "e" * 64
TRANSITION = "1" * 64
DECISION_RECEIPT = "2" * 64
EFFECT_RECEIPT = "3" * 64
ADMISSION_RECEIPT = "4" * 64
EVIDENCE = "5" * 64


def new_trace(nonce: str = "trace-test"):
    return TraceSDK.start_trace(
        workflow_name="aegis-proofline",
        source_commit=COMMIT,
        policy_commitment=POLICY,
        genesis_control_state_root=STATE0,
        deterministic_nonce=nonce,
        group_id="campaign-1",
        metadata={"suite": "proof-trace", "raw_payloads": False},
    )


def test_trace_id_is_deterministic_and_source_bound():
    left = trace_id_from_nonce(
        workflow_name="aegis-proofline", source_commit=COMMIT, deterministic_nonce="n1"
    )
    right = trace_id_from_nonce(
        workflow_name="aegis-proofline", source_commit=COMMIT, deterministic_nonce="n1"
    )
    other = trace_id_from_nonce(
        workflow_name="aegis-proofline", source_commit="f" * 40, deterministic_nonce="n1"
    )
    assert left == right
    assert left.startswith("trace_")
    assert left != other


def test_trace_header_explicitly_says_trace_is_not_authority():
    trace = new_trace()
    assert trace.header.trace_semantics == TRACE_SEMANTICS
    assert trace.header.trace_semantics == "TRACE_IS_EVIDENCE_CONTAINER_NOT_AUTHORITY"


def test_model_output_cannot_carry_decision_authority():
    trace = new_trace()
    handle = trace.start_span(name="planner-model", span_kind=MODEL)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(handle, authority_class=DECISION_AUTHORITY, output_digest=digest_payload("answer"))
    assert exc.value.code == "EVIDENCE_ONLY_SPAN_CANNOT_CARRY_AUTHORITY"


def test_tool_output_cannot_carry_admission_authority():
    trace = new_trace()
    handle = trace.start_span(name="tool-call", span_kind=TOOL)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(handle, authority_class=ADMISSION_AUTHORITY, output_digest=digest_payload("result"))
    assert exc.value.code == "EVIDENCE_ONLY_SPAN_CANNOT_CARRY_AUTHORITY"


def test_decision_authority_requires_transition_and_receipt_binding():
    trace = new_trace()
    missing_transition = trace.start_span(name="decision-a", span_kind=DECISION)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(
            missing_transition,
            authority_class=DECISION_AUTHORITY,
            receipt_roots=(DECISION_RECEIPT,),
        )
    assert exc.value.code == "TRANSITION_BOUND_SPAN_MISSING_TRANSITION_ID"

    trace2 = new_trace("trace-test-2")
    missing_receipt = trace2.start_span(name="decision-b", span_kind=DECISION)
    with pytest.raises(ProofTraceError) as exc:
        trace2.finish_span(
            missing_receipt,
            authority_class=DECISION_AUTHORITY,
            transition_id=TRANSITION,
        )
    assert exc.value.code == "AUTHORITY_SPAN_RECEIPT_BINDING_REQUIRED"


def test_decision_effect_admission_remain_nominally_separate():
    trace = new_trace()
    decision = trace.record_span(
        name="permit-decision",
        span_kind=DECISION,
        transition_id=TRANSITION,
        authority_class=DECISION_AUTHORITY,
        epistemic_tier=T1,
        receipt_roots=(DECISION_RECEIPT,),
    )
    effect = trace.record_span(
        name="observed-effect",
        span_kind=EFFECT,
        transition_id=TRANSITION,
        authority_class=NO_AUTHORITY,
        receipt_roots=(EFFECT_RECEIPT,),
        observed_pre_state_root=STATE0,
        observed_post_state_root=STATE1,
    )
    assert decision.authority_class == DECISION_AUTHORITY
    assert effect.authority_class == NO_AUTHORITY
    assert effect.span_kind == EFFECT


def test_effect_span_requires_evidence_or_receipt():
    trace = new_trace()
    handle = trace.start_span(name="effect", span_kind=EFFECT)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(handle, transition_id=TRANSITION)
    assert exc.value.code == "EFFECT_SPAN_EVIDENCE_BINDING_REQUIRED"


def test_non_admission_span_cannot_advance_control_state():
    trace = new_trace()
    handle = trace.start_span(name="tool", span_kind=TOOL)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(handle, control_state_after=STATE1)
    assert exc.value.code == "NON_ADMISSION_CONTROL_STATE_MUTATION_FORBIDDEN"


def test_admission_without_admission_authority_cannot_advance_control_state():
    trace = new_trace()
    handle = trace.start_span(name="denied-admission", span_kind=ADMISSION)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(
            handle,
            status=DENIED,
            transition_id=TRANSITION,
            authority_class=NO_AUTHORITY,
            control_state_after=STATE1,
        )
    assert exc.value.code == "CONTROL_STATE_ADVANCE_REQUIRES_ADMISSION_AUTHORITY"


def test_receipt_bound_admission_advances_control_state_once():
    trace = new_trace()
    admitted = trace.record_span(
        name="admit-transition",
        span_kind=ADMISSION,
        transition_id=TRANSITION,
        authority_class=ADMISSION_AUTHORITY,
        epistemic_tier=T1,
        receipt_roots=(ADMISSION_RECEIPT,),
        control_state_after=STATE1,
    )
    assert admitted.control_state_before == STATE0
    assert admitted.control_state_after == STATE1
    assert trace.current_control_state_root == STATE1
    bundle = trace.close()
    assert bundle.final_control_state_root == STATE1
    assert verify_trace_bundle(bundle).valid is True


def test_two_admissions_started_from_same_prestate_cannot_both_commit():
    trace = new_trace()
    first = trace.start_span(name="admission-1", span_kind=ADMISSION)
    second = trace.start_span(name="admission-2", span_kind=ADMISSION)
    trace.finish_span(
        first,
        transition_id=TRANSITION,
        authority_class=ADMISSION_AUTHORITY,
        receipt_roots=(ADMISSION_RECEIPT,),
        control_state_after=STATE1,
    )
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(
            second,
            transition_id="6" * 64,
            authority_class=ADMISSION_AUTHORITY,
            receipt_roots=("7" * 64,),
            control_state_after=STATE2,
        )
    assert exc.value.code == "ADMISSION_CONTROL_STATE_STALE"
    assert trace.current_control_state_root == STATE1


def test_causal_parent_must_already_be_completed():
    trace = new_trace()
    parent = trace.start_span(name="parent", span_kind=CUSTOM)
    with pytest.raises(ProofTraceError) as exc:
        trace.start_span(name="child", span_kind=CUSTOM, causal_parent_ids=(parent.span_id,))
    assert exc.value.code == "CAUSAL_PARENT_NOT_COMPLETED"


def test_structural_parent_can_be_active_and_context_scope_nests():
    trace = new_trace()
    with trace.span(name="agent", span_kind=CUSTOM) as parent:
        with trace.span(name="tool", span_kind=TOOL) as child:
            child.bind_input({"query": "x"})
            child.bind_output({"count": 1})
        assert child.completed_span is not None
        assert child.completed_span.parent_span_id == parent.span_id
    bundle = trace.close()
    assert verify_trace_bundle(bundle).valid is True
    assert bundle.spans[0].name == "tool"
    assert bundle.spans[1].name == "agent"


def test_completed_span_can_be_bound_as_causal_parent():
    trace = new_trace()
    source = trace.record_span(name="evidence", span_kind=CUSTOM, evidence_roots=(EVIDENCE,))
    derived_handle = trace.start_span(
        name="verifier", span_kind=CUSTOM, causal_parent_ids=(source.span_id,)
    )
    derived = trace.finish_span(derived_handle, evidence_roots=(source.root,))
    assert derived.causal_parent_ids == (source.span_id,)
    assert trace.close().spans[-1].span_id == derived.span_id


def test_trace_cannot_close_with_active_span():
    trace = new_trace()
    trace.start_span(name="left-open", span_kind=CUSTOM)
    with pytest.raises(ProofTraceError) as exc:
        trace.close()
    assert exc.value.code == "TRACE_HAS_ACTIVE_SPANS"


def test_artifact_manifest_commits_receipts_and_evidence():
    trace = new_trace()
    trace.record_span(name="one", span_kind=CUSTOM, evidence_roots=(EVIDENCE,))
    trace.record_span(name="two", span_kind=CUSTOM, receipt_roots=(DECISION_RECEIPT,))
    bundle = trace.close()
    verification = verify_trace_bundle(bundle)
    assert verification.valid is True
    assert verification.artifact_count == 2
    assert verification.recomputed_artifact_manifest_root == bundle.artifact_manifest_root


def test_external_observability_span_is_forced_to_t2_evidence_only():
    trace = new_trace()
    span = trace.record_external_span(
        external_system="openai-agents",
        external_trace_id="trace_0123456789abcdef0123456789abcdef",
        external_span_id="span_0123456789abcdef",
        name="generation",
        payload={"model": "gpt", "captured": "digest-only"},
    )
    assert span.span_kind == EXTERNAL
    assert span.authority_class == NO_AUTHORITY
    assert span.epistemic_tier == T2
    assert span.external_ref_digest is not None


def test_external_span_does_not_store_raw_external_ids_in_export():
    trace = new_trace()
    external_trace_id = "trace_secretish_identifier"
    external_span_id = "span_secretish_identifier"
    trace.record_external_span(
        external_system="openai-agents",
        external_trace_id=external_trace_id,
        external_span_id=external_span_id,
        name="external",
        payload={"prompt": "not retained as plaintext"},
    )
    exported = trace.close().to_json()
    assert external_trace_id not in exported
    assert external_span_id not in exported
    assert "not retained as plaintext" not in exported


def test_context_scope_records_error_without_storing_exception_text():
    trace = new_trace()
    with pytest.raises(RuntimeError):
        with trace.span(name="failure", span_kind=CUSTOM):
            raise RuntimeError("sensitive exception body")
    bundle = trace.close()
    assert bundle.spans[0].status == ERROR
    assert bundle.spans[0].error_code == "UNHANDLED_EXCEPTION"
    assert "sensitive exception body" not in bundle.to_json()


def test_bundle_json_roundtrip_is_byte_root_stable():
    trace = new_trace()
    trace.record_span(name="evidence", span_kind=CUSTOM, evidence_roots=(EVIDENCE,))
    bundle = trace.close()
    payload = bundle.to_json()
    loaded = bundle_from_json(payload)
    assert loaded.root == bundle.root
    assert loaded.to_json() == payload
    assert verify_trace_bundle(loaded).valid is True


def test_json_supplied_bundle_root_tamper_fails_closed():
    trace = new_trace()
    trace.record_span(name="evidence", span_kind=CUSTOM)
    raw = json.loads(trace.close().to_json())
    raw["bundle_root"] = "f" * 64
    with pytest.raises(ProofTraceError) as exc:
        bundle_from_json(json.dumps(raw))
    assert exc.value.code == "TRACE_BUNDLE_ROOT_MISMATCH"


def test_span_output_tamper_is_detected_by_commit_chain():
    trace = new_trace()
    trace.record_span(name="model", span_kind=MODEL, output_digest=digest_payload("original"))
    bundle = trace.close()
    changed_span = replace(bundle.spans[0], output_digest=digest_payload("tampered"))
    tampered = ProofTraceBundleV1(
        bundle_kind=bundle.bundle_kind,
        header=bundle.header,
        spans=(changed_span,),
        commits=bundle.commits,
        final_control_state_root=bundle.final_control_state_root,
        artifact_manifest_root=bundle.artifact_manifest_root,
        terminal_commit_root=bundle.terminal_commit_root,
    )
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert any(code.startswith("TRACE_COMMIT_SPAN_ROOT_MISMATCH") for code in verification.errors)


def test_missing_structural_parent_is_detected_even_if_span_is_nominally_valid():
    trace = new_trace()
    span = trace.record_span(name="root", span_kind=CUSTOM)
    bundle = trace.close()
    changed = replace(span, parent_span_id="span_missing")
    commit = TraceCommitV1(
        sequence=1,
        span_id=changed.span_id,
        span_root=changed.root,
        prior_commit_root=ZERO_HASH,
    )
    tampered = ProofTraceBundleV1(
        bundle_kind=bundle.bundle_kind,
        header=bundle.header,
        spans=(changed,),
        commits=(commit,),
        final_control_state_root=bundle.final_control_state_root,
        artifact_manifest_root=bundle.artifact_manifest_root,
        terminal_commit_root=commit.root,
    )
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert f"STRUCTURAL_PARENT_MISSING:{changed.span_id}" in verification.errors


def test_structural_cycle_is_detected():
    trace = new_trace()
    a = trace.record_span(name="a", span_kind=CUSTOM)
    b = trace.record_span(name="b", span_kind=CUSTOM)
    bundle = trace.close()
    a2 = replace(a, parent_span_id=b.span_id)
    b2 = replace(b, parent_span_id=a.span_id)
    c1 = TraceCommitV1(1, a2.span_id, a2.root, ZERO_HASH)
    c2 = TraceCommitV1(2, b2.span_id, b2.root, c1.root)
    tampered = ProofTraceBundleV1(
        bundle_kind=bundle.bundle_kind,
        header=bundle.header,
        spans=(a2, b2),
        commits=(c1, c2),
        final_control_state_root=bundle.final_control_state_root,
        artifact_manifest_root=bundle.artifact_manifest_root,
        terminal_commit_root=c2.root,
    )
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert "STRUCTURAL_PARENT_CYCLE" in verification.errors


def test_causal_parent_must_precede_dependent_span_in_commit_order():
    trace = new_trace()
    a = trace.record_span(name="a", span_kind=CUSTOM)
    b = trace.record_span(name="b", span_kind=CUSTOM)
    bundle = trace.close()
    a2 = replace(a, causal_parent_ids=(b.span_id,))
    c1 = TraceCommitV1(1, a2.span_id, a2.root, ZERO_HASH)
    c2 = TraceCommitV1(2, b.span_id, b.root, c1.root)
    tampered = ProofTraceBundleV1(
        bundle_kind=bundle.bundle_kind,
        header=bundle.header,
        spans=(a2, b),
        commits=(c1, c2),
        final_control_state_root=bundle.final_control_state_root,
        artifact_manifest_root=bundle.artifact_manifest_root,
        terminal_commit_root=c2.root,
    )
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert f"CAUSAL_PARENT_NOT_PRIOR:{a2.span_id}" in verification.errors


def test_final_control_state_tamper_is_detected():
    trace = new_trace()
    trace.record_span(
        name="admission",
        span_kind=ADMISSION,
        transition_id=TRANSITION,
        authority_class=ADMISSION_AUTHORITY,
        receipt_roots=(ADMISSION_RECEIPT,),
        control_state_after=STATE1,
    )
    bundle = trace.close()
    tampered = replace(bundle, final_control_state_root=STATE2)
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert "TRACE_FINAL_CONTROL_STATE_MISMATCH" in verification.errors


def test_artifact_manifest_tamper_is_detected():
    trace = new_trace()
    trace.record_span(name="evidence", span_kind=CUSTOM, evidence_roots=(EVIDENCE,))
    bundle = trace.close()
    tampered = replace(bundle, artifact_manifest_root="f" * 64)
    verification = verify_trace_bundle(tampered)
    assert verification.valid is False
    assert "TRACE_ARTIFACT_MANIFEST_MISMATCH" in verification.errors


def test_openai_metadata_binds_observability_trace_to_aegis_bundle_only():
    trace = new_trace()
    trace.record_span(name="model", span_kind=MODEL, output_digest=digest_payload("answer"))
    bundle = trace.close()
    metadata = openai_trace_metadata(bundle)
    assert metadata["aegis_bundle_root"] == bundle.root
    assert metadata["aegis_terminal_commit_root"] == bundle.terminal_commit_root
    assert metadata["aegis_policy_commitment"] == POLICY
    assert set(metadata) == {
        "aegis_trace_id",
        "aegis_trace_root",
        "aegis_bundle_root",
        "aegis_terminal_commit_root",
        "aegis_policy_commitment",
        "aegis_source_commit",
    }


def test_trace_with_no_spans_is_structurally_valid_but_contains_no_evidence():
    bundle = new_trace().close()
    verification = verify_trace_bundle(bundle)
    assert verification.valid is True
    assert verification.span_count == 0
    assert verification.artifact_count == 0
    assert bundle.terminal_commit_root == ZERO_HASH
    assert bundle.final_control_state_root == STATE0


def test_duplicate_receipt_roots_are_rejected():
    trace = new_trace()
    handle = trace.start_span(name="custom", span_kind=CUSTOM)
    with pytest.raises(ProofTraceError) as exc:
        trace.finish_span(handle, receipt_roots=(DECISION_RECEIPT, DECISION_RECEIPT))
    assert exc.value.code == "receipt_root:DUPLICATE"


def test_digest_payload_is_domain_separated_from_trace_roots():
    value = {"x": 1}
    assert digest_payload(value) == digest_payload(value)
    assert digest_payload(value) != POLICY
