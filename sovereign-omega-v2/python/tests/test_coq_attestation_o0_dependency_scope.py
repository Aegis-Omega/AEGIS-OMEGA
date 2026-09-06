import json
import tempfile
import unittest
from pathlib import Path

from coq_attestation import DIAGNOSTIC_ONLY, build_receipt


class O0DependencyScopeTests(unittest.TestCase):
    def test_o0_dependency_probe_is_diagnostic_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            formal_root = root / "formal" / "theories"
            source = formal_root / "Weil" / "O0DependencyProbe.v"
            source.parent.mkdir(parents=True)
            source.write_text(
                "Theorem dependency_probe_smoke : True. Proof. exact I. Qed.\n",
                encoding="utf-8",
            )

            compile_status = root / "compile-status.json"
            compile_status.write_text(
                json.dumps(
                    {
                        "Weil/O0DependencyProbe.v": {
                            "status": "COMPILED",
                            "log_sha256": "0" * 64,
                        }
                    }
                ),
                encoding="utf-8",
            )

            assumptions_root = root / "assumptions"
            assumptions_root.mkdir()
            (assumptions_root / "Weil__O0DependencyProbe__dependency_probe_smoke.txt").write_text(
                "Closed under the global context\n",
                encoding="utf-8",
            )

            receipt = build_receipt(
                formal_root=formal_root,
                compile_status_path=compile_status,
                assumptions_root=assumptions_root,
                source_commit="a" * 40,
                coq_version="8.20.1",
            )

            self.assertEqual(len(receipt["files"]), 1)
            self.assertEqual(receipt["files"][0]["evidence_scope"], DIAGNOSTIC_ONLY)
            self.assertEqual(receipt["summary"]["diagnostic_only_files"], 1)
            self.assertEqual(receipt["summary"]["authority_eligible_files"], 0)


if __name__ == "__main__":
    unittest.main()
