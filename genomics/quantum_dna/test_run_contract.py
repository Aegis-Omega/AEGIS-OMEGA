"""Negative controls for physical metadata, artifact binding and causal ablations."""

import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from genomics.quantum_dna.run_contract import ContractError, classical_criteria, validate_contract


def zeros(n):
    return [["0" for _ in range(n)] for _ in range(n)]


class RunContractTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.h = zeros(6)
        self.h[0][1] = self.h[1][0] = "0.03"
        self.contract = self.fixture()

    def artifact(self, name, value):
        raw = json.dumps(value).encode()
        (self.root / name).write_bytes(raw)
        return {"path": name, "sha256": hashlib.sha256(raw).hexdigest()}

    def fixture(self, reference=False):
        n = 37 if reference else 6
        h = zeros(n) if reference else self.h
        rho = zeros(n)
        occupied = 1 if reference else 0
        rho[occupied][occupied] = "1"
        collapse = zeros(n)
        collapse[0][1] = "0.05"
        return {
            "schema": "AEGIS_QDNA_RUN_CONTRACT_V1",
            "model_id": "REFERENCE_2P_ELM_GROUND_37D" if reference else "SWEEP_ONE_HOLE_ELM_6D",
            "sequence": "GCG", "complement": "CGC",
            "site_order": [f"{strand}:{i + 1}:{base}" for strand, bases in
                           (("upper", "GCG"), ("lower", "CGC")) for i, base in enumerate(bases)],
            "hamiltonian": self.artifact("H.json", h), "rho0": self.artifact("rho.json", rho),
            "collapse_operators": [self.artifact("collapse.json", collapse)] if reference else [],
            "units": {"hamiltonian": "eV", "time": "fs", "collapse": "fs^-1/2"},
            "dephasing": {"kind": "LOCAL_PROJECTOR_PURE_DEPHASING", "gamma_eV": "0",
                          "rate_fs_inverse": "0", "hbar_eV_fs": "0.6582119569"},
            "solver": {"name": "scipy.solve_ivp:DOP853", "version": "1.17.0", "rtol": "1e-9",
                       "atol": "1e-11", "versions": {"python": "3.12.13", "qdna": "1.0.1",
                       "qutip": "5.3.1", "scipy": "1.17.0", "numpy": "2.3.5"}},
            "output_grid": {"start_fs": "0", "end_fs": "200", "count": 2001,
                            "spacing_fs": "0.1", "integration": "ADAPTIVE_INTERNAL_OUTPUT_GRID_ONLY"},
            "randomness": {"mode": "NONE_DETERMINISTIC", "seed": None},
            "interpretation": {"trap_present": reference, "temperature_K": None,
                               "biological_effect": "NOT_ESTABLISHED", "authority_promotion": False},
            "ablation": None,
        }

    def validate(self):
        return validate_contract(self.contract, self.root)

    def test_valid_sweep_and_reference(self):
        self.assertIsNone(self.validate())
        self.contract = self.fixture(reference=True)
        self.assertIsNone(self.validate())

    def test_tampered_bytes_rejected(self):
        (self.root / "H.json").write_text("[]")
        with self.assertRaisesRegex(ContractError, "digest mismatch"):
            self.validate()

    def test_unknown_fields_rejected_at_both_levels(self):
        for parent in (self.contract, self.contract["interpretation"]):
            parent["admitted"] = True
            with self.assertRaises(ContractError):
                self.validate()
            del parent["admitted"]

    def test_path_traversal_absolute_and_symlink_rejected(self):
        original = self.contract["hamiltonian"]["path"]
        (self.root / "linked.json").symlink_to(self.root / original)
        for bad in ("../H.json", str(self.root / "H.json"), "linked.json", "./H.json", "x//H.json", "a\x00b"):
            self.contract["hamiltonian"]["path"] = bad
            with self.subTest(path=bad), self.assertRaises(ContractError):
                self.validate()

    def test_model_dimensions_and_sequence_mapping_rejected(self):
        for key, value in (("model_id", "REFERENCE_2P_ELM_GROUND_37D"),
                           ("model_id", "OTHER"), ("complement", "GCG"), ("sequence", "GGG"),
                           ("site_order", list(reversed(self.contract["site_order"])))):
            changed = copy.deepcopy(self.contract)
            changed[key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_contract(changed, self.root)

    def test_hash_valid_artifacts_cannot_grant_authority_or_biology(self):
        for key, value in (("trap_present", True), ("temperature_K", "310"),
                           ("biological_effect", "VERIFIED"), ("authority_promotion", True),
                           ("authority_promotion", 0)):
            changed = copy.deepcopy(self.contract)
            changed["interpretation"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_contract(changed, self.root)

    def test_units_hbar_and_gamma_rate_binding(self):
        for key, value in (("hbar_eV_fs", "1"), ("gamma_eV", "0.1"),
                           ("gamma_eV", 0.0), ("gamma_eV", "NaN"), ("rate_fs_inverse", "-1"),
                           ("gamma_eV", "1e999999999"), ("gamma_eV", "1e-999999999"),
                           ("gamma_eV", "1e-20")):
            changed = copy.deepcopy(self.contract)
            changed["dephasing"][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_contract(changed, self.root)
        self.contract["units"]["time"] = "ps"
        with self.assertRaises(ContractError):
            self.validate()

    def test_output_grid_solver_and_randomness_required(self):
        cases = (("output_grid", "spacing_fs", "1"), ("output_grid", "count", True),
                 ("output_grid", "integration", "FIXED_DT"), ("solver", "atol", "0"),
                 ("solver", "version", ""), ("randomness", "seed", 123))
        for parent, key, value in cases:
            changed = copy.deepcopy(self.contract)
            changed[parent][key] = value
            with self.subTest(key=key), self.assertRaises(ContractError):
                validate_contract(changed, self.root)

    def test_rehashed_nonhermitian_hamiltonian_rejected(self):
        self.h[1][0] = "0.04"
        self.contract["hamiltonian"] = self.artifact("H.json", self.h)
        with self.assertRaisesRegex(ContractError, "not real Hermitian"):
            self.validate()

    def test_rehashed_invalid_density_rejected(self):
        rho = zeros(6)
        rho[0][0] = "1"
        rho[0][1] = rho[1][0] = "1"
        self.contract["rho0"] = self.artifact("rho.json", rho)
        with self.assertRaisesRegex(ContractError, "localized initial state"):
            self.validate()

    def add_dephasing(self):
        rate = Decimal("0.1") / Decimal("0.6582119569")
        self.contract["dephasing"].update(gamma_eV="0.1", rate_fs_inverse=str(rate))
        self.contract["collapse_operators"] = []
        for i in range(6):
            matrix = zeros(6)
            matrix[i][i] = str(rate.sqrt())
            self.contract["collapse_operators"].append(self.artifact(f"L{i}.json", matrix))

    def test_actual_collapse_projectors_bound_to_rate(self):
        self.add_dephasing()
        self.assertIsNone(self.validate())
        matrix = zeros(6)
        matrix[0][0] = "1"
        self.contract["collapse_operators"][0] = self.artifact("L0.json", matrix)
        with self.assertRaisesRegex(ContractError, "amplitude/rate mismatch"):
            self.validate()

    def test_rehashed_nonprojector_collapse_rejected(self):
        self.add_dephasing()
        matrix = json.loads((self.root / "L0.json").read_text())
        matrix[0][1] = "0.01"
        self.contract["collapse_operators"][0] = self.artifact("L0.json", matrix)
        with self.assertRaisesRegex(ContractError, "nonprojector"):
            self.validate()

    def test_reference_cannot_splice_sweep_trap_semantics(self):
        self.contract = self.fixture(reference=True)
        self.contract["interpretation"]["trap_present"] = False
        with self.assertRaisesRegex(ContractError, "trap/model mismatch"):
            self.validate()

    def add_ablation(self):
        self.contract["ablation"] = {"base_hamiltonian": self.artifact("base.json", self.h),
                                     "allowed_entries": [[0, 1]]}
        changed = copy.deepcopy(self.h)
        changed[0][1] = changed[1][0] = "0.07"
        self.contract["hamiltonian"] = self.artifact("H.json", changed)
        return changed

    def test_symmetric_coupling_and_diagonal_ablation(self):
        changed = self.add_ablation()
        self.assertIsNone(self.validate())
        changed[2][2] = "-8.8"
        self.contract["hamiltonian"] = self.artifact("H.json", changed)
        self.contract["ablation"]["allowed_entries"].append([2, 2])
        self.assertIsNone(self.validate())

    def test_hidden_additional_ablation_rejected(self):
        changed = self.add_ablation()
        changed[2][2] = "0.1"
        self.contract["hamiltonian"] = self.artifact("H.json", changed)
        with self.assertRaisesRegex(ContractError, "undeclared"):
            self.validate()

    def test_zero_duplicate_asymmetric_and_empty_ablation_rejected(self):
        self.add_ablation()
        for entries in ([], [[0, 1], [0, 1]], [[1, 0]], [[0, 1], [2, 2]], [[True, 1]]):
            self.contract["ablation"]["allowed_entries"] = entries
            with self.subTest(entries=entries), self.assertRaises(ContractError):
                self.validate()
        self.contract["ablation"]["allowed_entries"] = [[0, 1]]
        self.contract["hamiltonian"] = self.artifact("H.json", self.h)
        with self.assertRaisesRegex(ContractError, "omitted declared"):
            self.validate()

    def cli(self, text):
        path = self.root / "contract.json"
        path.write_text(text)
        return subprocess.run([sys.executable, "-m", "genomics.quantum_dna.run_contract",
                               str(path), "--artifact-root", str(self.root)],
                              cwd=Path(__file__).resolve().parents[2], capture_output=True, text=True)

    def test_cli_pass_has_no_execution_or_authority(self):
        result = self.cli(json.dumps(self.contract))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout), {"status": "PREFLIGHT_PASS", "execution": "NOT_PERFORMED",
                         "authority_promotion": False, "scope": "DECLARED_MATRIX_CONTRACT_ONLY"})

    def test_cli_rejects_duplicate_keys_and_forged_authority(self):
        raw = json.dumps(self.contract)
        duplicate = raw.replace('"schema":', '"schema": "OTHER", "schema":', 1)
        changed = copy.deepcopy(self.contract)
        changed["interpretation"]["authority_promotion"] = True
        for text in (duplicate, json.dumps(changed), raw.replace('"gamma_eV": "0"', '"gamma_eV": NaN')):
            with self.subTest(text=text[:70]):
                result = self.cli(text)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("preflight DENY", result.stderr)
                self.assertEqual(result.stdout, "")


class ClassicalCriteriaTests(unittest.TestCase):
    def test_all_criteria_required(self):
        self.assertTrue(classical_criteria("0.1", "0.1", "0.05", "0.05", 1))
        for args in (("0.1", "0.101", "0.05", "0.05", 1),
                     ("0.1", "0.1", "0.051", "0.05", 1),
                     ("0.1", "0.1", "0.05", "0.051", 1),
                     ("0.1", "0.1", "0.05", "0.05", 0)):
            with self.subTest(args=args):
                self.assertFalse(classical_criteria(*args))

    def test_zero_gamma_nonfinite_negative_and_bool_rejected(self):
        for args in ((0, 0, 0, 0, 1), ("NaN", 0, 0, 0, 1),
                     ("0.1", -1, 0, 0, 1), ("0.1", 0, 0, 0, True)):
            with self.subTest(args=args), self.assertRaises(ContractError):
                classical_criteria(*args)


if __name__ == "__main__":
    unittest.main()
