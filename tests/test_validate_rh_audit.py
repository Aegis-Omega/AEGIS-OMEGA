import copy
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "validate_rh_audit", ROOT / "scripts/validate-rh-audit.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load RH audit validator")
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class AstraReceiptTests(unittest.TestCase):
    def setUp(self):
        self.dag_data = json.loads(MODULE.DAG.read_text())
        self.receipt_data = json.loads(MODULE.RECEIPT.read_text())
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.dag = self.root / "docs/rh/RH_PROOF_OBLIGATION_DAG_V1.json"
        self.receipt = self.root / "docs/rh/external/AEGIS_RH_ASTRA_ENV_RECEIPT_V1.json"
        self.receipt.parent.mkdir(parents=True)
        self.write(self.dag, self.dag_data)
        self.write(self.receipt, self.receipt_data)
        paths = patch.multiple(MODULE, DAG=self.dag, RECEIPT=self.receipt)
        paths.start()
        self.addCleanup(paths.stop)

    def write(self, path, data):
        path.write_text(json.dumps(data))

    def test_repository_audit_is_structurally_valid(self):
        self.assertEqual(MODULE.validate_dag(), (6, "NOT_PROVEN"))
        self.assertEqual(MODULE.validate_receipt(None), [])

    def test_invalid_receipt_fields_fail_closed(self):
        cases = {
            "schema": "UNKNOWN",
            "rh_status": "PROVEN",
            "authority_effect": "GRANTED",
            "claim_promotion": "ALLOWED",
            "execution_release": "ALLOWED",
            "frontier_sha": "not-a-head",
            "receipt_sha256": "0" * 63,
            "provenance": {"verification_status": "VERIFIED"},
            "files": {"artifact.txt": "not-a-digest"},
        }
        for field, value in cases.items():
            with self.subTest(field=field):
                receipt = copy.deepcopy(self.receipt_data)
                receipt[field] = value
                self.write(self.receipt, receipt)
                with self.assertRaises(ValueError):
                    MODULE.validate_receipt(None)
        receipt = copy.deepcopy(self.receipt_data)
        receipt["files"] = {}
        self.write(self.receipt, receipt)
        with self.assertRaises(ValueError):
            MODULE.validate_receipt(None)

    def test_unsafe_artifact_names_fail_closed(self):
        for name in ("../artifact.txt", "/artifact.txt", "..\\artifact.txt", "C:artifact.txt", ".", "..", "", "bad\x00name"):
            with self.subTest(name=name):
                receipt = copy.deepcopy(self.receipt_data)
                receipt["files"] = {name: "0" * 64}
                self.write(self.receipt, receipt)
                with self.assertRaisesRegex(ValueError, "unsafe artifact name"):
                    MODULE.validate_receipt(None)

    def test_invalid_dag_fields_fail_closed(self):
        cases = {
            "unknown RH status": lambda d: d.update(rh_status="UNKNOWN"),
            "empty nodes": lambda d: d.update(nodes=[]),
            "invalid nodes type": lambda d: d.update(nodes={}),
            "authority escalation": lambda d: d.update(authority_effect="GRANTED"),
            "claim promotion": lambda d: d.update(claim_promotion="ALLOWED"),
            "duplicate node": lambda d: d["nodes"].append(copy.deepcopy(d["nodes"][0])),
            "missing field": lambda d: d["nodes"][0].pop("statement"),
            "unknown status": lambda d: d["nodes"][0].update(status="UNKNOWN"),
            "unknown dependency": lambda d: d["nodes"][0].update(dependencies=["UNKNOWN"]),
            "invalid head": lambda d: d["nodes"][0].update(exact_head="not-a-head"),
            "unsupported ceiling": lambda d: d["nodes"][0].update(authority_ceiling="PROVED_MACHINE_CHECKED"),
            "cycle": lambda d: d["nodes"][0].update(dependencies=[d["nodes"][1]["id"]]),
        }
        for name, mutate in cases.items():
            with self.subTest(case=name):
                dag = copy.deepcopy(self.dag_data)
                mutate(dag)
                self.write(self.dag, dag)
                with self.assertRaises(ValueError):
                    MODULE.validate_dag()

    def test_proven_requires_implemented_bound_proof_verification(self):
        for artifacts in ("null", "plausible", "empty DAG"):
            with self.subTest(artifacts=artifacts):
                dag = copy.deepcopy(self.dag_data)
                dag["rh_status"] = "PROVEN"
                for node in dag["nodes"]:
                    node.update(status="PROVED_MACHINE_CHECKED",
                                authority_ceiling="PROVED_MACHINE_CHECKED",
                                source_path=None, theorem_name=None)
                    if artifacts == "plausible":
                        node.update(source_path="proofs/rh.v", theorem_name="riemann_hypothesis")
                if artifacts == "empty DAG":
                    dag["nodes"] = []
                self.write(self.dag, dag)
                with self.assertRaisesRegex(
                    ValueError, "PROVEN requires bound proof verification; not implemented"
                ):
                    MODULE.validate_dag()

    def test_missing_bundle_files_fail_closed(self):
        with tempfile.TemporaryDirectory() as directory:
            failures = MODULE.validate_receipt(Path(directory))
        self.assertTrue(failures)
        self.assertTrue(all(item.startswith("missing: ") for item in failures))

    def test_digest_mismatch_fails_closed(self):
        receipt = json.loads(MODULE.RECEIPT.read_text())
        with tempfile.TemporaryDirectory() as directory:
            bundle = Path(directory)
            for name in receipt["files"]:
                (bundle / name).write_bytes(b"not the declared artifact")
            failures = MODULE.validate_receipt(bundle)
        self.assertEqual(len(failures), len(receipt["files"]))
        self.assertTrue(all(item.startswith("digest mismatch: ") for item in failures))

    def test_synthetic_bundle_checks_exact_bytes_without_verifying_external_claim(self):
        # These are synthetic bytes, not a recovered ASTRA payload or witness.
        payload = b"normalization\r\nfreeze\x00"
        receipt = copy.deepcopy(self.receipt_data)
        receipt["files"] = {
            "synthetic.bin": "ceab4957e017560ae05fcf4335adf18e0a3aeeeff2e5910c23ea6b19b54a7539"
        }
        self.write(self.receipt, receipt)
        artifact = self.root / "synthetic.bin"
        artifact.write_bytes(payload)
        self.assertEqual(MODULE.validate_receipt(self.root), [])
        self.assertEqual(json.loads(self.receipt.read_text()), receipt)
        self.assertEqual(receipt["provenance"]["verification_status"], "UNVERIFIED_EXTERNAL_CLAIM")
        artifact.write_bytes(payload.replace(b"\r\n", b"\n"))
        self.assertEqual(MODULE.validate_receipt(self.root), ["digest mismatch: synthetic.bin"])

    def test_main_reports_validator_status(self):
        output = io.StringIO()
        with patch.object(MODULE, "validate_dag", return_value=(7, "VALIDATOR_SENTINEL")), \
                patch.object(MODULE, "validate_receipt", return_value=[]), \
                patch.object(sys, "argv", ["validate-rh-audit.py"]), redirect_stdout(output):
            MODULE.main()
        self.assertIn("validated 7 RH DAG nodes", output.getvalue())
        self.assertIn("status=VALIDATOR_SENTINEL", output.getvalue())
        self.assertNotIn("status=NOT_PROVEN", output.getvalue())

    def test_cli_rejects_invalid_inputs_under_python_optimization(self):
        script = self.root / "scripts/validate-rh-audit.py"
        script.parent.mkdir()
        shutil.copyfile(ROOT / "scripts/validate-rh-audit.py", script)
        cases = ("receipt promotion", "unknown dependency", "forged PROVEN", "empty PROVEN")
        for case in cases:
            dag = copy.deepcopy(self.dag_data)
            receipt = copy.deepcopy(self.receipt_data)
            if case == "receipt promotion":
                receipt["rh_status"] = "PROVEN"
            elif case == "unknown dependency":
                dag["nodes"][0]["dependencies"] = ["UNKNOWN"]
            else:
                dag["rh_status"] = "PROVEN"
                for node in dag["nodes"]:
                    node.update(status="PROVED_MACHINE_CHECKED",
                                authority_ceiling="PROVED_MACHINE_CHECKED",
                                source_path=None, theorem_name=None)
                if case == "empty PROVEN":
                    dag["nodes"] = []
            self.write(self.dag, dag)
            self.write(self.receipt, receipt)
            for flags, optimize in (([], "0"), (["-O"], "0"), ([], "1"), (["-OO"], "0")):
                with self.subTest(case=case, flags=flags, PYTHONOPTIMIZE=optimize):
                    result = subprocess.run(
                        [sys.executable, *flags, str(script)], cwd=self.root,
                        env={**os.environ, "PYTHONOPTIMIZE": optimize},
                        capture_output=True, text=True, timeout=15,
                    )
                    self.assertNotEqual(result.returncode, 0)
                    self.assertEqual(result.stdout, "")
                    self.assertTrue(result.stderr)


if __name__ == "__main__":
    unittest.main()
