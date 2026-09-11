import json
import tempfile
import unittest
from pathlib import Path

from coq_target_census import (
    build_manifest,
    extract_explicit_declarations,
    manifest_bytes,
    verify_committed_manifest,
)


class CoqTargetCensusTests(unittest.TestCase):
    def test_extracts_exported_explicit_declarations_and_ignores_nested_comments(self):
        source = r'''
        (* Definition Fake := 0. (* Lemma Hidden : True. *) *)
        Record Event := { eid : nat }.
        Parameter sha256 : nat -> nat.
        Parameters step_JS step_PY step_WASM : nat -> nat.
        Axiom cross_runtime_bisimulation : True.
        Definition event_hash (x : nat) := x.
        Fixpoint walk (n : nat) := n.
        Theorem stable : True. Proof. exact I. Qed.
        Lemma also_stable : True. Proof. exact I. Qed.
        '''
        self.assertEqual(
            extract_explicit_declarations(source),
            [
                "Event",
                "also_stable",
                "cross_runtime_bisimulation",
                "event_hash",
                "sha256",
                "stable",
                "step_JS",
                "step_PY",
                "step_WASM",
                "walk",
            ],
        )

    def test_manifest_is_deterministic_and_content_addressed(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Z").mkdir()
            (root / "A").mkdir()
            (root / "Z" / "Second.v").write_text("Definition z := 2.\n", encoding="utf-8")
            (root / "A" / "First.v").write_text("Definition a := 1.\n", encoding="utf-8")
            first = build_manifest(root)
            second = build_manifest(root)
            self.assertEqual(first, second)
            self.assertEqual(list(first["files"]), ["A/First.v", "Z/Second.v"])
            self.assertEqual(first["files"]["A/First.v"]["declarations"], ["a"])
            self.assertEqual(manifest_bytes(first), manifest_bytes(second))

    def test_duplicate_declaration_name_is_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "Dup.v").write_text(
                "Definition x := 1.\nLemma x : True. Proof. exact I. Qed.\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "duplicate explicit declaration"):
                build_manifest(root)

    def test_check_rejects_manifest_drift(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "One.v").write_text("Definition x := 1.\n", encoding="utf-8")
            manifest = root / "coq-targets.json"
            manifest.write_bytes(manifest_bytes(build_manifest(root)))
            verify_committed_manifest(root, manifest)
            (root / "One.v").write_text("Definition x := 2.\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "committed Coq target manifest drift"):
                verify_committed_manifest(root, manifest)

    def test_manifest_schema_is_exact(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            (root / "One.v").write_text("Definition x := 1.\n", encoding="utf-8")
            manifest = build_manifest(root)
            self.assertEqual(
                set(manifest), {"kind", "binding_scope", "files"}
            )
            self.assertEqual(manifest["kind"], "COQ_TARGET_MANIFEST_V1")
            self.assertEqual(
                manifest["binding_scope"], "SOURCE_BYTES_AND_EXPLICIT_DECLARATIONS"
            )
            encoded = manifest_bytes(manifest)
            self.assertEqual(json.loads(encoded), manifest)


if __name__ == "__main__":
    unittest.main()
