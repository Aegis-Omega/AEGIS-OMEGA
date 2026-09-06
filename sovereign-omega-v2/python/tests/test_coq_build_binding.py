"""Synthetic build-boundary checks; these tests do not run Coq or a kernel replay."""

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from coq_attestation import build_receipt
from coq_build_binding import (
    check,
    declaration_query,
    digest,
    freeze,
    sealed,
    verifier_identity as capture_verifier_identity,
    verify_receipt_binding,
)


class CoqBuildBindingTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.formal = self.root / "theories"
        self.formal.mkdir()
        self.source = self.formal / "Fixture.v"
        self.source.write_text(
            "Definition value : nat := 1.\n"
            "Theorem value_positive : value = 1. Proof. reflexivity. Qed.\n",
            encoding="utf-8",
        )
        self.targets = self.root / "coq-targets.json"
        self.manifest = {
            "kind": "COQ_TARGET_MANIFEST_V1",
            "files": {
                "Fixture.v": {
                    "source_sha256": digest(self.source.read_bytes()),
                    "declarations": ["value", "value_positive"],
                }
            },
        }
        self.targets.write_text(json.dumps(self.manifest), encoding="utf-8")
        self.identity = {
            "executables": {
                name: {"path": f"/synthetic/{name}", "sha256": "a" * 64,
                       "version": "SYNTHETIC_NOT_A_COQ_BUILD"}
                for name in ("coqc", "coqtop")
            },
            "compiled_dependencies": {"Synthetic.vo": "b" * 64},
        }
        self.commit = "c" * 40
        self.evidence = self.root / "evidence"
        self.identity_patch = patch("coq_build_binding.verifier_identity",
                                    return_value=self.identity)
        self.mock_identity = self.identity_patch.start()
        self.addCleanup(self.identity_patch.stop)

    def frozen_contract(self) -> dict:
        return freeze(self.formal, self.targets, self.commit)

    def compiled_artifacts(self) -> None:
        self.source.with_suffix(".vo").write_bytes(b"synthetic compiled artifact")
        self.source.with_suffix(".glob").write_bytes(b"synthetic declaration index")

    def checked_binding(self, contract: dict | None = None) -> dict:
        if contract is None:
            contract = self.frozen_contract()
        self.compiled_artifacts()
        output = subprocess.CompletedProcess([], 0, stdout=b"synthetic query success\n")
        with patch("coq_build_binding.subprocess.run", return_value=output):
            return check(self.formal, self.targets, contract, self.evidence)

    def receipt_inputs(self) -> dict:
        """Set up synthetic receipt inputs, without running a compiler."""
        status = self.root / "compile-status.json"
        status.write_text(json.dumps({"Fixture.v": {
            "status": "COMPILED", "log_sha256": digest(b"synthetic compile success")
        }}), encoding="utf-8")
        assumptions = self.root / "assumptions"
        assumptions.mkdir(exist_ok=True)
        (assumptions / "Fixture__value_positive.txt").write_text(
            "Closed under the global context\n", encoding="utf-8"
        )
        return {"formal_root": self.formal, "compile_status_path": status,
                "assumptions_root": assumptions, "source_commit": self.commit,
                "coq_version": "SYNTHETIC_NOT_A_COQ_BUILD"}

    def test_synthetic_freeze_check_and_receipt_join(self) -> None:
        contract = self.frozen_contract()
        self.assertEqual(contract["targets_sha256"], digest(self.targets.read_bytes()))
        self.compiled_artifacts()
        output = subprocess.CompletedProcess([], 0, stdout=b"synthetic query success\n")
        with patch("coq_build_binding.subprocess.run", return_value=output) as query:
            binding = check(self.formal, self.targets, contract, self.evidence)
        query.assert_called_once()
        argv = query.call_args.args[0]
        self.assertEqual(argv[:-1], ["/synthetic/coqtop", *contract["query_flags"]])
        self.assertEqual(contract["query_flags"], ["-q", "-quiet", "-batch", "-l"])
        self.assertEqual(contract["compile_flags"], ["-q", "-async-proofs", "off"])
        self.assertEqual(query.call_args.kwargs["cwd"], self.formal)
        query_bytes = Path(argv[-1]).read_bytes()
        self.assertEqual(
            query_bytes.decode("utf-8"),
            "Set Coqtop Exit On Error.\nRequire Import Fixture.\n"
            "Check Fixture.value.\nCheck Fixture.value_positive.\n",
        )
        self.assertEqual(binding["files"]["Fixture.v"]["query_sha256"], digest(query_bytes))
        self.assertEqual(binding["status"], "VERIFIED")
        self.assertEqual(binding["independence"], "SAME_JOB")
        self.assertEqual(binding["kernel_replay"], "NOT_PERFORMED")
        self.assertEqual(binding["production"], "NOT_ADMITTED")
        verify_receipt_binding(binding, self.formal, self.commit)

    def test_freeze_rejects_source_changed_after_manifest_review(self) -> None:
        self.source.write_text("Definition value : nat := 2.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "frozen source mismatch"):
            self.frozen_contract()

    def test_freeze_rejects_unreviewed_source_file(self) -> None:
        (self.formal / "Extra.v").write_text("Definition extra := 0.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "inventory mismatch"):
            self.frozen_contract()

    def test_freeze_rejects_stale_compiled_artifacts(self) -> None:
        for suffix in (".vo", ".vos", ".vok", ".glob"):
            with self.subTest(suffix=suffix):
                artifact = self.source.with_suffix(suffix)
                artifact.write_bytes(b"stale evidence")
                with self.assertRaisesRegex(ValueError, "stale compiled artifacts"):
                    self.frozen_contract()
                artifact.unlink()

    def test_freeze_requires_exact_source_commit(self) -> None:
        for commit in ("main", "c" * 7, "g" * 40):
            with self.subTest(commit=commit):
                with self.assertRaisesRegex(ValueError, "exact Git SHA-1"):
                    freeze(self.formal, self.targets, commit)

    def test_check_rejects_changed_manifest_even_if_still_valid_json(self) -> None:
        contract = self.frozen_contract()
        manifest = copy.deepcopy(self.manifest)
        manifest["files"]["Fixture.v"]["declarations"] = ["value"]
        self.targets.write_text(json.dumps(manifest), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "manifest changed after freeze"):
            check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_changed_source_after_freeze(self) -> None:
        contract = self.frozen_contract()
        self.source.write_text("Definition value := 0.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "frozen source mismatch"):
            check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_tampered_contract_without_resealing(self) -> None:
        contract = self.frozen_contract()
        contract["query_flags"] = []
        with self.assertRaisesRegex(ValueError, "invalid build contract"):
            check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_changed_verifier_or_dependency(self) -> None:
        contract = self.frozen_contract()
        for component in ("executable", "dependency"):
            with self.subTest(component=component):
                changed = copy.deepcopy(self.identity)
                if component == "executable":
                    changed["executables"]["coqtop"]["sha256"] = "d" * 64
                else:
                    changed["compiled_dependencies"]["Synthetic.vo"] = "d" * 64
                self.mock_identity.return_value = changed
                with self.assertRaisesRegex(ValueError, "changed after freeze"):
                    check(self.formal, self.targets, contract, self.evidence)

    def test_verifier_identity_hashes_executable_and_library_bytes(self) -> None:
        binaries = self.root / "bin"
        binaries.mkdir()
        for name in ("coqc", "coqtop"):
            (binaries / name).write_bytes(f"synthetic {name} bytes".encode("utf-8"))
        library = self.root / "lib"
        library.mkdir()
        (library / "Init.vo").write_bytes(b"synthetic compiled library")
        (library / "Plugin.cmxs").write_bytes(b"synthetic compiled plugin")
        (library / "README.txt").write_bytes(b"not a compiled dependency")

        def command_output(argv, **kwargs):
            if argv[-1] == "-where":
                return str(library) + "\n"
            self.assertEqual(argv[-1], "--version")
            return "SYNTHETIC_NOT_A_COQ_BUILD\n"

        with patch("coq_build_binding.shutil.which", side_effect=lambda name: str(binaries / name)), \
                patch("coq_build_binding.run_text", side_effect=command_output):
            identity = capture_verifier_identity()
            self.assertEqual(identity["executables"]["coqc"]["sha256"],
                             digest((binaries / "coqc").read_bytes()))
            self.assertEqual(identity["compiled_dependencies"], {
                "Init.vo": digest((library / "Init.vo").read_bytes()),
                "Plugin.cmxs": digest((library / "Plugin.cmxs").read_bytes()),
            })
            (binaries / "coqc").write_bytes(b"different synthetic executable")
            changed_binary = capture_verifier_identity()
            self.assertNotEqual(changed_binary["executables"], identity["executables"])
            self.assertEqual(changed_binary["compiled_dependencies"], identity["compiled_dependencies"])
            (library / "Init.vo").write_bytes(b"different compiled library")
            changed_library = capture_verifier_identity()
            self.assertNotEqual(changed_library["compiled_dependencies"], changed_binary["compiled_dependencies"])
            self.assertEqual(changed_library["executables"], changed_binary["executables"])

    def test_check_requires_both_vo_and_glob(self) -> None:
        contract = self.frozen_contract()
        for suffix in (".vo", ".glob"):
            with self.subTest(missing=suffix):
                self.compiled_artifacts()
                self.source.with_suffix(suffix).unlink()
                with self.assertRaisesRegex(ValueError, "missing/invalid compiled artifacts"):
                    check(self.formal, self.targets, contract, self.evidence)

    def test_synthetic_missing_explicit_declaration_query_fails(self) -> None:
        contract = self.frozen_contract()
        self.compiled_artifacts()
        error = b"Error: The reference Fixture.value was not found.\n"
        output = subprocess.CompletedProcess([], 1, stdout=error)
        with patch("coq_build_binding.subprocess.run", return_value=output):
            with self.assertRaisesRegex(ValueError, "declaration query failed"):
                check(self.formal, self.targets, contract, self.evidence)
        self.assertEqual((self.evidence / "Fixture.log").read_bytes(), error)

    def test_check_rejects_source_drift_during_query(self) -> None:
        contract = self.frozen_contract()
        self.compiled_artifacts()

        def mutate_source(*args, **kwargs):
            self.source.write_text("Definition value := 0.\n", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout=b"synthetic success")

        with patch("coq_build_binding.subprocess.run", side_effect=mutate_source):
            with self.assertRaisesRegex(ValueError, "frozen source mismatch"):
                check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_manifest_drift_during_query(self) -> None:
        contract = self.frozen_contract()
        self.compiled_artifacts()

        def mutate_manifest(*args, **kwargs):
            self.targets.write_text("{}", encoding="utf-8")
            return subprocess.CompletedProcess([], 0, stdout=b"synthetic success")

        with patch("coq_build_binding.subprocess.run", side_effect=mutate_manifest):
            with self.assertRaisesRegex(ValueError, "manifest changed during queries"):
                check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_compiled_artifact_drift_during_query(self) -> None:
        contract = self.frozen_contract()
        self.compiled_artifacts()

        def mutate_artifact(*args, **kwargs):
            self.source.with_suffix(".vo").write_bytes(b"replaced compiled artifact")
            return subprocess.CompletedProcess([], 0, stdout=b"synthetic success")

        with patch("coq_build_binding.subprocess.run", side_effect=mutate_artifact):
            with self.assertRaisesRegex(ValueError, "artifact changed during query"):
                check(self.formal, self.targets, contract, self.evidence)

    def test_check_rejects_verifier_drift_during_queries(self) -> None:
        contract = self.frozen_contract()
        changed = copy.deepcopy(self.identity)
        changed["executables"]["coqtop"]["sha256"] = "d" * 64
        self.mock_identity.side_effect = [self.identity, changed]
        with self.assertRaisesRegex(ValueError, "changed during queries"):
            self.checked_binding(contract)

    def test_check_rechecks_earlier_artifacts_after_later_queries(self) -> None:
        second = self.formal / "ZSecond.v"
        second.write_text("Definition second := 2.\n", encoding="utf-8")
        self.manifest["files"]["ZSecond.v"] = {
            "source_sha256": digest(second.read_bytes()), "declarations": ["second"]
        }
        self.targets.write_text(json.dumps(self.manifest), encoding="utf-8")
        contract = self.frozen_contract()
        for suffix in (".vo", ".glob"):
            with self.subTest(artifact=suffix):
                self.compiled_artifacts()
                second.with_suffix(".vo").write_bytes(b"synthetic second module")
                second.with_suffix(".glob").write_bytes(b"synthetic second index")

                def mutate_earlier_artifact(argv, **kwargs):
                    if Path(argv[-1]).name == "ZSecond.v":
                        self.source.with_suffix(suffix).write_bytes(b"changed after its query")
                    return subprocess.CompletedProcess([], 0, stdout=b"synthetic success")

                with patch("coq_build_binding.subprocess.run", side_effect=mutate_earlier_artifact):
                    with self.assertRaisesRegex(ValueError, "artifact changed during queries"):
                        check(self.formal, self.targets, contract, self.evidence)

    def test_receipt_join_rejects_failed_or_unsealed_binding(self) -> None:
        binding = self.checked_binding()
        changed = copy.deepcopy(binding)
        changed["status"] = "FAILED"
        for candidate in (changed, sealed(changed)):
            with self.subTest(resealed=candidate == sealed(candidate)):
                with self.assertRaisesRegex(ValueError, "invalid or failed build binding"):
                    verify_receipt_binding(candidate, self.formal, self.commit)

    def test_receipt_join_rejects_another_commit(self) -> None:
        binding = self.checked_binding()
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            verify_receipt_binding(binding, self.formal, "d" * 40)

    def test_receipt_join_rejects_omitted_declaration_evidence(self) -> None:
        binding = self.checked_binding()
        binding["files"] = {}
        with self.assertRaisesRegex(ValueError, "file inventory mismatch"):
            verify_receipt_binding(sealed(binding), self.formal, self.commit)

    def test_resealed_target_omission_cannot_override_reviewed_manifest(self) -> None:
        binding = self.checked_binding()
        names = ["value"]
        binding["contract"]["targets"]["files"]["Fixture.v"]["declarations"] = names
        binding["files"]["Fixture.v"]["declarations"] = names
        binding["files"]["Fixture.v"]["query_sha256"] = digest(
            declaration_query("Fixture.v", names).encode("utf-8"))
        binding["contract"] = sealed(binding["contract"])
        binding = sealed(binding)
        with self.assertRaisesRegex(ValueError, "target manifest"):
            verify_receipt_binding(binding, self.formal, self.commit)
        with patch("coq_build_binding.subprocess.run") as query:
            with self.assertRaisesRegex(ValueError, "target manifest"):
                check(self.formal, self.targets, binding["contract"], self.evidence)
            query.assert_not_called()

    def test_receipt_join_rejects_resealed_target_digest(self) -> None:
        binding = self.checked_binding()
        binding["contract"]["targets_sha256"] = "d" * 64
        binding["contract"] = sealed(binding["contract"])
        with self.assertRaisesRegex(ValueError, "target manifest"):
            verify_receipt_binding(sealed(binding), self.formal, self.commit)

    def test_receipt_join_requires_unchanged_reviewed_manifest_file(self) -> None:
        binding = self.checked_binding()
        self.targets.write_text("{}", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "target manifest"):
            verify_receipt_binding(binding, self.formal, self.commit)
        self.targets.unlink()
        with self.assertRaises(FileNotFoundError):
            verify_receipt_binding(binding, self.formal, self.commit)

    def test_receipt_join_requires_recorded_verifier_identity(self) -> None:
        binding = self.checked_binding()
        del binding["contract"]["verifier_identity"]
        binding["contract"] = sealed(binding["contract"])
        with self.assertRaises(ValueError):
            verify_receipt_binding(sealed(binding), self.formal, self.commit)

    def test_check_and_receipt_join_reject_flags_that_bypass_queries(self) -> None:
        binding = self.checked_binding()
        binding["contract"]["query_flags"] = ["--version"]
        binding["contract"] = sealed(binding["contract"])
        output = subprocess.CompletedProcess([], 0, stdout=b"synthetic version output\n")
        with patch("coq_build_binding.subprocess.run", return_value=output) as query:
            with self.assertRaises(ValueError):
                check(self.formal, self.targets, binding["contract"], self.evidence)
            query.assert_not_called()
        with self.assertRaises(ValueError):
            verify_receipt_binding(sealed(binding), self.formal, self.commit)

    def test_receipt_join_rejects_modified_declarations_sources_and_exit_codes(self) -> None:
        binding = self.checked_binding()
        mutations = (("declarations", ["value_positive"]),
                     ("source_sha256", "d" * 64),
                     ("query_exit_code", 1), ("query_exit_code", False))
        for key, value in mutations:
            with self.subTest(key=key, value=value):
                changed = copy.deepcopy(binding)
                changed["files"]["Fixture.v"][key] = value
                with self.assertRaisesRegex(ValueError, "declaration evidence mismatch"):
                    verify_receipt_binding(sealed(changed), self.formal, self.commit)

    def test_receipt_join_rejects_source_drift(self) -> None:
        binding = self.checked_binding()
        self.source.write_text("Definition value := 0.\n", encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "frozen source mismatch"):
            verify_receipt_binding(binding, self.formal, self.commit)

    def test_receipt_join_rejects_query_digest_unrelated_to_explicit_targets(self) -> None:
        binding = self.checked_binding()
        binding["files"]["Fixture.v"]["query_sha256"] = digest(b"Check nat.\n")
        with self.assertRaisesRegex(ValueError, "query.*mismatch"):
            verify_receipt_binding(sealed(binding), self.formal, self.commit)

    def test_synthetic_receipt_generator_includes_verified_binding(self) -> None:
        binding = self.checked_binding()
        binding_path = self.root / "build-binding.json"
        binding_path.write_text(json.dumps(binding), encoding="utf-8")
        receipt = build_receipt(**self.receipt_inputs(), build_binding_path=binding_path)
        self.assertEqual(receipt["schema_version"], "1.2.0")
        self.assertEqual(receipt["build_binding_status"], "VERIFIED")
        self.assertEqual(receipt["build_binding"], binding)
        self.assertEqual(receipt["build_binding"]["kernel_replay"], "NOT_PERFORMED")
        self.assertEqual(receipt["correspondence"], "NOT_ESTABLISHED")

    def test_legacy_receipt_without_binding_is_explicitly_not_bound(self) -> None:
        receipt = build_receipt(**self.receipt_inputs())
        self.assertEqual(receipt["schema_version"], "1.1.0")
        self.assertEqual(receipt["build_binding_status"], "NOT_BOUND")
        self.assertNotIn("build_binding", receipt)

    def test_receipt_generator_rejects_missing_binding_file(self) -> None:
        with self.assertRaises(FileNotFoundError):
            build_receipt(**self.receipt_inputs(),
                          build_binding_path=self.root / "missing-binding.json")

    def test_receipt_generator_rejects_invalid_binding_file(self) -> None:
        binding = self.checked_binding()
        tampered = copy.deepcopy(binding)
        tampered["status"] = "FAILED"
        binding_path = self.root / "invalid-binding.json"
        for raw in ("{invalid json", "{}", json.dumps(tampered), json.dumps(sealed(tampered))):
            with self.subTest(raw=raw[:40]):
                binding_path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError):
                    build_receipt(**self.receipt_inputs(), build_binding_path=binding_path)

    def test_receipt_generator_rejects_binding_for_another_commit(self) -> None:
        binding_path = self.root / "build-binding.json"
        binding_path.write_text(json.dumps(self.checked_binding()), encoding="utf-8")
        inputs = self.receipt_inputs()
        inputs["source_commit"] = "d" * 40
        with self.assertRaisesRegex(ValueError, "source commit mismatch"):
            build_receipt(**inputs, build_binding_path=binding_path)

    def test_receipt_generator_rejects_verifier_version_label_mismatch(self) -> None:
        binding_path = self.root / "build-binding.json"
        binding_path.write_text(json.dumps(self.checked_binding()), encoding="utf-8")
        inputs = self.receipt_inputs()
        inputs["coq_version"] = "9.2.0"
        with self.assertRaises(ValueError):
            build_receipt(**inputs, build_binding_path=binding_path)


if __name__ == "__main__":
    unittest.main()
