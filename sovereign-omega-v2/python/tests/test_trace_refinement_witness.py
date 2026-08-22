from __future__ import annotations

import importlib
from dataclasses import replace

import pytest

from harness.sdk.proof_trace import CUSTOM, MEMORY, TraceSDK
from harness.sdk.trace_constraint_refinement import (
    ConstraintBindingV1,
    constraint_causal_root,
    make_constraint_certificate,
)

COMMIT = "a" * 40
POLICY = "b" * 64
STATE0 = "c" * 64
P_SECRET = "1" * 64
P_PUBLIC = "2" * 64
R_NO_SEND = "3" * 64
R_NO_SPAWN = "4" * 64
A_READ = "5" * 64
A_WRITE = "6" * 64
A_SEND = "7" * 64
BOGUS = "f" * 64


def witness_module():
    try:
        return importlib.import_module("harness.sdk.trace_refinement_witness")
    except ModuleNotFoundError:
        pytest.fail("trace_refinement_witness module is missing")


def valid_case():
    trace = TraceSDK.start_trace(
        workflow_name="kg005-proof-producing-refinement",
        source_commit=COMMIT,
        policy_commitment=POLICY,
        genesis_control_state_root=STATE0,
        deterministic_nonce="kg005",
        metadata={"claim": "KG-005", "raw_payloads": False},
    )
    source = trace.record_span(name="source", span_kind=CUSTOM)
    handle = trace.start_span(
        name="memory-transform",
        span_kind=MEMORY,
        causal_parent_ids=(source.span_id,),
    )
    child = trace.finish_span(handle)
    bundle = trace.close()

    source_binding = ConstraintBindingV1(
        trace_root=bundle.header.root,
        span_id=source.span_id,
        span_root=source.root,
        provenance_roots=(P_SECRET,),
        restriction_roots=(R_NO_SEND,),
        authority_roots=(A_READ, A_WRITE),
        causal_binding_roots=(),
        captured_control_state_root=source.control_state_before,
        causal_closure_root=constraint_causal_root(()),
    )
    child_binding = ConstraintBindingV1(
        trace_root=bundle.header.root,
        span_id=child.span_id,
        span_root=child.root,
        provenance_roots=(P_SECRET, P_PUBLIC),
        restriction_roots=(R_NO_SEND, R_NO_SPAWN),
        authority_roots=(A_READ,),
        causal_binding_roots=(source_binding.root,),
        captured_control_state_root=child.control_state_before,
        causal_closure_root=constraint_causal_root((source_binding.root,)),
    )
    certificate = make_constraint_certificate(bundle, (source_binding, child_binding))
    return bundle, certificate, source_binding, child_binding


def test_valid_certificate_emits_deterministic_witness():
    m = witness_module()
    bundle, certificate, _, _ = valid_case()
    witness1 = m.make_refinement_witness(bundle, certificate)
    witness2 = m.make_refinement_witness(bundle, certificate)
    assert witness1.root == witness2.root
    assert witness1.to_json() == witness2.to_json()
    assert len(witness1.edges) == 1


def test_invalid_certificate_cannot_emit_witness():
    m = witness_module()
    bundle, certificate, source, child = valid_case()
    forged_child = replace(child, authority_roots=(A_READ, A_SEND))
    forged = make_constraint_certificate(bundle, (source, forged_child))
    with pytest.raises(m.TraceRefinementWitnessError) as exc:
        m.make_refinement_witness(bundle, forged)
    assert exc.value.code == "CONSTRAINT_CERTIFICATE_INVALID"


def test_witness_is_bound_to_exact_bundle_and_certificate_roots():
    m = witness_module()
    bundle, certificate, _, _ = valid_case()
    witness = m.make_refinement_witness(bundle, certificate)
    assert witness.bundle_root == bundle.root
    assert witness.certificate_root == certificate.root
    tampered = replace(witness, certificate_root=BOGUS)
    verification = m.verify_refinement_witness(bundle, certificate, tampered)
    assert verification.valid is False
    assert "WITNESS_CERTIFICATE_ROOT_MISMATCH" in verification.errors


def test_witness_recomputes_semantic_edge_not_producer_claim():
    m = witness_module()
    bundle, certificate, _, _ = valid_case()
    witness = m.make_refinement_witness(bundle, certificate)
    edge = witness.edges[0]
    forged_edge = replace(edge, child_authority_roots=(A_READ, A_SEND))
    forged = replace(witness, edges=(forged_edge,))
    verification = m.verify_refinement_witness(bundle, certificate, forged)
    assert verification.valid is False
    assert any(code.startswith("WITNESS_EDGE_MISMATCH:") for code in verification.errors)


def test_coq_facts_emitter_is_deterministic_and_injection_closed():
    m = witness_module()
    bundle, certificate, _, _ = valid_case()
    witness = m.make_refinement_witness(bundle, certificate)
    coq1 = m.emit_coq_witness_facts(witness, module_name="KG005Witness")
    coq2 = m.emit_coq_witness_facts(witness, module_name="KG005Witness")
    assert coq1 == coq2
    assert "Module KG005Witness." in coq1
    assert witness.root in coq1
    with pytest.raises(m.TraceRefinementWitnessError) as exc:
        m.emit_coq_witness_facts(witness, module_name='Bad.Module") End X.')
    assert exc.value.code == "COQ_MODULE_NAME_INVALID"
