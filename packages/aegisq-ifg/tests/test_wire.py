"""Wire adversarial controls plus an independently specified stationary fixture."""

from dataclasses import asdict
import json
from pathlib import Path
import platform
import subprocess
import sys
import unittest

import numpy as np
import scipy

from aegisq_ifg.physics import IndependentFalsificationGate, PhysicsPolicy
from run_ifg import MAX_INPUT_BYTES, process_bytes


RUNNER = Path(__file__).resolve().parents[1] / "run_ifg.py"


def pair(value):
    array = np.asarray(value, dtype=complex)
    return {"real": array.real.tolist(), "imag": array.imag.tolist()}


def fixture():
    # |1><1| is stationary under H=0 with no jumps. The six-outcome Pauli
    # measurement is informationally complete, with analytically known weights.
    identity = np.eye(2)
    axes = (np.array([[0, 1], [1, 0]]), np.array([[0, -1j], [1j, 0]]), np.diag([1, -1]))
    povm = [(identity + sign * axis) / 6 for axis in axes for sign in (1, -1)]
    return {
        "raw": {
            "schema_version": "AEGISQ_STATE_OBSERVATION_V1",
            "source_kind": "SYNTHETIC_VALIDATION",
            "time_unit": "second",
            "times_seconds": [0, 0.01, 0.02],
            "rho": pair([np.diag([0, 1])] * 3),
            "probabilities": [[1/6, 1/6, 1/6, 1/6, 0, 1/3]] * 3,
        },
        "model": {
            "schema_version": "AEGISQ_GKSL_MODEL_V1",
            "hamiltonian": pair(np.zeros((2, 2))),
            "jumps": {"real": [], "imag": []},
            "povm": pair(povm),
        },
        "policy": asdict(PhysicsPolicy()),
    }


def encode(value):
    return json.dumps(value, allow_nan=False).encode("utf-8")


class WireTests(unittest.TestCase):
    def assertWireDenied(self, data, reason):
        result, code = process_bytes(data)
        self.assertEqual(code, 2, result)
        self.assertEqual(result["status"], "DENY")
        self.assertEqual(result["reasons"], [reason])
        self.assertFalse(result["clinical_admission"])
        json.dumps(result, allow_nan=False)
        return result

    def test_isolated_subprocess_recomputes_stationary_fock_case(self):
        value = fixture()
        process = subprocess.run([sys.executable, "-I", str(RUNNER)], input=encode(value),
                                 capture_output=True, check=False, cwd="/")
        self.assertEqual(process.returncode, 0, process.stderr)
        result = json.loads(process.stdout)
        self.assertEqual(result["status"], "PASS_RESEARCH_ONLY", result)
        self.assertEqual(result["metrics"]["measurement_rank"], 3)
        self.assertEqual(result["metrics"]["max_transition_residual"], 0)
        self.assertFalse(result["clinical_admission"])

        def unpack(value):
            return np.asarray(value["real"]) + 1j * np.asarray(value["imag"])

        raw, model = value["raw"], value["model"]
        expected = IndependentFalsificationGate(PhysicsPolicy(**value["policy"])).evaluate(
            unpack(raw["rho"]), raw["times_seconds"], unpack(model["hamiltonian"]),
            [], povm=unpack(model["povm"]), probabilities=raw["probabilities"],
        )
        self.assertEqual(result, expected)

    def test_identity_is_available_in_isolated_mode(self):
        process = subprocess.run([sys.executable, "-I", str(RUNNER), "--identity"],
                                 capture_output=True, check=False, cwd="/")
        self.assertEqual(process.returncode, 0, process.stderr)
        self.assertEqual(json.loads(process.stdout), {
            "python_version": platform.python_version(),
            "numpy_version": np.__version__, "scipy_version": scipy.__version__,
        })

    def test_computed_physical_denial_exits_zero(self):
        value = fixture()
        value["raw"]["rho"]["real"][1] = [[-0.01, 0], [0, 1.01]]
        result, code = process_bytes(encode(value))
        self.assertEqual(code, 0)
        self.assertIn("PSD_VIOLATION", result["reasons"])
        self.assertEqual(result["status"], "DENY")

    def test_precomputed_pass_and_extra_fields_are_rejected(self):
        for target in ("top", "raw", "model", "policy", "rho", "diagnosis"):
            with self.subTest(target=target):
                value = fixture()
                container = value if target in ("top", "diagnosis") else (
                    value["raw"]["rho"] if target == "rho" else value[target])
                container["status" if target != "diagnosis" else "diagnosis"] = "PASS_RESEARCH_ONLY"
                self.assertWireDenied(encode(value), "WIRE_SCHEMA_INVALID")

    def test_all_policy_fields_are_required_and_validation_is_explicit(self):
        for name in fixture()["policy"]:
            value = fixture()
            del value["policy"][name]
            result = self.assertWireDenied(encode(value), "WIRE_SCHEMA_INVALID")
            self.assertIsNone(result["policy"])
        for name, invalid in (("max_dimension", 16.0), ("trace_tolerance", True),
                              ("transition_residual", 0), ("identifiability_rtol", 1)):
            value = fixture()
            value["policy"][name] = invalid
            result = self.assertWireDenied(encode(value), "WIRE_POLICY_INVALID")
            self.assertIsNone(result["policy"])

    def test_schema_versions_time_unit_and_source_are_required(self):
        for section, name, invalid in (
            ("raw", "schema_version", "AEGISQ_STATE_OBSERVATION_V2"),
            ("model", "schema_version", "AEGISQ_GKSL_MODEL_V2"),
            ("raw", "time_unit", "millisecond"), ("raw", "time_unit", 1),
            ("raw", "source_kind", "CLINICAL_VALIDATION"), ("raw", "source_kind", []),
        ):
            value = fixture()
            value[section][name] = invalid
            result = self.assertWireDenied(encode(value), "WIRE_SCHEMA_INVALID")
            self.assertEqual(result["policy"], value["policy"])

    def test_complex_parts_never_broadcast(self):
        for field, section in (("rho", "raw"), ("hamiltonian", "model"),
                               ("jumps", "model"), ("povm", "model")):
            value = fixture()
            value[section][field]["imag"] = [0]
            self.assertWireDenied(encode(value), "WIRE_COMPLEX_SHAPE_MISMATCH")

    def test_numeric_arrays_reject_bool_string_null_and_ragged_rows(self):
        for invalid in (True, "0", None):
            value = fixture()
            value["raw"]["times_seconds"][0] = invalid
            self.assertWireDenied(encode(value), "WIRE_ARRAY_NON_NUMERIC")
        value = fixture()
        value["raw"]["rho"]["real"][0][0].append(0)
        self.assertWireDenied(encode(value), "WIRE_ARRAY_INVALID")

    def test_array_dimensions_and_correspondence_are_checked(self):
        for field, section, invalid, reason in (
            ("rho", "raw", pair(np.eye(2)), "WIRE_STATE_SHAPE_INVALID"),
            ("times_seconds", "raw", [0, 1], "WIRE_TIME_SHAPE_INVALID"),
            ("hamiltonian", "model", pair(np.eye(3)), "WIRE_HAMILTONIAN_SHAPE_INVALID"),
            ("jumps", "model", pair(np.eye(2)), "WIRE_JUMP_SHAPE_INVALID"),
            ("povm", "model", pair(np.eye(2)), "WIRE_POVM_SHAPE_INVALID"),
            ("probabilities", "raw", [[0.5, 0.5]] * 3, "WIRE_PROBABILITY_SHAPE_INVALID"),
        ):
            value = fixture()
            value[section][field] = invalid
            self.assertWireDenied(encode(value), reason)

    def test_json_parser_rejects_constants_overflow_and_unsafe_integers(self):
        for token in (b"NaN", b"Infinity", b"-Infinity", b"1e400"):
            self.assertWireDenied(b'{"raw":' + token + b'}', "NONFINITE_JSON_NUMBER")
        for token in (b"9007199254740992", b"-9007199254740992", b"9007199254740992.0"):
            self.assertWireDenied(b'{"raw":' + token + b'}', "UNSAFE_JSON_INTEGER")

    def test_duplicate_keys_at_any_depth_are_rejected(self):
        for data in (b'{"raw":{},"raw":{}}', b'{"raw":{"rho":{"real":[],"real":[]}}}'):
            self.assertWireDenied(data, "DUPLICATE_JSON_KEY")

    def test_invalid_json_encoding_and_nonascii_strings_are_rejected(self):
        for data in (b"{", b"{}{}", b"\xff", b"", b"[" * 2000):
            self.assertWireDenied(data, "JSON_WIRE_INVALID")
        for data in (b'{"raw":"\\u00e9"}', b'{"\\u03c1":0}'):
            self.assertWireDenied(data, "NON_ASCII_JSON_STRING")

    def test_input_size_bound(self):
        self.assertWireDenied(b" " * (MAX_INPUT_BYTES + 1), "WIRE_INPUT_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
