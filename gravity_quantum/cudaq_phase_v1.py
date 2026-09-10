#!/usr/bin/env python3
"""AEGIS Ω CUDA-Q phase/Hamiltonian computational cross-check.

This module validates a deliberately small identity:

    H = Z / 2
    U(theta) = exp(-i * theta * Z / 2) = RZ(theta)
    |psi(0)> = |+>
    <X>(theta) = cos(theta)

The CUDA-Q result is a computational cross-check only. It carries no empirical
physics authority and does not test quantum gravity.
"""
from __future__ import annotations

import importlib.metadata
import json
import math

import cudaq
from cudaq import spin

SCHEMA = "AEGIS_CUDAQ_PHASE_HAMILTONIAN_V1"
EXPECTATION_SCALE = 1_000_000_000_000
TOLERANCE_SCALED = 1_000
DEFAULT_ANGLE_MICRORAD = (0, 250_000, 500_000, 1_000_000, 1_570_796)

cudaq.set_target("qpp-cpu")


@cudaq.kernel
def phase_kernel(theta: float):
    q = cudaq.qubit()
    h(q)
    rz(theta, q)


def _require_angle_microrad(angle_microrad: int) -> int:
    if type(angle_microrad) is not int:
        raise ValueError("ANGLE_MICRORAD_MUST_BE_INTEGER")
    return angle_microrad


def _scaled_expectation(value: float) -> int:
    return int(round(value * EXPECTATION_SCALE))


def classical_x_expectation_scaled(angle_microrad: int) -> int:
    angle_microrad = _require_angle_microrad(angle_microrad)
    theta = angle_microrad / 1_000_000.0
    return _scaled_expectation(math.cos(theta))


def run_phase_probe(angle_microrad: int) -> dict:
    angle_microrad = _require_angle_microrad(angle_microrad)
    theta = angle_microrad / 1_000_000.0
    classical_scaled = classical_x_expectation_scaled(angle_microrad)
    cudaq_expectation = cudaq.observe(phase_kernel, spin.x(0), theta).expectation()
    cudaq_scaled = _scaled_expectation(cudaq_expectation)
    return {
        "angle_microrad": angle_microrad,
        "classical_x_scaled": classical_scaled,
        "cudaq_x_scaled": cudaq_scaled,
        "abs_error_scaled": abs(cudaq_scaled - classical_scaled),
        "tolerance_scaled": TOLERANCE_SCALED,
        "within_tolerance": abs(cudaq_scaled - classical_scaled) <= TOLERANCE_SCALED,
    }


def build_phase_receipt() -> dict:
    points = [run_phase_probe(angle) for angle in DEFAULT_ANGLE_MICRORAD]
    all_within = all(point["within_tolerance"] for point in points)
    if not all_within:
        raise ValueError("CUDAQ_PHASE_CROSSCHECK_OUTSIDE_TOLERANCE")
    return {
        "schema": SCHEMA,
        "scope": "RESEARCH_ONLY_COMPUTATIONAL_CROSSCHECK",
        "cudaq_version": importlib.metadata.version("cudaq"),
        "target": "qpp-cpu",
        "hamiltonian": "H=Z/2",
        "unitary": "U(theta)=exp(-i*theta*Z/2)=RZ(theta)",
        "initial_state": "|+>",
        "observable": "X",
        "classical_oracle": "<X>(theta)=cos(theta)",
        "angle_unit": "microradian",
        "expectation_scale": EXPECTATION_SCALE,
        "tolerance_scaled": TOLERANCE_SCALED,
        "shots_count": "ANALYTIC_OBSERVE_NO_SHOTS",
        "points": points,
        "checks": {
            "all_points_within_tolerance": all_within,
            "integer_scaled_receipt": True,
            "analytic_observe": True,
        },
        "gpu_acceleration_tested": False,
        "qpu_hardware_tested": False,
        "empirical_data_used": False,
        "quantum_gravity_status": "NOT_TESTED",
        "physics_claim_effect": "NONE",
        "authority_effect": "NONE",
    }


if __name__ == "__main__":
    print(json.dumps(build_phase_receipt(), indent=2, sort_keys=True))
