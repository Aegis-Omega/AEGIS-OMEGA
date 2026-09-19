"""Adversarial validator tests. Every fixture here is SYNTHETIC / TEST_ONLY.

Fixture creates self-authored mock observation/policy pins strictly to exercise
validation. It neither invokes Lean nor supplies an independently trusted replay.
Never use these fixture artifacts or pins as mathematical evidence.
"""

import argparse
import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import gate


class Fixture:
    """TEST_ONLY fixture generator; not a replay adapter or receipt issuer."""

    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.source = self.root / "Synthetic.lean"
        self.source.write_text("-- TEST_ONLY; no Lean replay performed\nexample : True := True.intro\n")
        type_bytes = b"TEST_ONLY exact elaborated type export\n"
        statement_bytes = b"TEST_ONLY canonical statement and reachable definition bundle\n"
        self.subject = {
            "repository": "TEST_ONLY/synthetic-repository", "source_head": "a" * 40,
            "target": {"declaration": "TEST_ONLY.synthetic_target",
                       "elaborated_type_sha256": gate.digest(type_bytes),
                       "statement_bundle_sha256": gate.digest(statement_bytes)},
            "environment": {"lean_version": "4.33.1", "mathlib_commit": "b" * 40,
                            "dependencies": {"synthetic_dependency": "c" * 40}},
        }
        subject_hash = gate.digest(gate.canonical(self.subject))
        self.adapter = {"name": "TEST_ONLY/mock-adapter", "commit": "d" * 40}
        self.kernel = {"name": "TEST_ONLY/mock-independent-kernel", "version": "0"}
        self.receipt = {"schema": "EXACT_TARGET_PROOF_RECEIPT_V1",
                        "subject": copy.deepcopy(self.subject), "subject_sha256": subject_hash,
                        "evidence_kind": "EXECUTED", "authority_effect": "NONE", "artifacts": {}}
        proof = b"TEST_ONLY opaque mock proof object; NOT KERNEL CHECKED\n"
        common = {"subject_sha256": subject_hash, **self.subject["target"],
                  "proof_export_sha256": gate.digest(proof), "result": "PASS", "native_trust": False}
        reports = {
            "axiom_report": {**common, "schema": "EXACT_TARGET_AXIOM_REPORT_V1",
                             "transitive_axioms": sorted(gate.STANDARD_AXIOMS)},
            "comparator_report": {**common, "schema": "EXACT_TARGET_COMPARATOR_REPORT_V1",
                                  "comparison": "EXACT_TARGET"},
            "independent_kernel_report": {**common, "schema": "EXACT_TARGET_KERNEL_REPORT_V1",
                                           "kernel": self.kernel, "replay_kind": "INDEPENDENT_KERNEL",
                                           "proof_object_checked": True},
        }
        raw = {
            "source_tree_manifest": gate.canonical({
                "schema": "EXACT_TARGET_SOURCE_TREE_V1", "source_head": self.subject["source_head"],
                "files": {"Synthetic.lean": gate.digest(self.source.read_bytes())}}),
            "lean_toolchain": b"leanprover/lean4:v4.33.1\n",
            "lake_manifest": gate.canonical({"packages": [
                {"name": "mathlib", "rev": "b" * 40},
                {"name": "synthetic_dependency", "rev": "c" * 40}]}),
            "elaborated_type": type_bytes, "statement_bundle": statement_bytes,
            "proof_export": proof, "build_log": b"TEST_ONLY synthetic build log; NOT EXECUTED\n",
            **{role: gate.canonical(report) for role, report in reports.items()},
        }
        for role, data in raw.items():
            self.put(role, data)
        self.observation = {"schema": "EXACT_TARGET_OBSERVATION_V1",
                            "subject_sha256": subject_hash, "artifact_sha256": {},
                            "replay_adapter": self.adapter, "evidence_kind": "EXECUTED",
                            "result": "REPLAY_COMPLETED"}
        self.policy = {"schema": "EXACT_TARGET_POLICY_V1", **copy.deepcopy(self.subject),
                       "allowed_axioms": sorted(gate.STANDARD_AXIOMS),
                       "required_artifact_roles": list(gate.ROLES), "replay_adapter": self.adapter,
                       "independent_kernel": self.kernel, "trusted_observation_sha256": []}
        self.args = argparse.Namespace(
            receipt=str(self.root / "receipt.json"), policy=str(self.root / "policy.json"),
            observation=str(self.root / "observation.json"), evidence_root=str(self.root),
            expected_head=self.subject["source_head"])
        self.reanchor()

    def put(self, role, data):
        path = role + ".artifact"
        (self.root / path).write_bytes(data)
        self.receipt["artifacts"][role] = {"path": path, "sha256": gate.digest(data)}

    def report(self, role, **changes):
        data = json.loads((self.root / self.receipt["artifacts"][role]["path"]).read_bytes())
        data.update(changes)
        self.put(role, gate.canonical(data))

    def save_receipt(self):
        Path(self.args.receipt).write_bytes(gate.canonical(self.receipt))

    def reanchor(self):
        """Mock trust-controller action; used only by synthetic unit tests."""
        self.observation["artifact_sha256"] = {
            role: entry["sha256"] for role, entry in self.receipt["artifacts"].items()}
        observation_bytes = gate.canonical(self.observation)
        Path(self.args.observation).write_bytes(observation_bytes)
        self.args.observation_sha256 = gate.digest(observation_bytes)
        self.policy["trusted_observation_sha256"] = [self.args.observation_sha256]
        policy_bytes = gate.canonical(self.policy)
        Path(self.args.policy).write_bytes(policy_bytes)
        self.args.policy_sha256 = gate.digest(policy_bytes)
        self.save_receipt()

    def cli_args(self):
        return [part for key, value in vars(self.args).items()
                for part in ("--" + key.replace("_", "-"), str(value))]


class GateTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.f = Fixture(self.tmp.name)

    def denied(self, pattern=None):
        with self.assertRaisesRegex(gate.GateError, pattern or ".+"):
            gate.validate(self.f.args)

    def test_synthetic_evidence_validates_without_claiming_proof(self):
        result = gate.validate(self.f.args)
        self.assertEqual(result["status"], "PASS_EVIDENCE_VALIDATED")
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertNotIn("PROVEN", result.values())

    def test_changed_artifact_without_rehash_is_denied(self):
        (self.f.root / "proof_export.artifact").write_bytes(b"forged proof")
        self.denied("artifact differs")

    def test_self_consistent_forgery_cannot_replace_pinned_observation(self):
        self.f.put("proof_export", b"self-consistent forged proof")
        forged_digest = self.f.receipt["artifacts"]["proof_export"]["sha256"]
        for role in ("axiom_report", "comparator_report", "independent_kernel_report"):
            self.f.report(role, proof_export_sha256=forged_digest)
        self.f.save_receipt()
        self.denied("trusted observation")

    def test_candidate_rewrites_observation_without_external_pin_is_denied(self):
        self.f.observation["artifact_sha256"]["proof_export"] = "f" * 64
        Path(self.f.args.observation).write_bytes(gate.canonical(self.f.observation))
        self.denied("observation digest")

    def test_candidate_rewrites_policy_without_external_pin_is_denied(self):
        self.f.policy["allowed_axioms"].append("sorryAx")
        Path(self.f.args.policy).write_bytes(gate.canonical(self.f.policy))
        self.denied("policy digest")

    def test_observation_external_pin_alone_cannot_override_policy(self):
        self.f.args.observation_sha256 = "f" * 64
        self.denied("not approved by policy")

    def test_stale_head(self):
        self.f.args.expected_head = "e" * 40
        self.denied("stale policy")

    def test_receipt_target_change(self):
        self.f.receipt["subject"]["target"]["declaration"] = "TEST_ONLY.constituent_lemma"
        self.f.receipt["subject_sha256"] = gate.digest(gate.canonical(self.f.receipt["subject"]))
        self.f.save_receipt()
        self.denied("canonical subject")

    def test_empty_target(self):
        self.f.receipt["subject"]["target"]["declaration"] = ""
        self.f.save_receipt()
        self.denied("nonempty string")

    def test_nearby_theorem_even_with_mock_trusted_observation(self):
        self.f.report("comparator_report", comparison="CONSTITUENT_LEMMA")
        self.f.reanchor()
        self.denied("not exact target")

    def test_cross_report_binding_mutations(self):
        for field, value in (("subject_sha256", "f" * 64),
                             ("declaration", "TEST_ONLY.other_target"),
                             ("elaborated_type_sha256", "f" * 64),
                             ("statement_bundle_sha256", "f" * 64),
                             ("proof_export_sha256", "f" * 64), ("result", "NOT_RUN")):
            with self.subTest(field=field):
                self.f = Fixture(Path(self.tmp.name) / field)
                self.f.report("independent_kernel_report", **{field: value})
                self.f.reanchor()
                self.denied("binding/result mismatch")

    def test_axiom_closure_rejects_sorry_custom_and_native_trust(self):
        for axiom in ("sorryAx", "custom_RH", "Lean.ofReduceBool", "native_decide"):
            with self.subTest(axiom=axiom):
                self.f = Fixture(Path(self.tmp.name) / axiom)
                self.f.report("axiom_report", transitive_axioms=[axiom])
                self.f.reanchor()
                self.denied("unapproved axiom")

    def test_policy_cannot_permit_extra_axiom(self):
        self.f.policy["allowed_axioms"].append("sorryAx")
        self.f.reanchor()
        self.denied("nonstandard axiom")

    def test_native_trust_bool_int_confusion(self):
        self.f.report("axiom_report", native_trust=0)
        self.f.reanchor()
        self.denied("native trust")

    def test_kernel_proof_check_bool_int_confusion(self):
        self.f.report("independent_kernel_report", proof_object_checked=1)
        self.f.reanchor()
        self.denied("proof-object replay")

    def test_missing_independent_replay(self):
        del self.f.receipt["artifacts"]["independent_kernel_report"]
        self.f.save_receipt()
        self.denied("receipt artifacts")

    def test_reported_only_receipt(self):
        self.f.receipt["evidence_kind"] = "REPORTED_ONLY"
        self.f.save_receipt()
        self.denied("executed evidence")

    def test_reported_only_observation(self):
        self.f.observation["evidence_kind"] = "REPORTED_ONLY"
        self.f.reanchor()
        self.denied("completed execution")

    def test_wrong_kernel(self):
        self.f.report("independent_kernel_report", kernel={"name": "Lean", "version": "4.33.1"})
        self.f.reanchor()
        self.denied("wrong kernel")

    def test_toolchain_artifact_mutation(self):
        self.f.put("lean_toolchain", b"leanprover/lean4:v4.34.0\n")
        self.f.reanchor()
        self.denied("toolchain mismatch")

    def test_dependency_manifest_mutation(self):
        self.f.put("lake_manifest", gate.canonical({"packages": [{"name": "mathlib", "rev": "f" * 40}]}))
        self.f.reanchor()
        self.denied("dependency commits")

    def test_mathlib_root_manifest(self):
        manifest = {"name": "mathlib", "packages": [
            {"name": "synthetic_dependency", "rev": "c" * 40}]}
        self.f.put("lake_manifest", gate.canonical(manifest))
        self.f.reanchor()
        self.assertEqual(gate.validate(self.f.args)["status"], "PASS_EVIDENCE_VALIDATED")
        manifest["packages"].append({"name": "mathlib", "rev": "b" * 40})
        self.f.put("lake_manifest", gate.canonical(manifest))
        self.f.reanchor()
        self.denied("dependency commits")

    def test_canonical_type_and_definition_bytes(self):
        for role in ("elaborated_type", "statement_bundle"):
            with self.subTest(role=role):
                self.f = Fixture(Path(self.tmp.name) / role)
                self.f.put(role, b"changed canonical content")
                self.f.reanchor()
                self.denied("canonical target mismatch")

    def test_source_manifest_hashes_actual_sources(self):
        self.f.source.write_text("changed source\n")
        self.denied("source file hash mismatch")

    def test_duplicate_json_keys(self):
        data = Path(self.f.args.receipt).read_bytes()
        Path(self.f.args.receipt).write_bytes(b'{"schema":"wrong",' + data[1:])
        self.denied("duplicate JSON key")

    def test_nan_is_not_json(self):
        Path(self.f.args.receipt).write_bytes(b'{"invalid":NaN}')
        self.denied("invalid JSON constant")

    def test_invalid_types_and_unsafe_paths(self):
        for path in (False, [], "../proof", "/tmp/proof", "sub/../proof", "a//b",
                     "a/./b", r"C:\proof", "", "proof\x00export"):
            with self.subTest(path=path):
                self.f.receipt["artifacts"]["proof_export"]["path"] = path
                self.f.save_receipt()
                self.denied()

    def test_symlink_artifact_and_directory(self):
        target = self.f.root / "proof_export.artifact"
        target.rename(self.f.root / "original")
        target.symlink_to("original")
        with self.assertRaises(OSError):
            gate.validate(self.f.args)
        target.unlink()
        nested = self.f.root / "nested"
        nested.symlink_to(self.f.root, target_is_directory=True)
        self.f.receipt["artifacts"]["proof_export"]["path"] = "nested/original"
        self.f.save_receipt()
        with self.assertRaises(OSError):
            gate.validate(self.f.args)

    def test_empty_artifact(self):
        self.f.put("proof_export", b"")
        self.f.reanchor()
        self.denied("empty")

    def test_every_role_is_mandatory(self):
        self.f.policy["required_artifact_roles"].remove("independent_kernel_report")
        self.f.reanchor()
        self.denied("every evidence role")

    def test_cli_normal_and_optimized_have_same_security_result(self):
        script = str(Path(gate.__file__).resolve())
        for optimized in (False, True):
            prefix = [sys.executable] + (["-O"] if optimized else []) + [script]
            with self.subTest(optimized=optimized, case="valid"):
                result = subprocess.run(prefix + self.f.cli_args(), capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(json.loads(result.stdout)["status"], "PASS_EVIDENCE_VALIDATED")
            for case in ("stale-head", "forged-proof"):
                with self.subTest(optimized=optimized, case=case):
                    f = Fixture(Path(self.tmp.name) / (str(optimized) + case))
                    if case == "stale-head":
                        f.args.expected_head = "f" * 40
                    else:
                        f.put("proof_export", b"forged proof")
                        f.save_receipt()
                    result = subprocess.run(prefix + f.cli_args(), capture_output=True, text=True)
                    self.assertEqual(result.returncode, 1, result.stderr)
                    outcome = json.loads(result.stdout)
                    self.assertEqual(outcome["status"], "REJECTED")
                    self.assertEqual(outcome["authority_effect"], "NONE")


if __name__ == "__main__":
    unittest.main()
