#!/usr/bin/env python3
"""AEGIS Ω quantum cross-framework witness v1.

This module replays the already-bound coupled two-qubit Ising benchmark through
an independent PennyLane implementation and compares it with both the analytic
closed-form oracle and CUDA-Q qpp-cpu results.

Computational scope only. No empirical physics claim or operational authority
is created by agreement between simulators.
"""
from __future__ import annotations

import importlib.metadata
import json
import math

import pennylane as qml

from gravity_quantum.cudaq_twoqubit_v1 import (
    COEFFICIENT_SCALE,
    DEFAULT_TIME_SCALED,
    DYNAMICS_TOLERANCE_SCALED,
    FIELD0_SCALED,
    FIELD1_SCALED,
    INTERACTION_J_SCALED,
    SPECTRUM_TOLERANCE_SCALED,
    TIME_SCALE,
    VALUE_SCALE,
    analytic_spectrum_scaled,
    cudaq_spectrum_scaled,
    run_dynamics_point,
)

SCHEMA = "AEGIS_QUANTUM_CROSS_FRAMEWORK_WITNESS_V1"
PARENT_TWOQUBIT_HEAD = "35d7aa884d17670a9bc2f8e1fdfb2b5d988f8958"
PARENT_TWOQUBIT_RECEIPT_SHA256 = "264b285e2447482d70d41da8284569ebe23897b14afe88d594b3528a49bfce8d"
EXPECTED_CUDAQ_VERSION = "0.15.1"
EXPECTED_PENNYLANE_VERSION = "0.45.1"
PENNYLANE_BACKEND = "default.qubit"


def _scaled_to_float(value: int, scale: int) -> float:
    return value / float(scale)


def _to_value_scale(value: float) -> int:
    return int(round(float(value) * VALUE_SCALE))


def _require_time_scaled(time_scaled: int) -> int:
    if type(time_scaled) is not int:
        raise ValueError("TIME_SCALED_MUST_BE_INTEGER")
    return time_scaled


def _coefficients() -> tuple[float, float, float]:
    return (
        _scaled_to_float(INTERACTION_J_SCALED, COEFFICIENT_SCALE),
        _scaled_to_float(FIELD0_SCALED, COEFFICIENT_SCALE),
        _scaled_to_float(FIELD1_SCALED, COEFFICIENT_SCALE),
    )


def _pennylane_hamiltonian():
    j, h0, h1 = _coefficients()
    return qml.Hamiltonian(
        [j, h0, h1],
        [qml.PauliZ(0) @ qml.PauliZ(1), qml.PauliZ(0), qml.PauliZ(1)],
    )


_spectrum_device = qml.device(PENNYLANE_BACKEND, wires=2, shots=None)
_dynamics_device = qml.device(PENNYLANE_BACKEND, wires=2, shots=None)


@qml.qnode(_spectrum_device)
def _basis_energy(bit0: int, bit1: int):
    if bit0:
        qml.PauliX(0)
    if bit1:
        qml.PauliX(1)
    return qml.expval(_pennylane_hamiltonian())


@qml.qnode(_dynamics_device)
def _pennylane_evolved_plus_plus(time_value: float):
    qml.Hadamard(0)
    qml.Hadamard(1)
    qml.evolve(_pennylane_hamiltonian(), coeff=time_value)
    return qml.expval(qml.PauliX(0)), qml.expval(qml.PauliX(1))


def _independent_closed_form_scaled(time_scaled: int) -> tuple[int, int]:
    time_scaled = _require_time_scaled(time_scaled)
    t = _scaled_to_float(time_scaled, TIME_SCALE)
    j, h0, h1 = _coefficients()
    x0 = math.cos(2.0 * h0 * t) * math.cos(2.0 * j * t)
    x1 = math.cos(2.0 * h1 * t) * math.cos(2.0 * j * t)
    return _to_value_scale(x0), _to_value_scale(x1)


def pennylane_spectrum_scaled() -> dict:
    basis_bits = {
        "00": (0, 0),
        "01": (0, 1),
        "10": (1, 0),
        "11": (1, 1),
    }
    return {
        basis: _to_value_scale(_basis_energy(bit0, bit1))
        for basis, (bit0, bit1) in basis_bits.items()
    }


def pennylane_dynamics_point(time_scaled: int) -> dict:
    time_scaled = _require_time_scaled(time_scaled)
    t = _scaled_to_float(time_scaled, TIME_SCALE)
    expected_x0, expected_x1 = _independent_closed_form_scaled(time_scaled)
    observed_x0, observed_x1 = _pennylane_evolved_plus_plus(t)
    pennylane_x0 = _to_value_scale(observed_x0)
    pennylane_x1 = _to_value_scale(observed_x1)
    error_x0 = abs(pennylane_x0 - expected_x0)
    error_x1 = abs(pennylane_x1 - expected_x1)
    return {
        "time_scaled": time_scaled,
        "analytic_x0_scaled": expected_x0,
        "analytic_x1_scaled": expected_x1,
        "pennylane_x0_scaled": pennylane_x0,
        "pennylane_x1_scaled": pennylane_x1,
        "abs_error_x0_scaled": error_x0,
        "abs_error_x1_scaled": error_x1,
        "tolerance_scaled": DYNAMICS_TOLERANCE_SCALED,
        "within_tolerance": (
            error_x0 <= DYNAMICS_TOLERANCE_SCALED
            and error_x1 <= DYNAMICS_TOLERANCE_SCALED
        ),
    }


def build_crossframework_receipt() -> dict:
    cudaq_version = importlib.metadata.version("cudaq")
    pennylane_version = importlib.metadata.version("pennylane")
    if cudaq_version != EXPECTED_CUDAQ_VERSION:
        raise ValueError("UNEXPECTED_CUDAQ_VERSION")
    if pennylane_version != EXPECTED_PENNYLANE_VERSION:
        raise ValueError("UNEXPECTED_PENNYLANE_VERSION")

    analytic = analytic_spectrum_scaled()["by_basis"]
    cudaq_values = cudaq_spectrum_scaled()
    pennylane_values = pennylane_spectrum_scaled()

    spectrum = []
    spectrum_ok = True
    for basis in ("00", "01", "10", "11"):
        cudaq_error = abs(cudaq_values[basis] - analytic[basis])
        pennylane_error = abs(pennylane_values[basis] - analytic[basis])
        framework_delta = abs(cudaq_values[basis] - pennylane_values[basis])
        point_ok = (
            cudaq_error <= SPECTRUM_TOLERANCE_SCALED
            and pennylane_error <= SPECTRUM_TOLERANCE_SCALED
            and framework_delta <= SPECTRUM_TOLERANCE_SCALED
        )
        spectrum_ok = spectrum_ok and point_ok
        spectrum.append(
            {
                "basis": basis,
                "analytic_energy_scaled": analytic[basis],
                "cudaq_energy_scaled": cudaq_values[basis],
                "pennylane_energy_scaled": pennylane_values[basis],
                "cudaq_abs_error_scaled": cudaq_error,
                "pennylane_abs_error_scaled": pennylane_error,
                "cross_framework_delta_scaled": framework_delta,
                "tolerance_scaled": SPECTRUM_TOLERANCE_SCALED,
                "within_tolerance": point_ok,
            }
        )

    dynamics = []
    dynamics_ok = True
    for time_scaled in DEFAULT_TIME_SCALED:
        analytic_x0, analytic_x1 = _independent_closed_form_scaled(time_scaled)
        cudaq_point = run_dynamics_point(time_scaled)
        pennylane_point = pennylane_dynamics_point(time_scaled)
        delta_x0 = abs(
            cudaq_point["cudaq_x0_scaled"] - pennylane_point["pennylane_x0_scaled"]
        )
        delta_x1 = abs(
            cudaq_point["cudaq_x1_scaled"] - pennylane_point["pennylane_x1_scaled"]
        )
        point_ok = (
            abs(cudaq_point["cudaq_x0_scaled"] - analytic_x0) <= DYNAMICS_TOLERANCE_SCALED
            and abs(cudaq_point["cudaq_x1_scaled"] - analytic_x1) <= DYNAMICS_TOLERANCE_SCALED
            and pennylane_point["within_tolerance"]
            and delta_x0 <= DYNAMICS_TOLERANCE_SCALED
            and delta_x1 <= DYNAMICS_TOLERANCE_SCALED
        )
        dynamics_ok = dynamics_ok and point_ok
        dynamics.append(
            {
                "time_scaled": time_scaled,
                "analytic_x0_scaled": analytic_x0,
                "analytic_x1_scaled": analytic_x1,
                "cudaq_x0_scaled": cudaq_point["cudaq_x0_scaled"],
                "cudaq_x1_scaled": cudaq_point["cudaq_x1_scaled"],
                "pennylane_x0_scaled": pennylane_point["pennylane_x0_scaled"],
                "pennylane_x1_scaled": pennylane_point["pennylane_x1_scaled"],
                "cross_framework_delta_x0_scaled": delta_x0,
                "cross_framework_delta_x1_scaled": delta_x1,
                "tolerance_scaled": DYNAMICS_TOLERANCE_SCALED,
                "within_tolerance": point_ok,
            }
        )

    analytic_ok = len(set(analytic.values())) == 4
    cudaq_ok = spectrum_ok and all(point["within_tolerance"] for point in dynamics)
    pennylane_ok = spectrum_ok and all(
        pennylane_dynamics_point(t)["within_tolerance"] for t in DEFAULT_TIME_SCALED
    )
    all_ok = analytic_ok and cudaq_ok and pennylane_ok and dynamics_ok
    if not all_ok:
        raise ValueError("CROSS_FRAMEWORK_WITNESS_OUTSIDE_TOLERANCE")

    return {
        "schema": SCHEMA,
        "scope": "RESEARCH_ONLY_COMPUTATIONAL_CROSS_FRAMEWORK_WITNESS",
        "parent_twoqubit_head": PARENT_TWOQUBIT_HEAD,
        "parent_twoqubit_receipt_sha256": PARENT_TWOQUBIT_RECEIPT_SHA256,
        "cudaq_version": cudaq_version,
        "cudaq_backend": "qpp-cpu",
        "pennylane_version": pennylane_version,
        "pennylane_backend": PENNYLANE_BACKEND,
        "pennylane_evolution_primitive": "qml.evolve(H, coeff=t)",
        "hamiltonian": "H=0.7*Z0Z1+0.2*Z0-0.1*Z1",
        "parameters_scaled": {
            "interaction_j": INTERACTION_J_SCALED,
            "field_0": FIELD0_SCALED,
            "field_1": FIELD1_SCALED,
            "coefficient_scale": COEFFICIENT_SCALE,
        },
        "value_scale": VALUE_SCALE,
        "time_scale": TIME_SCALE,
        "spectrum": spectrum,
        "dynamics": dynamics,
        "checks": {
            "analytic_oracle_verified": analytic_ok,
            "cudaq_replay_verified": cudaq_ok,
            "pennylane_replay_verified": pennylane_ok,
            "cross_framework_spectrum_within_tolerance": spectrum_ok,
            "cross_framework_dynamics_within_tolerance": dynamics_ok,
            "integer_scaled_receipt": True,
        },
        "computational_status": "COMPUTATIONAL_CROSS_FRAMEWORK_REPRODUCIBLE",
        "second_environment_replay": "NOT_PERFORMED",
        "gpu_acceleration_tested": False,
        "qpu_hardware_tested": False,
        "empirical_data_used": False,
        "quantum_gravity_status": "NOT_TESTED",
        "physics_claim_effect": "NONE",
        "authority_effect": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(build_crossframework_receipt(), indent=2, sort_keys=True))
