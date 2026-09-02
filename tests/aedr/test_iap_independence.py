from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

from scripts.aedr.iap_verifier import IAP_PREDICATE_TYPE, build_iap_predicate, verify_iap
from scripts.aedr.surface_producer import _canonical_json, build_surface_document


REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
WORKFLOW = ".github/workflows/aedr-multilayer-dag.yml"
PR_NUMBER = 376
HEAD_SHA = "a" * 40
RUN_ID = 33590857525
SIGNER_DIGEST = "b" * 40


def test_j3_digest_match_does_not_claim_independent_falsifier_authenticity(
    tmp_path: Path, monkeypatch
) -> None:
    manifest = {
        "schema_version": "AEDR-FALSIFIER-MANIFEST-V1",
        "required_behavior_ids": ["BEHAVIOR_A"],
        "required_falsifier_ids": ["FALSIFIER_A"],
        "unique_non_generated_paths": ["scripts/aedr/example.py"],
        "assumption_identities": ["ASSUMP_A"],
        "security_exposure_identities": ["SECURITY_A"],
    }
    document = build_surface_document(
        manifest,
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        run_id=RUN_ID,
    )
    surface = tmp_path / "aedr-surface.json"
    surface.write_bytes(_canonical_json(document) + b"\n")
    predicate = build_iap_predicate(
        surface,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
    )
    subject_digest = hashlib.sha256(surface.read_bytes()).hexdigest()
    verification = [{
        "attestation": {"bundle": "verified-by-gh"},
        "verificationResult": {
            "statement": {
                "_type": "https://in-toto.io/Statement/v1",
                "predicateType": IAP_PREDICATE_TYPE,
                "subject": [{"name": surface.name, "digest": {"sha256": subject_digest}}],
                "predicate": predicate,
            },
            "signature": {"certificate": {
                "issuer": "https://token.actions.githubusercontent.com",
                "subjectAlternativeName": f"https://github.com/{REPOSITORY}/{WORKFLOW}@refs/pull/376/merge",
                "githubWorkflowRepository": REPOSITORY,
                "buildSignerURI": f"https://github.com/{REPOSITORY}/{WORKFLOW}@refs/pull/376/merge",
                "buildSignerDigest": SIGNER_DIGEST,
                "runnerEnvironment": "github-hosted",
                "sourceRepositoryURI": f"https://github.com/{REPOSITORY}",
                "sourceRepositoryDigest": SIGNER_DIGEST,
                "sourceRepositoryRef": "refs/pull/376/merge",
                "runInvocationURI": f"https://github.com/{REPOSITORY}/actions/runs/{RUN_ID}/attempts/1",
            }},
            "verifiedTimestamps": [{"type": "Tlog", "uri": "https://rekor.sigstore.dev"}],
        },
    }]

    monkeypatch.setattr(
        subprocess,
        "run",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, stdout=json.dumps(verification), stderr=""
        ),
    )

    receipt = verify_iap(
        surface,
        repository=REPOSITORY,
        workflow_path=WORKFLOW,
        expected_pr=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_run_id=RUN_ID,
        trusted_signer_digest=SIGNER_DIGEST,
    )

    assert receipt["j3_status"] == "PASS"
    assert receipt["trusted_signer_policy_match"] == "ESTABLISHED"
    assert receipt["independent_falsifier_authenticity"] == "NOT_ESTABLISHED"
    assert receipt["authority_effect"] == "NONE"
