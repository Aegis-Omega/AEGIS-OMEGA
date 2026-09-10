#!/usr/bin/env python3
"""Strict JSON stdin/stdout adapter for the finite AegisQ research gate.

No supplied decision is trusted. The caller binds these source bytes, the
interpreter, dependencies, observations, model, and complete numerical policy.
"""

from dataclasses import asdict, fields
import json
import math
from pathlib import Path
import platform
import sys

# -I deliberately excludes the script directory from the import search path.
sys.path.insert(0, str(Path(__file__).resolve().parent))

import numpy as np  # noqa: E402
import scipy  # noqa: E402

from aegisq_ifg.physics import IndependentFalsificationGate, PhysicsPolicy  # noqa: E402


MAX_INPUT_BYTES = 8 * 1024 * 1024
MAX_SAFE_INTEGER = 2**53 - 1
SCOPE = "FINITE_SAMPLED_MODEL_CONSISTENCY_ONLY"


class WireError(ValueError):
    """Fixed machine-readable wire rejection code."""


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise WireError("DUPLICATE_JSON_KEY")
        result[key] = value
    return result


def _constant(_value):
    raise WireError("NONFINITE_JSON_NUMBER")


def _json_values(value):
    """Keep JSON values inside the trusted TypeScript caller's numeric domain."""
    if isinstance(value, str):
        if not value.isascii():
            raise WireError("NON_ASCII_JSON_STRING")
    elif type(value) in (int, float):
        if not math.isfinite(value):
            raise WireError("NONFINITE_JSON_NUMBER")
        if abs(value) > MAX_SAFE_INTEGER and (type(value) is int or value.is_integer()):
            raise WireError("UNSAFE_JSON_INTEGER")
    elif isinstance(value, dict):
        for key, item in value.items():
            _json_values(key)
            _json_values(item)
    elif isinstance(value, list):
        for item in value:
            _json_values(item)


def _keys(value, expected):
    if type(value) is not dict or set(value) != set(expected):
        raise WireError("WIRE_SCHEMA_INVALID")


def _real_array(value):
    if type(value) is not list:
        raise WireError("WIRE_ARRAY_INVALID")

    def numeric_leaves(node):
        if type(node) is list:
            for item in node:
                numeric_leaves(item)
        elif type(node) not in (int, float):
            raise WireError("WIRE_ARRAY_NON_NUMERIC")

    numeric_leaves(value)
    try:
        array = np.asarray(value, dtype=np.float64)
    except (ValueError, TypeError, OverflowError) as exc:
        raise WireError("WIRE_ARRAY_INVALID") from exc
    if not np.all(np.isfinite(array)):
        raise WireError("NONFINITE_JSON_NUMBER")
    return array


def _complex_array(value):
    _keys(value, ("real", "imag"))
    real, imag = _real_array(value["real"]), _real_array(value["imag"])
    if real.shape != imag.shape:
        raise WireError("WIRE_COMPLEX_SHAPE_MISMATCH")
    return real + 1j * imag


def _denial(code, policy=None):
    return {
        "status": "DENY",
        "reasons": [code],
        "metrics": {},
        "policy": None if policy is None else asdict(policy),
        "scope": SCOPE,
        "calibration_authority": "NOT_VERIFIED_BY_THIS_MODULE",
        "clinical_admission": False,
        "quantum_nonclassicality": "NOT_TESTED_BY_PHYSICAL_GATE",
    }


def process_bytes(data):
    """Return (result, exit code); wire errors exit 2, computed decisions exit 0."""
    policy = None
    try:
        if len(data) > MAX_INPUT_BYTES:
            raise WireError("WIRE_INPUT_TOO_LARGE")
        try:
            payload = json.loads(data.decode("utf-8"), object_pairs_hook=_object,
                                 parse_constant=_constant)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise WireError("JSON_WIRE_INVALID") from exc
        _json_values(payload)
        _keys(payload, ("raw", "model", "policy"))
        _keys(payload["policy"], [field.name for field in fields(PhysicsPolicy)])
        try:
            policy = PhysicsPolicy(**payload["policy"])
        except (ValueError, TypeError) as exc:
            raise WireError("WIRE_POLICY_INVALID") from exc

        raw, model = payload["raw"], payload["model"]
        _keys(raw, ("schema_version", "source_kind", "time_unit", "times_seconds",
                    "rho", "probabilities"))
        _keys(model, ("schema_version", "hamiltonian", "jumps", "povm"))
        if (raw["schema_version"] != "AEGISQ_STATE_OBSERVATION_V1"
                or raw["source_kind"] not in ("SYNTHETIC_VALIDATION", "RESEARCH_MEASUREMENT")
                or raw["time_unit"] != "second"
                or model["schema_version"] != "AEGISQ_GKSL_MODEL_V1"):
            raise WireError("WIRE_SCHEMA_INVALID")
        rho = _complex_array(raw["rho"])
        times = _real_array(raw["times_seconds"])
        probabilities = _real_array(raw["probabilities"])
        hamiltonian = _complex_array(model["hamiltonian"])
        jumps = _complex_array(model["jumps"])
        povm = _complex_array(model["povm"])
        if rho.ndim != 3 or rho.shape[1] != rho.shape[2]:
            raise WireError("WIRE_STATE_SHAPE_INVALID")
        count, dimension, _ = rho.shape
        if times.shape != (count,):
            raise WireError("WIRE_TIME_SHAPE_INVALID")
        if hamiltonian.shape != (dimension, dimension):
            raise WireError("WIRE_HAMILTONIAN_SHAPE_INVALID")
        if jumps.shape != (0,) and (jumps.ndim != 3 or jumps.shape[1:] != (dimension, dimension)):
            raise WireError("WIRE_JUMP_SHAPE_INVALID")
        if povm.ndim != 3 or povm.shape[1:] != (dimension, dimension):
            raise WireError("WIRE_POVM_SHAPE_INVALID")
        if probabilities.shape != (count, povm.shape[0]):
            raise WireError("WIRE_PROBABILITY_SHAPE_INVALID")
        result = IndependentFalsificationGate(policy).evaluate(
            rho, times, hamiltonian, jumps, povm=povm, probabilities=probabilities,
        )
        return result, 0
    except WireError as exc:
        return _denial(str(exc), policy), 2
    except (RecursionError, OverflowError, ValueError):
        # Includes the JSON parser's integer-digit/depth limits. Never echo input.
        return _denial("JSON_WIRE_INVALID", policy), 2


def main():
    if sys.argv[1:] == ["--identity"]:
        result, code = {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__,
            "scipy_version": scipy.__version__,
        }, 0
    elif sys.argv[1:]:
        result, code = _denial("UNSUPPORTED_ARGUMENTS"), 2
    else:
        result, code = process_bytes(sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
    sys.stdout.write(json.dumps(result, allow_nan=False, ensure_ascii=True, separators=(",", ":")) + "\n")
    return code


if __name__ == "__main__":
    raise SystemExit(main())
