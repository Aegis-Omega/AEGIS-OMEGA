#!/usr/bin/env python3
from __future__ import annotations

import copy
import importlib.util
import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "harness" / "sdk" / "repository_knowledge.py"


def git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=True,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    ).stdout.strip()


def load_module():
    spec = importlib.util.spec_from_file_location("aegis_repository_knowledge", MODULE_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def write(repo: Path, relative: str, content: str) -> None:
    path = repo / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def commit_all(repo: Path, message: str) -> None:
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", message)


class RepositoryCartographerContract(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.repo = Path(self.temp.name)
        git(self.repo, "init", "-q")
        git(self.repo, "config", "user.email", "aegis@example.invalid")
        git(self.repo, "config", "user.name", "AEGIS Test")

        write(self.repo, "WORKFLOW.md", "use what exists\n")
        write(self.repo, "REPO_MAP.md", "legacy map\n")
        write(
            self.repo,
            "reports/inventory.json",
            json.dumps({"generated_from": "1" * 40, "generated": "2026-07-12"}) + "\n",
        )
        write(self.repo, "harness/skill_tree.json", '{"skills":[{"skill_id":"existing_skill"}]}\n')
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'engineering'\n")
        write(self.repo, "vertex/serve.py", "APP_NAME = 'aegis'\n")
        write(self.repo, ".github/workflows/ci.yml", "name: CI\n")
        write(self.repo, "supabase/migrations/001.sql", "select 1;\n")
        write(self.repo, "formal/theories/Foo.v", "Theorem foo : True. Proof. exact I. Qed.\n")
        write(self.repo, "docs/spec.md", "# Spec\n")
        write(self.repo, "scripts/run.sh", "#!/bin/sh\nexit 0\n")
        write(self.repo, "tests/test_x.py", "assert True\n")
        commit_all(self.repo, "initial")

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_production_module_exists(self) -> None:
        self.assertTrue(MODULE_PATH.exists(), "repository knowledge module is not implemented")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_snapshot_is_exact_head_content_addressed_and_deterministic(self) -> None:
        mod = load_module()
        first = mod.build_snapshot(
            self.repo,
            repository_id=123,
            repository_full_name="Aegis-Omega/AEGIS-OMEGA",
        )
        second = mod.build_snapshot(
            self.repo,
            repository_id=123,
            repository_full_name="Aegis-Omega/AEGIS-OMEGA",
        )

        self.assertEqual(first, second)
        self.assertEqual(first["source_head_sha"], git(self.repo, "rev-parse", "HEAD"))
        self.assertEqual(first["source_tree_sha"], git(self.repo, "rev-parse", "HEAD^{tree}"))
        self.assertEqual(first["repository_id"], 123)
        self.assertEqual(first["repository_full_name"], "Aegis-Omega/AEGIS-OMEGA")
        self.assertEqual(first["knowledge_status"], "ESTABLISHED")
        self.assertRegex(first["artifacts_digest"], r"^[0-9a-f]{64}$")
        self.assertRegex(first["snapshot_digest"], r"^[0-9a-f]{64}$")

        paths = [item["path"] for item in first["artifacts"]]
        self.assertEqual(paths, sorted(paths))
        by_path = {item["path"]: item for item in first["artifacts"]}
        self.assertEqual(by_path[".github/workflows/ci.yml"]["category"], "workflow")
        self.assertEqual(by_path["agents/engineering.py"]["category"], "agent")
        self.assertEqual(by_path["supabase/migrations/001.sql"]["category"], "migration")
        self.assertEqual(by_path["formal/theories/Foo.v"]["category"], "formal")
        self.assertEqual(by_path["tests/test_x.py"]["category"], "test")
        self.assertEqual(by_path["docs/spec.md"]["category"], "documentation")
        self.assertEqual(first["legacy_inventory"]["state"], "STALE_DECLARED_HEAD")
        self.assertEqual(first["legacy_inventory"]["declared_head"], "1" * 40)

        verification = mod.verify_snapshot(self.repo, first, expected_repository_id=123)
        self.assertEqual(verification["status"], "ESTABLISHED")
        self.assertEqual(verification["reason_codes"], [])

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_old_snapshot_is_denied_after_head_moves(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'engineering_v2'\n")
        commit_all(self.repo, "move head")

        verification = mod.verify_snapshot(self.repo, snapshot, expected_repository_id=123)
        self.assertEqual(verification["status"], "DENIED")
        self.assertIn("SOURCE_HEAD_MISMATCH", verification["reason_codes"])
        self.assertIn("SOURCE_TREE_MISMATCH", verification["reason_codes"])

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_delta_is_path_and_blob_exact(self) -> None:
        mod = load_module()
        before = mod.build_snapshot(self.repo, repository_id=123)
        write(self.repo, "agents/engineering.py", "CAPABILITY = 'changed'\n")
        write(self.repo, "docs/new.md", "# New\n")
        (self.repo / "scripts" / "run.sh").unlink()
        commit_all(self.repo, "delta")
        after = mod.build_snapshot(self.repo, repository_id=123)

        delta = mod.compute_delta(before, after)
        self.assertEqual(delta["from_head_sha"], before["source_head_sha"])
        self.assertEqual(delta["to_head_sha"], after["source_head_sha"])
        self.assertEqual(delta["added"], ["docs/new.md"])
        self.assertEqual(delta["deleted"], ["scripts/run.sh"])
        self.assertEqual(delta["modified"], ["agents/engineering.py"])
        self.assertRegex(delta["delta_digest"], r"^[0-9a-f]{64}$")

    @unittest.skipUnless(MODULE_PATH.exists(), "RED: cartographer module absent")
    def test_tampered_snapshot_document_is_denied(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        tampered = copy.deepcopy(snapshot)
        tampered["artifacts"][0]["path"] = "forged/path"

        verification = mod.verify_snapshot_document(tampered, expected_repository_id=123)
        self.assertEqual(verification["status"], "DENIED")
        self.assertIn("ARTIFACTS_DIGEST_MISMATCH", verification["reason_codes"])
        self.assertIn("SNAPSHOT_DIGEST_MISMATCH", verification["reason_codes"])


    def test_gitless_package_content_receipt_denies_tamper(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        manifest = mod.build_runtime_export_manifest(snapshot)
        self.assertEqual(manifest, mod.build_runtime_export_manifest(snapshot))
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            for entry in manifest["files"]:
                name = entry["path"]
                src = self.repo / ("vertex/serve.py" if name == "serve.py" else name)
                dst = root / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            receipt = mod.verify_runtime_export_manifest(
                root, manifest, expected_head=snapshot["source_head_sha"])
            self.assertEqual(receipt["status"], "CONTENT_MATCH_ONLY", receipt)
            self.assertEqual(receipt["authority"], "NOT_GRANTED")
            self.assertEqual(receipt["attestation"], "NOT_PRESENT")
            (root / "agents/engineering.py").write_text("tampered\n")
            self.assertIn("FILE_CONTENT_MISMATCH", mod.verify_runtime_export_manifest(
                root, manifest, expected_head=snapshot["source_head_sha"])["reason_codes"])
            shutil.copy2(self.repo / "agents/engineering.py", root / "agents/engineering.py")
            (root / "agents/untracked.py").write_text("injected\n")
            self.assertIn("FILE_SET_MISMATCH", mod.verify_runtime_export_manifest(
                root, manifest, expected_head=snapshot["source_head_sha"])["reason_codes"])
            (root / "agents/untracked.py").unlink()
            self.assertIn("SOURCE_HEAD_MISMATCH", mod.verify_runtime_export_manifest(
                root, manifest, expected_head="f" * 40)["reason_codes"])
            fake = copy.deepcopy(manifest)
            fake["files"][0]["git_blob_sha"] = "0" * 40
            self.assertIn("MANIFEST_DIGEST_MISMATCH", mod.verify_runtime_export_manifest(
                root, fake, expected_head=snapshot["source_head_sha"])["reason_codes"])

    def test_runtime_export_rejects_nonregular_git_source(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        altered = copy.deepcopy(snapshot)
        for file in altered["artifacts"]:
            if file["path"] == "agents/engineering.py":
                file["mode"] = "120000"
        altered["artifacts_digest"] = mod._digest(altered["artifacts"])
        altered.pop("snapshot_digest")
        altered["snapshot_digest"] = mod._digest(altered)
        with self.assertRaisesRegex(ValueError, "NONREGULAR"):
            mod.build_runtime_export_manifest(altered)


    def test_vertex_docker_source_stage_and_ci_are_bound_to_same_payload(self) -> None:
        dockerfile = (ROOT / "vertex/Dockerfile").read_text(encoding="utf-8")
        workflow = (ROOT / ".github/workflows/repository-knowledge.yml").read_text(encoding="utf-8")
        self.assertIn("FROM scratch AS source-payload", dockerfile)
        self.assertIn("COPY vertex/serve.py /app/serve.py", dockerfile)
        self.assertIn("COPY agents /app/agents", dockerfile)
        self.assertIn("COPY harness /app/harness", dockerfile)
        for path in ("serve.py", "agents", "harness"):
            self.assertIn(
                "COPY --from=source-payload /app/" + path + " /app/" + path,
                dockerfile,
            )
        self.assertIn("docker build --target source-payload --network none", workflow)
        self.assertIn("docker cp", workflow)
        self.assertIn("verify_runtime_export_manifest(", workflow)
        self.assertIn('receipt["authority"] != "NOT_GRANTED"', workflow)
        self.assertNotIn("docker push", workflow)
        self.assertNotIn("gcloud builds submit", workflow)


    def test_read_only_github_identity_cross_check_denies_mismatch(self) -> None:
        mod = load_module()
        snapshot = mod.build_snapshot(self.repo, repository_id=123)
        manifest = mod.build_runtime_export_manifest(snapshot)
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for item in manifest["files"]:
                name = item["path"]
                src = self.repo / ("vertex/serve.py" if name == "serve.py" else name)
                dst = root / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            content = mod.verify_runtime_export_manifest(
                root, manifest, expected_head=snapshot["source_head_sha"])
        binding = {
            "expected_head": snapshot["source_head_sha"],
            "expected_repository": "Aegis-Omega/AEGIS-OMEGA",
            "remote_commit_sha": snapshot["source_head_sha"],
            "remote_tree_sha": snapshot["source_tree_sha"],
        }
        verified = mod.verify_remote_git_source(manifest, content, **binding)
        self.assertEqual(verified["status"], "REMOTE_GIT_MATCH_ONLY", verified)
        self.assertEqual(verified["authority"], "NOT_GRANTED")
        self.assertEqual(verified["attestation"], "NOT_PRESENT")
        for changed, reason in (
            ({"remote_commit_sha": "f" * 40}, "REMOTE_COMMIT_MISMATCH"),
            ({"remote_tree_sha": "f" * 40}, "REMOTE_TREE_MISMATCH"),
            ({"expected_repository": "other/repo"}, "REPOSITORY_MISMATCH"),
            ({"expected_head": "f" * 40}, "SOURCE_HEAD_MISMATCH"),
        ):
            with self.subTest(code=reason):
                result = mod.verify_remote_git_source(manifest, content, **{**binding, **changed})
                self.assertIn(reason, result["reason_codes"])
                self.assertEqual(result["status"], "DENIED")
        fake = copy.deepcopy(manifest)
        fake["source_tree_sha"] = "f" * 40
        self.assertIn("MANIFEST_INVALID", mod.verify_remote_git_source(
            fake, content, **binding)["reason_codes"])
        self.assertIn("CONTENT_NOT_VERIFIED", mod.verify_remote_git_source(
            manifest, {**content, "authority": "ADMITTED"}, **binding)["reason_codes"])


    def test_local_final_image_ci_is_bounded_and_non_authoritative(self) -> None:
        workflow = (ROOT / ".github/workflows/repository-knowledge.yml").read_text(encoding="utf-8")
        dockerfile = (ROOT / "vertex/Dockerfile").read_text(encoding="utf-8")
        job = workflow.split("      - name: Verify complete Vertex image locally", 1)[1].split(
            "      - name: Cross-check exact source via read-only GitHub API", 1)[0]
        self.assertIn("timeout 240s docker build", job)
        self.assertIn("docker cp", job)
        self.assertIn("verify_runtime_export_manifest(", job)
        self.assertIn("CI_LOCAL_IMAGE_ONLY", job)
        self.assertIn('"attestation": "NOT_PRESENT"', job)
        self.assertIn('"authority": "NOT_GRANTED"', job)
        self.assertIn("docker run --rm --network none --read-only", job)
        self.assertIn("GITLESS_RUNTIME_DENIED_AS_EXPECTED", job)
        self.assertIn("python-dependencies.txt", job)
        self.assertIn("--entrypoint python", job)
        self.assertNotIn("docker push", job)
        self.assertNotIn("gcloud", job)
        self.assertNotIn("id-token: write", workflow)
        self.assertIn("FROM scratch AS source-payload", dockerfile)


    def test_final_image_cross_binding_rejects_forged_claims(self) -> None:
        mod = load_module()
        snap = mod.build_snapshot(self.repo, repository_id=123)
        manifest = mod.build_runtime_export_manifest(snap)
        with tempfile.TemporaryDirectory() as folder:
            image = Path(folder)
            for item in manifest["files"]:
                name = item["path"]
                src = self.repo / ("vertex/serve.py" if name == "serve.py" else name)
                dst = image / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            content = mod.verify_runtime_export_manifest(
                image, manifest, expected_head=snap["source_head_sha"])
        args = dict(expected_head=snap["source_head_sha"],
                    expected_repository="Aegis-Omega/AEGIS-OMEGA",
                    remote_commit_sha=snap["source_head_sha"], remote_tree_sha=snap["source_tree_sha"])
        image = dict(schema="aegis-final-image-local-observation/1",
                     scope="CI_LOCAL_IMAGE_ONLY", source_head_sha=snap["source_head_sha"],
                     source_tree_sha=snap["source_tree_sha"], manifest_digest=manifest["manifest_digest"],
                     image_id="sha256:"+"a"*64, source_status="CONTENT_MATCH_ONLY",
                     authority="NOT_GRANTED", attestation="NOT_PRESENT")
        good = mod.verify_remote_git_source(manifest, content, final_image_receipt=image, **args)
        self.assertEqual(good["status"], "REMOTE_GIT_MATCH_ONLY", good)
        self.assertEqual(good["final_image_binding"], "CI_LOCAL_CONTENT_MATCH_ONLY")
        self.assertEqual(good["authority"], "NOT_GRANTED")
        for field, bad in (("image_id", "invalid"), ("source_head_sha", "f"*40),
                           ("source_tree_sha", "f"*40), ("manifest_digest", "f"*64),
                           ("scope", "DEPLOYED"), ("attestation", "SIGNED"),
                           ("authority", "ADMITTED"), ("source_status", "DENIED")):
            with self.subTest(field=field):
                result = mod.verify_remote_git_source(
                    manifest, content, final_image_receipt={**image, field:bad}, **args)
                self.assertEqual(result["status"], "DENIED")
                self.assertIn("FINAL_IMAGE_BINDING_MISMATCH", result["reason_codes"])

    def test_automaton3_crypto_verifier_is_source_bound_and_never_image_admission(self) -> None:
        source = (ROOT / ".github/workflows/automaton-3.yml").read_text(encoding="utf-8")
        self.assertIn("      - name: Attest exact Automaton-3 candidate", source)
        self.assertIn("      - name: Verify signed Automaton-3 candidate with GitHub Sigstore", source)
        self.assertLess(source.index("      - name: Attest exact Automaton-3 candidate"),
                        source.index("      - name: Verify signed Automaton-3 candidate with GitHub Sigstore"))
        step = source.split("      - name: Verify signed Automaton-3 candidate with GitHub Sigstore", 1)[1]
        self.assertIn("gh attestation verify", step)
        self.assertIn("--signer-workflow", step)
        self.assertIn('--source-digest "$GITHUB_SHA"', step)
        self.assertNotIn('--source-digest "$CANDIDATE_SHA"', step)
        self.assertIn("EXPECTED_PARENT_SHA $CANDIDATE_SHA", step)
        self.assertIn('gh api "repos/$GITHUB_REPOSITORY/git/commits/$GITHUB_SHA"', step)
        self.assertIn('--cert-oidc-issuer "https://token.actions.githubusercontent.com/aegis-omega"', step)
        self.assertNotIn("--cert-oidc-issuer \"https://token.actions.githubusercontent.com\" ", step)
        self.assertIn("--deny-self-hosted-runners", step)
        self.assertIn("SIGNATURE_VERIFIED", step)
        self.assertIn('"final_image_attested": False', step)
        self.assertIn('"authority": "NOT_GRANTED"', step)
        self.assertIn("subject_sha256", step)
        self.assertIn('if [[ "$verified" != 1 ]]; then', step)
        self.assertNotIn("docker push", step)
        self.assertNotIn("gcloud", step)
        self.assertIn("id-token: write", source)
        self.assertIn("attestations: write", source)
        self.assertNotIn("contents: write", source)



    def test_automaton3_signs_and_verifies_existing_build_recipe_inputs_without_image_claims(self) -> None:
        workflow = (ROOT / ".github/workflows/automaton-3.yml").read_text(encoding="utf-8")
        signed = workflow.split("      - name: Attest exact Automaton-3 candidate", 1)[1].split(
            "      - name: Verify signed Automaton-3 candidate with GitHub Sigstore", 1)[0]
        verified = workflow.split("      - name: Verify signed Automaton-3 candidate with GitHub Sigstore", 1)[1]
        for path in ("vertex/Dockerfile", "vertex/cloudbuild.yaml", "harness/sdk/repository_knowledge.py"):
            with self.subTest(subject=path):
                self.assertIn("            " + path + "\n", signed)
                self.assertIn(path, verified)
                self.assertTrue((ROOT / path).is_file())
        self.assertIn("AUTOMATON3_CANDIDATE_OR_BUILD_RECIPE_ONLY", verified)
        self.assertIn('subject_key="${subject//\\//__}"', verified)
        self.assertIn('$out/$subject_key.verified.json', verified)
        self.assertIn('$out/$subject_key.receipt.json', verified)
        self.assertNotIn('$out/$subject.verified.json', verified)
        self.assertIn('"final_image_attested": False', verified)
        self.assertIn('"authority": "NOT_GRANTED"', verified)
        self.assertIn("--source-digest \"$GITHUB_SHA\"", verified)
        self.assertIn("--signer-workflow \"$signer\"", verified)
        self.assertIn('[[ "$parents" == "$EXPECTED_PARENT_SHA $CANDIDATE_SHA" ]]', verified)
        self.assertNotIn("docker push", verified)
        self.assertNotIn("id-token: write", (ROOT / ".github/workflows/repository-knowledge.yml").read_text())



    def test_ci_image_artifact_requires_exact_run_head_and_no_authority(self) -> None:
        spec = importlib.util.spec_from_file_location(
            "aegis_ci_image_observation", ROOT / "scripts/ci_image_observation.py"
        )
        assert spec and spec.loader
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        knowledge = load_module()
        snapshot = knowledge.build_snapshot(self.repo, repository_id=123)
        manifest = knowledge.build_runtime_export_manifest(snapshot)
        with tempfile.TemporaryDirectory() as temp:
            image = Path(temp)
            for item in manifest["files"]:
                name = item["path"]
                src = self.repo / ("vertex/serve.py" if name == "serve.py" else name)
                dst = image / name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            content = knowledge.verify_runtime_export_manifest(
                image, manifest, expected_head=snapshot["source_head_sha"])
        head, tree = snapshot["source_head_sha"], snapshot["source_tree_sha"]
        final = {
            "schema": "aegis-final-image-local-observation/1",
            "scope": "CI_LOCAL_IMAGE_ONLY",
            "source_head_sha": head, "source_tree_sha": tree,
            "manifest_digest": manifest["manifest_digest"],
            "image_id": "sha256:" + "a" * 64,
            "source_status": "CONTENT_MATCH_ONLY", "authority": "NOT_GRANTED",
            "attestation": "NOT_PRESENT",
        }
        readback = knowledge.verify_remote_git_source(
            manifest, content, expected_head=head,
            expected_repository="Aegis-Omega/AEGIS-OMEGA",
            remote_commit_sha=head, remote_tree_sha=tree,
            final_image_receipt=final,
        )
        package = {"manifest": manifest, "docker-source-receipt": content,
                   "final-image-receipt": final, "github-readback": readback}
        run = {"id": 123, "path": ".github/workflows/repository-knowledge.yml",
               "head_sha": head, "status": "completed", "conclusion": "success",
               "event": "pull_request",
               "repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"},
               "head_repository": {"full_name": "Aegis-Omega/AEGIS-OMEGA"}}
        artifact = {"id": 456, "name": f"runtime-export-{head}", "expired": False,
                    "digest": "sha256:" + "b" * 64, "size_in_bytes": 512,
                    "workflow_run": {"id": 123, "head_sha": head,
                        "repository_id": 1095915905, "head_repository_id": 1095915905}}
        good = mod.verify_ci_image_observation(
            package, run, artifact, expected_head=head, expected_tree=tree,
            dependencies="fastapi==0.115.0\n")
        self.assertEqual(good["status"], "SOURCE_BOUND_CI_OBSERVATION", good)
        self.assertEqual(good["authority"], "NOT_GRANTED")
        self.assertEqual(good["image_signature"], "NOT_PRESENT")
        self.assertFalse(good["deployment_attested"])
        bad_cases = (
            (run | {"head_sha": "f"*40}, artifact, package, "SOURCE_WORKFLOW_UNTRUSTED"),
            (run | {"conclusion": "failure"}, artifact, package, "SOURCE_WORKFLOW_UNTRUSTED"),
            (run | {"path": ".github/workflows/other.yml"}, artifact, package, "SOURCE_WORKFLOW_UNTRUSTED"),
            (run, artifact | {"digest": "unsigned"}, package, "ARTIFACT_IDENTITY_MISMATCH"),
            (run, artifact | {"name": "other"}, package, "ARTIFACT_IDENTITY_MISMATCH"),
            (run, artifact | {"workflow_run": artifact["workflow_run"] | {"head_sha": "f"*40}},
             package, "ARTIFACT_IDENTITY_MISMATCH"),
            (run, artifact, package | {"final-image-receipt": final | {"authority": "ADMITTED"}},
             "IMAGE_SOURCE_BINDING_INVALID"),
            (run, artifact, package | {"github-readback": readback | {"authority": "ADMITTED"}},
             "GITHUB_READBACK_INCONSISTENT"),
        )
        for run_in, artifact_in, package_in, reason in bad_cases:
            with self.subTest(reason=reason):
                bad = mod.verify_ci_image_observation(
                    package_in, run_in, artifact_in, expected_head=head,
                    expected_tree=tree, dependencies="fastapi==0.115.0\n")
                self.assertEqual(bad["status"], "DENIED", bad)
                self.assertIn(reason, bad["reason_codes"])
        self.assertIn("DEPENDENCY_INVENTORY_MISSING", mod.verify_ci_image_observation(
            package, run, artifact, expected_head=head,
            expected_tree=tree, dependencies="")["reason_codes"])

    def test_existing_oidc_signer_attests_only_source_bound_ci_receipt(self) -> None:
        source = (ROOT / ".github/workflows/automaton-3.yml").read_text(encoding="utf-8")
        self.assertIn("Import exact-head read-only Docker CI observation", source)
        self.assertIn("Attest exact source-bound CI-local image observation", source)
        self.assertIn("Verify signed CI-local image observation", source)
        self.assertIn("scripts/ci_image_observation.py", source)
        self.assertIn("gh run download", source)
        self.assertIn("source_tree=$(git rev-parse", source)
        self.assertIn("final-image-receipt", (ROOT / "scripts/ci_image_observation.py").read_text())
        self.assertIn('"image_signature": "NOT_PRESENT"', source)
        self.assertIn('"authority": "NOT_GRANTED"', source)
        self.assertIn('if: github.event_name == \'pull_request\'', source)
        self.assertIn("gh attestation verify", source)
        self.assertNotIn("contents: write", source)
        self.assertNotIn("docker push", source)



if __name__ == "__main__":
    unittest.main(verbosity=2)
