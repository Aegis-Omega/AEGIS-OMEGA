from __future__ import annotations

import importlib
from dataclasses import replace

import pytest

from harness.sdk.proof_trace import CUSTOM, HANDOFF, HERITAGE, MEMORY, TraceSDK

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


def refinement_module():
    try:
        return importlib.import_module("harness.sdk.trace_constraint_refinement")
    except ModuleNotFoundError:
        pytest.fail("trace_constraint_refinement module is missing")


def new_trace(nonce: str = "kg004"):
    return TraceSDK.start_trace(
        workflow_name="kg004-trace-refinement",
        source_commit=COMMIT,
        policy_commitment=POLICY,
        genesis_control_state_root=STATE0,
        deterministic_nonce=nonce,
        metadata={"claim": "KG-004", "raw_payloads": False},
    )


def valid_bundle_and_bindings(kind: str = MEMORY):
    m = refinement_module()
    trace = new_trace(kind.lower())
    source = trace.record_span(name="source", span_kind=CUSTOM)
    child_handle = trace.start_span(
        name=f"derived-{kind.lower()}",
        span_kind=kind,
        causal_parent_ids=(source.span_id,),
    )
    child = trace.finish_span(child_handle)
    bundle = trace.close()

    source_binding = m.ConstraintBindingV1(
        trace_root=bundle.header.root,
        span_id=source.span_id,
        span_root=source.root,
        provenance_roots=(P_SECRET,),
        restriction_roots=(R_NO_SEND,),
        authority_roots=(A_READ, A_WRITE),
        causal_binding_roots=(),
        captured_control_state_root=source.control_state_before,
        causal_closure_root=m.constraint_causal_root(()),
    )
    child_binding = m.ConstraintBindingV1(
        trace_root=bundle.header.root,
        span_id=child.span_id,
        span_root=child.root,
        provenance_roots=(P_SECRET, P_PUBLIC),
        restriction_roots=(R_NO_SEND, R_NO_SPAWN),
        authority_roots=(A_READ,),
        causal_binding_roots=(source_binding.root,),
        captured_control_state_root=child.control_state_before,
        causal_closure_root=m.constraint_causal_root((source_binding.root,)),
    )
    return bundle, source_binding, child_binding


@pytest.mark.parametrize("kind", [MEMORY, HANDOFF, HERITAGE])
def test_valid_constraint_carrying_causal_edge_is_accepted(kind: str):
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings(kind)
    certificate = m.make_constraint_certificate(bundle, (source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is True
    assert verification.errors == ()
    assert verification.binding_count == 2
    assert verification.constraint_edge_count == 1
    assert certificate.certificate_semantics == "CONSTRAINT_BINDINGS_ARE_EVIDENCE_NOT_AUTHORITY"


def test_provenance_laundering_is_rejected():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    child = replace(child, provenance_roots=())
    certificate = m.make_constraint_certificate(bundle, (source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert any(code.startswith("PROVENANCE_NOT_PRESERVED:") for code in verification.errors)


def test_restriction_laundering_is_rejected():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    child = replace(child, restriction_roots=())
    certificate = m.make_constraint_certificate(bundle, (source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert any(code.startswith("RESTRICTION_NOT_PRESERVED:") for code in verification.errors)


def test_authority_amplification_is_rejected():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    child = replace(child, authority_roots=(A_READ, A_SEND))
    certificate = m.make_constraint_certificate(bundle, (source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert any(code.startswith("AUTHORITY_AMPLIFICATION:") for code in verification.errors)


def test_causal_binding_splice_is_rejected():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    child = replace(
        child,
        causal_binding_roots=(BOGUS,),
        causal_closure_root=m.constraint_causal_root((BOGUS,)),
    )
    certificate = m.make_constraint_certificate(bundle, (source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert any(code.startswith("CAUSAL_BINDING_ROOT_MISMATCH:") for code in verification.errors)


def test_certificate_is_bound_to_exact_trace_bundle():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    certificate = m.make_constraint_certificate(bundle, (source, child))
    certificate = replace(certificate, bundle_root=BOGUS)
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert "CERTIFICATE_BUNDLE_ROOT_MISMATCH" in verification.errors


def test_binding_is_bound_to_exact_span_root_and_state():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    forged_source = replace(source, span_root=BOGUS, captured_control_state_root=BOGUS)
    certificate = m.make_constraint_certificate(bundle, (forged_source, child))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert any(code.startswith("BINDING_SPAN_ROOT_MISMATCH:") for code in verification.errors)
    assert any(code.startswith("BINDING_STATE_ROOT_MISMATCH:") for code in verification.errors)


def test_constraint_carrying_span_requires_semantic_binding():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    certificate = m.make_constraint_certificate(bundle, (source,))
    verification = m.verify_constraint_certificate(bundle, certificate)
    assert verification.valid is False
    assert f"CONSTRAINT_SPAN_BINDING_MISSING:{child.span_id}" in verification.errors


def test_certificate_json_roundtrip_is_root_stable():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings(HERITAGE)
    certificate = m.make_constraint_certificate(bundle, (source, child))
    payload = certificate.to_json()
    loaded = m.constraint_certificate_from_json(payload)
    assert loaded.root == certificate.root
    assert loaded.to_json() == payload
    assert m.verify_constraint_certificate(bundle, loaded).valid is True


def test_duplicate_constraint_roots_fail_closed():
    m = refinement_module()
    bundle, source, child = valid_bundle_and_bindings()
    with pytest.raises(m.TraceConstraintError) as exc:
        replace(child, provenance_roots=(P_SECRET, P_SECRET)).__post_init__()
    assert exc.value.code == "provenance_root:DUPLICATE"
