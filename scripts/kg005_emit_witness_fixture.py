#!/usr/bin/env python3
"""Emit one deterministic KG-005 witness module for CI kernel checking.

This is a test fixture producer only. It has no authority and performs no
external effects.
"""
from __future__ import annotations

import argparse
from pathlib import Path

from harness.sdk.proof_trace import CUSTOM, MEMORY, TraceSDK
from harness.sdk.trace_constraint_refinement import (
    ConstraintBindingV1,
    constraint_causal_root,
    make_constraint_certificate,
)
from harness.sdk.trace_refinement_witness import (
    emit_coq_witness_facts,
    make_refinement_witness,
    verify_refinement_witness,
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


def build_fixture():
    trace = TraceSDK.start_trace(
        workflow_name="kg005-proof-producing-refinement",
        source_commit=COMMIT,
        policy_commitment=POLICY,
        genesis_control_state_root=STATE0,
        deterministic_nonce="kg005-ci-fixture",
        metadata={"claim": "KG-005-CI", "raw_payloads": False},
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
    witness = make_refinement_witness(bundle, certificate)
    verification = verify_refinement_witness(bundle, certificate, witness)
    if not verification.valid:
        raise SystemExit("KG005_FIXTURE_WITNESS_INVALID:" + ",".join(verification.errors))
    return witness


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    witness = build_fixture()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        emit_coq_witness_facts(witness, module_name="KG005WitnessFacts"),
        encoding="utf-8",
    )
    print(witness.root)


if __name__ == "__main__":
    main()
