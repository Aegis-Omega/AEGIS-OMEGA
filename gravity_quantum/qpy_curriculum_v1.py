#!/usr/bin/env python3
"""AEGIS Ω Proof-Carrying QPY Curriculum v1.

Research-only training-data generator.

A curriculum item becomes gradient-admissible only when the same pinned
two-qubit Ising evolution is consistent across:

1. an analytic closed-form oracle,
2. CUDA-Q qpp-cpu,
3. PennyLane default.qubit,
4. Qiskit Statevector after a QPY v17 round-trip,

and the separability label is bound to the machine-formalized two-qubit pure
product determinant criterion from GravityQuantumPureProductV1.lean.

This module creates no scientific, operational, or model authority.  It only
constructs evidence-bound training examples and exact serialization receipts.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import io
import json
import math
import re
from pathlib import Path
from typing import Any

from qiskit import QuantumCircuit, qpy
from qiskit.quantum_info import SparsePauliOp, Statevector

from aegis_learning.evidence_gradient_compiler_v1 import (
    CompilerPolicy,
    FailureKind,
    LearningDisposition,
    Witness,
    WitnessStatus,
    canonical_json_bytes,
    compile_evidence_gradient,
    sha256_hex,
)

from gravity_quantum.cudaq_twoqubit_v1 import (
    COEFFICIENT_SCALE,
    DEFAULT_TIME_SCALED,
    DYNAMICS_TOLERANCE_SCALED,
    FIELD0_SCALED,
    FIELD1_SCALED,
    INTERACTION_J_SCALED,
    TIME_SCALE,
    VALUE_SCALE,
    run_dynamics_point,
)
from gravity_quantum.crossframework_v1 import pennylane_dynamics_point

SCHEMA = "AEGIS_PROOF_CARRYING_QPY_CURRICULUM_V1"
EXPECTED_QISKIT_VERSION = "2.5.2"
QPY_FORMAT_VERSION = 17
TRAINING_WEIGHT_PPM = 1_000_000
DET_SCALE = 1_000_000_000_000
DET_TOLERANCE_SCALED = 1_000

PARENT_CROSSFRAMEWORK_HEAD = "e4312011994ec2658a997f1781063b970865ec04"
CROSSFRAMEWORK_BLOB_SHA = "07016d497a4f0139db6c9bf02c72f9563c305e3d"
CUDAQ_TWOQUBIT_BLOB_SHA = "6fb7a3e19abf0e1d6e92e60f72b72357630be3af"

FORMAL_SOURCE_HEAD = "a841235b4d49f8399aa7f796493caef5dcfbea07"
FORMAL_SOURCE_PATH = (
    "sovereign-omega-v2/formal/bridges/lean/GravityQuantumPureProductV1.lean"
)
FORMAL_SOURCE_BLOB_SHA = "6d1eb047c932a4e7e512d62632de905da40f61bf"
FORMAL_THEOREM = "coeffDet_eq_zero_iff_pureProductCoeffs"
FORMAL_HOSTED_RUN_ID = 35_751_545_659
FORMAL_HOSTED_STATUS = "ZERO_STEP_INFRASTRUCTURE_FAILURE"


def _scaled_to_float(value: int, scale: int) -> float:
    return value / float(scale)


def _to_value_scale(value: float) -> int:
    return int(round(float(value) * VALUE_SCALE))


def _require_time_scaled(time_scaled: int) -> int:
    if type(time_scaled) is not int:
        raise ValueError("TIME_SCALED_MUST_BE_INTEGER")
    return time_scaled


def _parameters(time_scaled: int) -> tuple[float, float, float, float]:
    time_scaled = _require_time_scaled(time_scaled)
    t = _scaled_to_float(time_scaled, TIME_SCALE)
    j = _scaled_to_float(INTERACTION_J_SCALED, COEFFICIENT_SCALE)
    h0 = _scaled_to_float(FIELD0_SCALED, COEFFICIENT_SCALE)
    h1 = _scaled_to_float(FIELD1_SCALED, COEFFICIENT_SCALE)
    return t, j, h0, h1


def build_qiskit_circuit(time_scaled: int) -> QuantumCircuit:
    """Build the same |++> Ising evolution used by the CUDA-Q witness."""
    t, j, h0, h1 = _parameters(time_scaled)
    circuit = QuantumCircuit(2, name=f"aegis_ising_t_{time_scaled}")
    circuit.h(0)
    circuit.h(1)
    circuit.rz(2.0 * h0 * t, 0)
    circuit.rz(2.0 * h1 * t, 1)
    circuit.cx(0, 1)
    circuit.rz(2.0 * j * t, 1)
    circuit.cx(0, 1)
    return circuit


def qpy_roundtrip_bytes(circuit: QuantumCircuit) -> tuple[bytes, QuantumCircuit]:
    """Serialize to pinned QPY v17, reload, and require exact circuit equality."""
    first = io.BytesIO()
    qpy.dump(circuit, first, version=QPY_FORMAT_VERSION)
    payload = first.getvalue()

    second = io.BytesIO(payload)
    restored_programs = qpy.load(second)
    if len(restored_programs) != 1:
        raise ValueError("QPY_PROGRAM_COUNT_MISMATCH")
    restored = restored_programs[0]
    if restored != circuit:
        raise ValueError("QPY_ROUNDTRIP_MISMATCH")

    repeat = io.BytesIO()
    qpy.dump(circuit, repeat, version=QPY_FORMAT_VERSION)
    if repeat.getvalue() != payload:
        raise ValueError("QPY_NONDETERMINISTIC_IN_PINNED_ENVIRONMENT")

    return payload, restored


def _analytic_observables_scaled(time_scaled: int) -> tuple[int, int]:
    t, j, h0, h1 = _parameters(time_scaled)
    x0 = math.cos(2.0 * h0 * t) * math.cos(2.0 * j * t)
    x1 = math.cos(2.0 * h1 * t) * math.cos(2.0 * j * t)
    return _to_value_scale(x0), _to_value_scale(x1)


def qiskit_statevector_point(time_scaled: int) -> dict[str, Any]:
    circuit = build_qiskit_circuit(time_scaled)
    qpy_payload, restored = qpy_roundtrip_bytes(circuit)
    state = Statevector.from_instruction(restored)

    # Qiskit Pauli labels are ordered q1 q0, so IX = X on q0 and XI = X on q1.
    x0 = float(state.expectation_value(SparsePauliOp.from_list([("IX", 1.0)])).real)
    x1 = float(state.expectation_value(SparsePauliOp.from_list([("XI", 1.0)])).real)

    amplitudes = tuple(complex(v) for v in state.data)
    if len(amplitudes) != 4:
        raise ValueError("EXPECTED_TWO_QUBIT_STATEVECTOR")

    coeff_det = amplitudes[0] * amplitudes[3] - amplitudes[1] * amplitudes[2]
    det_abs = abs(coeff_det)
    det_abs_scaled = int(round(det_abs * DET_SCALE))
    concurrence_scaled = int(round(min(1.0, 2.0 * det_abs) * DET_SCALE))
    pure_product = det_abs_scaled <= DET_TOLERANCE_SCALED

    return {
        "time_scaled": time_scaled,
        "qiskit_x0_scaled": _to_value_scale(x0),
        "qiskit_x1_scaled": _to_value_scale(x1),
        "coeff_det_abs_scaled": det_abs_scaled,
        "concurrence_scaled": concurrence_scaled,
        "pure_product_within_tolerance": pure_product,
        "det_tolerance_scaled": DET_TOLERANCE_SCALED,
        "qpy_sha256": hashlib.sha256(qpy_payload).hexdigest(),
        "qpy_size_bytes": len(qpy_payload),
        "qpy_format_version": QPY_FORMAT_VERSION,
        "qpy_roundtrip_equal": True,
    }


def build_curriculum_record(
    time_scaled: int,
    source_head_sha: str = PARENT_CROSSFRAMEWORK_HEAD,
) -> dict[str, Any]:
    analytic_x0, analytic_x1 = _analytic_observables_scaled(time_scaled)
    cudaq_point = run_dynamics_point(time_scaled)
    pennylane_point = pennylane_dynamics_point(time_scaled)
    qiskit_point = qiskit_statevector_point(time_scaled)

    values_x0 = (
        analytic_x0,
        int(cudaq_point["cudaq_x0_scaled"]),
        int(pennylane_point["pennylane_x0_scaled"]),
        int(qiskit_point["qiskit_x0_scaled"]),
    )
    values_x1 = (
        analytic_x1,
        int(cudaq_point["cudaq_x1_scaled"]),
        int(pennylane_point["pennylane_x1_scaled"]),
        int(qiskit_point["qiskit_x1_scaled"]),
    )

    max_delta_x0 = max(values_x0) - min(values_x0)
    max_delta_x1 = max(values_x1) - min(values_x1)
    framework_agreement = (
        max_delta_x0 <= DYNAMICS_TOLERANCE_SCALED
        and max_delta_x1 <= DYNAMICS_TOLERANCE_SCALED
        and bool(cudaq_point["within_tolerance"])
        and bool(pennylane_point["within_tolerance"])
        and bool(qiskit_point["qpy_roundtrip_equal"])
    )

    qiskit_version = importlib.metadata.version("qiskit")
    version_ok = qiskit_version == EXPECTED_QISKIT_VERSION

    t, j, h0, h1 = _parameters(time_scaled)
    label = (
        "PURE_PRODUCT"
        if qiskit_point["pure_product_within_tolerance"]
        else "ENTANGLED_PURE_STATE"
    )

    analytic_row = {
        "x0_scaled": analytic_x0,
        "x1_scaled": analytic_x1,
    }
    cudaq_matches = (
        bool(cudaq_point["within_tolerance"])
        and abs(int(cudaq_point["cudaq_x0_scaled"]) - analytic_x0)
            <= DYNAMICS_TOLERANCE_SCALED
        and abs(int(cudaq_point["cudaq_x1_scaled"]) - analytic_x1)
            <= DYNAMICS_TOLERANCE_SCALED
    )
    pennylane_matches = (
        bool(pennylane_point["within_tolerance"])
        and abs(int(pennylane_point["pennylane_x0_scaled"]) - analytic_x0)
            <= DYNAMICS_TOLERANCE_SCALED
        and abs(int(pennylane_point["pennylane_x1_scaled"]) - analytic_x1)
            <= DYNAMICS_TOLERANCE_SCALED
    )
    qiskit_matches = (
        bool(qiskit_point["qpy_roundtrip_equal"])
        and abs(int(qiskit_point["qiskit_x0_scaled"]) - analytic_x0)
            <= DYNAMICS_TOLERANCE_SCALED
        and abs(int(qiskit_point["qiskit_x1_scaled"]) - analytic_x1)
            <= DYNAMICS_TOLERANCE_SCALED
        and version_ok
    )

    def runtime_witness(
        name: str,
        group: str,
        source_ref: str,
        row: dict[str, Any],
        matches: bool,
    ) -> Witness:
        return Witness(
            name=name,
            status=WitnessStatus.VERIFIED if matches else WitnessStatus.FAILED,
            independence_group=group,
            source_ref=source_ref,
            evidence_sha256=sha256_hex(canonical_json_bytes(row)) if matches else "",
            failure_kind=(
                FailureKind.NONE if matches
                else FailureKind.SEMANTIC_DISAGREEMENT
            ),
            detail="" if matches else "observable disagreement beyond tolerance",
        )

    witnesses = [
        Witness(
            name="analytic_oracle",
            status=WitnessStatus.VERIFIED,
            independence_group="analytic_closed_form",
            source_ref=(
                f"Aegis-Omega/AEGIS-OMEGA@{PARENT_CROSSFRAMEWORK_HEAD}:"
                "gravity_quantum/crossframework_v1.py#analytic"
            ),
            evidence_sha256=sha256_hex(canonical_json_bytes(analytic_row)),
        ),
        runtime_witness(
            "cudaq_qpp_cpu",
            "cudaq",
            (
                f"Aegis-Omega/AEGIS-OMEGA@{PARENT_CROSSFRAMEWORK_HEAD}:"
                "gravity_quantum/cudaq_twoqubit_v1.py"
            ),
            dict(cudaq_point),
            cudaq_matches,
        ),
        runtime_witness(
            "pennylane_default_qubit",
            "pennylane",
            (
                f"Aegis-Omega/AEGIS-OMEGA@{PARENT_CROSSFRAMEWORK_HEAD}:"
                "gravity_quantum/crossframework_v1.py#pennylane"
            ),
            dict(pennylane_point),
            pennylane_matches,
        ),
        runtime_witness(
            "qiskit_qpy_statevector",
            "qiskit_qpy",
            (
                f"Aegis-Omega/AEGIS-OMEGA@{source_head_sha}:"
                "gravity_quantum/qpy_curriculum_v1.py"
            ),
            dict(qiskit_point),
            qiskit_matches,
        ),
        Witness(
            name="lean_pure_product_kernel",
            status=WitnessStatus.FAILED,
            independence_group="lean_kernel",
            required=True,
            formal_kernel=True,
            source_ref=(
                f"Aegis-Omega/AEGIS-OMEGA@{FORMAL_SOURCE_HEAD}:"
                f"{FORMAL_SOURCE_PATH}#{FORMAL_THEOREM}"
            ),
            failure_kind=FailureKind.INFRASTRUCTURE,
            detail=(
                f"hosted_run={FORMAL_HOSTED_RUN_ID};"
                f"status={FORMAL_HOSTED_STATUS};steps=0"
            ),
        ),
    ]

    evidence_gradient = compile_evidence_gradient(
        example_id=f"ising-2q-t-{time_scaled}",
        source_head_sha=source_head_sha,
        witnesses=witnesses,
        representation=qiskit_point["qpy_sha256"].encode("ascii"),
        policy=CompilerPolicy(
            min_independent_groups=4,
            formal_kernel_required=True,
        ),
        metadata={
            "framework_agreement": framework_agreement,
            "qiskit_version_pinned": version_ok,
        },
    )

    return {
        "schema": SCHEMA,
        "example_id": f"ising-2q-t-{time_scaled}",
        "task_family": "MULTI_REPRESENTATION_QUANTUM_REASONING",
        "instruction": (
            "For H = 0.7 Z0Z1 + 0.2 Z0 - 0.1 Z1 and initial state |++>, "
            f"at scaled time {time_scaled}, predict <X0>, <X1>, and classify "
            "whether the resulting pure two-qubit state is a product state."
        ),
        "inputs": {
            "time_scaled": time_scaled,
            "time_scale": TIME_SCALE,
            "time_float": t,
            "interaction_j": j,
            "field_0": h0,
            "field_1": h1,
        },
        "targets": {
            "x0_scaled": analytic_x0,
            "x1_scaled": analytic_x1,
            "value_scale": VALUE_SCALE,
            "state_class": label,
            "coeff_det_abs_scaled": qiskit_point["coeff_det_abs_scaled"],
            "concurrence_scaled": qiskit_point["concurrence_scaled"],
            "det_scale": DET_SCALE,
        },
        "representations": {
            "qpy_sha256": qiskit_point["qpy_sha256"],
            "qpy_size_bytes": qiskit_point["qpy_size_bytes"],
            "qpy_format_version": QPY_FORMAT_VERSION,
            "qiskit_version": qiskit_version,
        },
        "framework_observables": {
            "analytic": {"x0_scaled": analytic_x0, "x1_scaled": analytic_x1},
            "cudaq": {
                "x0_scaled": cudaq_point["cudaq_x0_scaled"],
                "x1_scaled": cudaq_point["cudaq_x1_scaled"],
            },
            "pennylane": {
                "x0_scaled": pennylane_point["pennylane_x0_scaled"],
                "x1_scaled": pennylane_point["pennylane_x1_scaled"],
            },
            "qiskit": {
                "x0_scaled": qiskit_point["qiskit_x0_scaled"],
                "x1_scaled": qiskit_point["qiskit_x1_scaled"],
            },
        },
        "formal_invariant": {
            "source_head": FORMAL_SOURCE_HEAD,
            "source_path": FORMAL_SOURCE_PATH,
            "source_blob_sha": FORMAL_SOURCE_BLOB_SHA,
            "theorem": FORMAL_THEOREM,
            "meaning": "coeffDet = 0 iff the pure two-qubit coefficient tensor is a product state",
            "hosted_run_id": FORMAL_HOSTED_RUN_ID,
            "hosted_status": FORMAL_HOSTED_STATUS,
            "kernel_verified": False,
        },
        "provenance": {
            "parent_crossframework_head": PARENT_CROSSFRAMEWORK_HEAD,
            "crossframework_blob_sha": CROSSFRAMEWORK_BLOB_SHA,
            "cudaq_twoqubit_blob_sha": CUDAQ_TWOQUBIT_BLOB_SHA,
        },
        "checks": {
            "framework_agreement": framework_agreement,
            "max_delta_x0_scaled": max_delta_x0,
            "max_delta_x1_scaled": max_delta_x1,
            "tolerance_scaled": DYNAMICS_TOLERANCE_SCALED,
            "qpy_roundtrip_equal": qiskit_point["qpy_roundtrip_equal"],
            "qiskit_version_pinned": version_ok,
        },
        "training": {
            "disposition": evidence_gradient["disposition"],
            "gradient_admissible": (
                evidence_gradient["disposition"]
                == LearningDisposition.POSITIVE.value
            ),
            "training_weight_ppm": evidence_gradient[
                "positive_gradient_weight_ppm"
            ],
            "contrastive_weight_ppm": evidence_gradient[
                "contrastive_weight_ppm"
            ],
            "sampling_priority_ppm": evidence_gradient[
                "sampling_priority_ppm"
            ],
            "evidence_gradient_receipt_sha256": evidence_gradient[
                "receipt_sha256"
            ],
            "rule": "NO_POSITIVE_GRADIENT_WITHOUT_COMPLETE_WITNESS",
        },
        "evidence_gradient": evidence_gradient,
        "scope": "RESEARCH_ONLY_TRAINING_DATA",
        "authority_effect": "NONE",
        "physics_claim_effect": "NONE",
    }


def _normalize_source_head(source_head_sha: str | None) -> str:
    if source_head_sha is None:
        return "LOCAL_UNBOUND"
    if re.fullmatch(r"[0-9a-f]{40}", source_head_sha) is None:
        raise ValueError("SOURCE_HEAD_SHA_MUST_BE_LOWERCASE_HEX40")
    return source_head_sha


def build_curriculum_receipt(source_head_sha: str | None = None) -> dict[str, Any]:
    source_head = _normalize_source_head(source_head_sha)
    qiskit_version = importlib.metadata.version("qiskit")
    if qiskit_version != EXPECTED_QISKIT_VERSION:
        raise ValueError("UNEXPECTED_QISKIT_VERSION")

    records = [
        build_curriculum_record(t, source_head)
        for t in DEFAULT_TIME_SCALED
    ]
    positive_count = sum(
        1 for record in records
        if record["training"]["disposition"] == LearningDisposition.POSITIVE.value
    )
    contrastive_count = sum(
        1 for record in records
        if record["training"]["disposition"]
        == LearningDisposition.CONTRASTIVE_ONLY.value
    )
    quarantine_count = len(records) - positive_count - contrastive_count

    return {
        "schema": SCHEMA,
        "scope": "RESEARCH_ONLY_PROOF_CARRYING_CURRICULUM",
        "source_head_sha": source_head,
        "record_count": len(records),
        "qiskit_version": qiskit_version,
        "qpy_format_version": QPY_FORMAT_VERSION,
        "parent_crossframework_head": PARENT_CROSSFRAMEWORK_HEAD,
        "formal_source_head": FORMAL_SOURCE_HEAD,
        "formal_source_blob_sha": FORMAL_SOURCE_BLOB_SHA,
        "formal_theorem": FORMAL_THEOREM,
        "records": records,
        "positive_gradient_count": positive_count,
        "contrastive_count": contrastive_count,
        "quarantine_count": quarantine_count,
        "all_gradient_admissible": positive_count == len(records),
        "formal_kernel_verified": False,
        "weakest_transition": FORMAL_HOSTED_STATUS,
        "authority_effect": "NONE",
        "physics_claim_effect": "NONE",
    }


def emit_bundle(output_dir: Path, source_head_sha: str | None = None) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    receipt = build_curriculum_receipt(source_head_sha)

    curriculum_path = output_dir / "curriculum.jsonl"
    positive_path = output_dir / "positive.jsonl"
    contrastive_path = output_dir / "contrastive.jsonl"
    quarantine_path = output_dir / "quarantine.jsonl"

    handles = {
        LearningDisposition.POSITIVE.value:
            positive_path.open("w", encoding="utf-8"),
        LearningDisposition.CONTRASTIVE_ONLY.value:
            contrastive_path.open("w", encoding="utf-8"),
        LearningDisposition.QUARANTINE.value:
            quarantine_path.open("w", encoding="utf-8"),
    }
    try:
        with curriculum_path.open("w", encoding="utf-8") as handle:
            for record in receipt["records"]:
                line = json.dumps(
                    record, sort_keys=True, separators=(",", ":")
                ) + "\n"
                handle.write(line)
                handles[record["training"]["disposition"]].write(line)
    finally:
        for partition_handle in handles.values():
            partition_handle.close()

    qpy_artifacts: dict[str, str] = {}
    for time_scaled in DEFAULT_TIME_SCALED:
        payload, _ = qpy_roundtrip_bytes(build_qiskit_circuit(time_scaled))
        name = f"ising-2q-t-{time_scaled}.qpy"
        path = output_dir / name
        path.write_bytes(payload)
        qpy_artifacts[name] = hashlib.sha256(payload).hexdigest()

    receipt["qpy_artifacts"] = qpy_artifacts
    receipt_path = output_dir / "receipt.json"
    receipt_path.write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return receipt


if __name__ == "__main__":
    print(json.dumps(build_curriculum_receipt(), indent=2, sort_keys=True))
