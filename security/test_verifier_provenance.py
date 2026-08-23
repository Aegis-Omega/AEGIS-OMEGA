from __future__ import annotations

import copy
from hashlib import sha256
import json
import os
from pathlib import Path
import tempfile
import unittest

from security.glasswing_evidence import EVIDENCE_AUTHORITY
from security.verifier_provenance import (
    GITHUB_ACTIONS_OIDC_ISSUER,
    SLSA_PROVENANCE_V1,
    build_verifier_provenance_receipt,
    verify_attested_artifact_with_gh,
    verify_verifier_provenance_receipt,
)


SOURCE_COMMIT = "a" * 40
SUBJECT_DIGEST = "b" * 64
EVIDENCE_DIGEST = "c" * 64
VERIFICATION_OUTPUT_DIGEST = "d" * 64
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
SIGNER_WORKFLOW = "Aegis-Omega/AEGIS-OMEGA/.github/workflows/security-evidence-trace-bridge.yml"
SOURCE_REF = "refs/heads/trace/security-evidence-prooftrace-v1"


class VerifierProvenanceTests(unittest.TestCase):
    def build_receipt(self):
        return build_verifier_provenance_receipt(
            verifier_id="github-gh-attestation-verify",
            repository=REPOSITORY,
            signer_workflow=SIGNER_WORKFLOW,
            source_commit=SOURCE_COMMIT,
            source_ref=SOURCE_REF,
            subject_digest=SUBJECT_DIGEST,
            evidence_digest=EVIDENCE_DIGEST,
            verification_output_digest=VERIFICATION_OUTPUT_DIGEST,
            gh_cli_version="2.80.0",
            oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
            predicate_type=SLSA_PROVENANCE_V1,
        )

    def test_receipt_binds_named_verifier_subject_evidence_and_exact_source(self):
        receipt = self.build_receipt()

        self.assertEqual(receipt.authority, EVIDENCE_AUTHORITY)
        self.assertEqual(receipt.repository, REPOSITORY)
        self.assertEqual(receipt.signer_workflow, SIGNER_WORKFLOW)
        self.assertEqual(receipt.source_commit, SOURCE_COMMIT)
        self.assertEqual(receipt.source_ref, SOURCE_REF)
        self.assertEqual(receipt.subject_digest, SUBJECT_DIGEST)
        self.assertEqual(receipt.evidence_digest, EVIDENCE_DIGEST)
        self.assertEqual(receipt.verification_output_digest, VERIFICATION_OUTPUT_DIGEST)
        self.assertEqual(receipt.oidc_issuer, GITHUB_ACTIONS_OIDC_ISSUER)
        self.assertEqual(receipt.predicate_type, SLSA_PROVENANCE_V1)
        self.assertTrue(verify_verifier_provenance_receipt(receipt.to_dict()))

    def test_receipt_is_deterministic_for_identical_verified_inputs(self):
        first = self.build_receipt()
        second = self.build_receipt()

        self.assertEqual(first.receipt_digest, second.receipt_digest)
        self.assertEqual(first.to_dict(), second.to_dict())

    def test_any_bound_provenance_tamper_is_rejected(self):
        receipt = self.build_receipt().to_dict()
        mutations = {
            "repository": "attacker/repo",
            "signer_workflow": "attacker/repo/.github/workflows/fake.yml",
            "source_commit": "f" * 40,
            "source_ref": "refs/heads/main",
            "subject_digest": "1" * 64,
            "evidence_digest": "2" * 64,
            "verification_output_digest": "3" * 64,
            "oidc_issuer": "https://issuer.invalid",
            "predicate_type": "https://example.invalid/predicate",
        }

        for field, value in mutations.items():
            with self.subTest(field=field):
                tampered = copy.deepcopy(receipt)
                tampered[field] = value
                self.assertFalse(verify_verifier_provenance_receipt(tampered))

    def test_non_github_oidc_or_non_slsa_provenance_is_rejected_at_construction(self):
        with self.assertRaisesRegex(ValueError, "OIDC_ISSUER_MISMATCH"):
            build_verifier_provenance_receipt(
                verifier_id="github-gh-attestation-verify",
                repository=REPOSITORY,
                signer_workflow=SIGNER_WORKFLOW,
                source_commit=SOURCE_COMMIT,
                source_ref=SOURCE_REF,
                subject_digest=SUBJECT_DIGEST,
                evidence_digest=EVIDENCE_DIGEST,
                verification_output_digest=VERIFICATION_OUTPUT_DIGEST,
                gh_cli_version="2.80.0",
                oidc_issuer="https://issuer.invalid",
                predicate_type=SLSA_PROVENANCE_V1,
            )

        with self.assertRaisesRegex(ValueError, "PREDICATE_TYPE_MISMATCH"):
            build_verifier_provenance_receipt(
                verifier_id="github-gh-attestation-verify",
                repository=REPOSITORY,
                signer_workflow=SIGNER_WORKFLOW,
                source_commit=SOURCE_COMMIT,
                source_ref=SOURCE_REF,
                subject_digest=SUBJECT_DIGEST,
                evidence_digest=EVIDENCE_DIGEST,
                verification_output_digest=VERIFICATION_OUTPUT_DIGEST,
                gh_cli_version="2.80.0",
                oidc_issuer=GITHUB_ACTIONS_OIDC_ISSUER,
                predicate_type="https://example.invalid/predicate",
            )

    def test_receipt_never_persists_raw_attestation_token_certificate_or_output(self):
        payload = self.build_receipt().to_dict()

        forbidden = {
            "token",
            "oidc_token",
            "certificate",
            "signature",
            "attestation",
            "verification_output",
            "raw_output",
        }
        self.assertTrue(forbidden.isdisjoint(payload))
        self.assertEqual(set(payload), {
            "schema_version",
            "authority",
            "verifier_id",
            "verification_mechanism",
            "repository",
            "signer_workflow",
            "source_commit",
            "source_ref",
            "subject_digest",
            "evidence_digest",
            "verification_output_digest",
            "gh_cli_version",
            "oidc_issuer",
            "predicate_type",
            "receipt_digest",
        })

    def _fake_gh(self, root: Path) -> tuple[Path, Path]:
        args_path = root / "gh-args.json"
        gh_path = root / "fake-gh"
        gh_path.write_text(
            """#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

if sys.argv[1:] == [\"--version\"]:
    print(\"gh version 2.80.0 (fixture)\")
    raise SystemExit(0)

Path(os.environ[\"FAKE_GH_ARGS\"]).write_text(json.dumps(sys.argv[1:]), encoding=\"utf-8\")
if os.environ.get(\"FAKE_GH_FAIL\") == \"1\":
    print(\"verification failed\", file=sys.stderr)
    raise SystemExit(1)
if os.environ.get(\"FAKE_GH_BAD_JSON\") == \"1\":
    print(\"not-json\")
    raise SystemExit(0)
print(json.dumps([{
    \"verificationResult\": {
        \"signature\": {\"certificate\": {}},
        \"verifiedTimestamps\": [{}],
        \"statement\": {\"predicateType\": \"https://slsa.dev/provenance/v1\"}
    }
}], sort_keys=True, separators=(\",\", \":\")))
""",
            encoding="utf-8",
        )
        gh_path.chmod(0o755)
        return gh_path, args_path

    def test_executable_verifier_locks_identity_source_oidc_predicate_and_subject(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "security-evidence.json"
            artifact.write_bytes(b'{"evidence":"fixture"}\n')
            gh_path, args_path = self._fake_gh(root)
            previous = os.environ.get("FAKE_GH_ARGS")
            os.environ["FAKE_GH_ARGS"] = str(args_path)
            try:
                receipt = verify_attested_artifact_with_gh(
                    artifact_path=artifact,
                    evidence_digest=EVIDENCE_DIGEST,
                    repository=REPOSITORY,
                    signer_workflow=SIGNER_WORKFLOW,
                    source_commit=SOURCE_COMMIT,
                    source_ref=SOURCE_REF,
                    gh_bin=str(gh_path),
                )
            finally:
                if previous is None:
                    os.environ.pop("FAKE_GH_ARGS", None)
                else:
                    os.environ["FAKE_GH_ARGS"] = previous

            args = json.loads(args_path.read_text(encoding="utf-8"))
            self.assertEqual(args[0:3], ["attestation", "verify", str(artifact)])
            self.assertIn("--repo", args)
            self.assertEqual(args[args.index("--repo") + 1], REPOSITORY)
            self.assertEqual(args[args.index("--signer-workflow") + 1], SIGNER_WORKFLOW)
            self.assertEqual(args[args.index("--source-digest") + 1], SOURCE_COMMIT)
            self.assertEqual(args[args.index("--source-ref") + 1], SOURCE_REF)
            self.assertEqual(
                args[args.index("--cert-oidc-issuer") + 1],
                GITHUB_ACTIONS_OIDC_ISSUER,
            )
            self.assertEqual(
                args[args.index("--predicate-type") + 1], SLSA_PROVENANCE_V1
            )
            self.assertIn("--deny-self-hosted-runners", args)
            self.assertEqual(args[-2:], ["--format", "json"])
            self.assertEqual(receipt.subject_digest, sha256(artifact.read_bytes()).hexdigest())
            self.assertEqual(receipt.evidence_digest, EVIDENCE_DIGEST)
            self.assertEqual(receipt.gh_cli_version, "2.80.0")
            self.assertTrue(verify_verifier_provenance_receipt(receipt.to_dict()))

    def test_executable_verifier_fails_closed_on_nonzero_or_invalid_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            artifact = root / "security-evidence.json"
            artifact.write_text("{}\n", encoding="utf-8")
            gh_path, args_path = self._fake_gh(root)
            saved = {name: os.environ.get(name) for name in (
                "FAKE_GH_ARGS",
                "FAKE_GH_FAIL",
                "FAKE_GH_BAD_JSON",
            )}
            os.environ["FAKE_GH_ARGS"] = str(args_path)
            try:
                os.environ["FAKE_GH_FAIL"] = "1"
                with self.assertRaisesRegex(RuntimeError, "GH_ATTESTATION_VERIFY_FAILED"):
                    verify_attested_artifact_with_gh(
                        artifact_path=artifact,
                        evidence_digest=EVIDENCE_DIGEST,
                        repository=REPOSITORY,
                        signer_workflow=SIGNER_WORKFLOW,
                        source_commit=SOURCE_COMMIT,
                        source_ref=SOURCE_REF,
                        gh_bin=str(gh_path),
                    )

                os.environ.pop("FAKE_GH_FAIL", None)
                os.environ["FAKE_GH_BAD_JSON"] = "1"
                with self.assertRaisesRegex(RuntimeError, "GH_ATTESTATION_VERIFY_OUTPUT_INVALID"):
                    verify_attested_artifact_with_gh(
                        artifact_path=artifact,
                        evidence_digest=EVIDENCE_DIGEST,
                        repository=REPOSITORY,
                        signer_workflow=SIGNER_WORKFLOW,
                        source_commit=SOURCE_COMMIT,
                        source_ref=SOURCE_REF,
                        gh_bin=str(gh_path),
                    )
            finally:
                for name, value in saved.items():
                    if value is None:
                        os.environ.pop(name, None)
                    else:
                        os.environ[name] = value


if __name__ == "__main__":
    unittest.main()
