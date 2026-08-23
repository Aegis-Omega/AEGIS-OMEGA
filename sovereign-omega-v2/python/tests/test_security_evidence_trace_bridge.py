from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from harness.sdk.proof_trace import (
    NO_AUTHORITY,
    OK,
    T2,
    VERIFIER,
    ProofTraceError,
    TraceSDK,
    verify_trace_bundle,
)
from harness.sdk.security_evidence_trace import (
    bind_verified_security_evidence,
    verify_and_bind_attested_security_evidence,
)
from security.glasswing_evidence import EVIDENCE_AUTHORITY, SecurityDisposition
from security.security_evidence_set import (
    SecurityEvidenceReference,
    build_security_evidence_set,
    verify_security_evidence_set,
)

COMMIT = "a" * 40
POLICY = "b" * 64
STATE0 = "c" * 64
SUBJECT = "d" * 64
METADATA = "e" * 64
REPOSITORY = "Aegis-Omega/AEGIS-OMEGA"
SIGNER_WORKFLOW = "Aegis-Omega/AEGIS-OMEGA/.github/workflows/security-evidence-trace-bridge.yml"
SOURCE_REF = "refs/heads/trace/security-evidence-prooftrace-v1"


def new_trace(nonce: str = "security-evidence-bridge"):
    return TraceSDK.start_trace(
        workflow_name="security-evidence-proofline",
        source_commit=COMMIT,
        policy_commitment=POLICY,
        genesis_control_state_root=STATE0,
        deterministic_nonce=nonce,
        metadata={"suite": "security-evidence-bridge", "raw_payloads": False},
    )


def reference(
    *,
    kind: str = "GLASSWING",
    evidence_digest: str = "1" * 64,
    disposition: SecurityDisposition = SecurityDisposition.CLEAN_WITHIN_COVERAGE,
    independence: str = "INDEPENDENT_CHECK",
) -> SecurityEvidenceReference:
    return SecurityEvidenceReference.create(
        evidence_kind=kind,
        producer_id=f"{kind.lower()}-fixture",
        subject_digest=SUBJECT,
        evidence_digest=evidence_digest,
        disposition=disposition,
        authority=EVIDENCE_AUTHORITY,
        independence=independence,
        metadata_digest=METADATA,
    )


def evidence_set(
    *,
    member: SecurityEvidenceReference | None = None,
    required_kinds=("GLASSWING",),
):
    return build_security_evidence_set(
        subject_root=SUBJECT,
        members=[member or reference()],
        required_kinds=required_kinds,
    )


def write_set(path: Path, security_set) -> None:
    path.write_text(
        json.dumps(security_set.to_dict(), sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def fake_gh(root: Path, *, fail: bool = False) -> tuple[Path, Path]:
    args_path = root / "gh-args.json"
    gh_path = root / "fake-gh"
    gh_path.write_text(
        f"""#!/usr/bin/env python3
import json
import os
from pathlib import Path
import sys

if sys.argv[1:] == [\"--version\"]:
    print(\"gh version 2.80.0 (fixture)\")
    raise SystemExit(0)
Path(os.environ[\"FAKE_GH_ARGS\"]).write_text(json.dumps(sys.argv[1:]), encoding=\"utf-8\")
if {str(fail)}:
    print(\"attestation rejected\", file=sys.stderr)
    raise SystemExit(1)
print(json.dumps([{{
    \"verificationResult\": {{
        \"signature\": {{\"certificate\": {{}}}},
        \"verifiedTimestamps\": [{{}}],
        \"statement\": {{\"predicateType\": \"https://slsa.dev/provenance/v1\"}}
    }}
}}], sort_keys=True, separators=(\",\", \":\")))
""",
        encoding="utf-8",
    )
    gh_path.chmod(0o755)
    return gh_path, args_path


def test_bridge_reruns_verifier_and_binds_set_and_verification_roots():
    trace = new_trace()
    security_set = evidence_set()
    expected = verify_security_evidence_set(security_set.to_dict())

    binding = bind_verified_security_evidence(trace, security_set.to_dict())

    assert binding.verification == expected
    assert binding.span.span_kind == VERIFIER
    assert binding.span.status == OK
    assert binding.span.authority_class == NO_AUTHORITY
    assert binding.span.epistemic_tier == T2
    assert binding.span.evidence_roots == (
        security_set.set_digest,
        expected.verification_root,
    )
    assert binding.span.control_state_before == STATE0
    assert binding.span.control_state_after == STATE0

    bundle = trace.close()
    verified = verify_trace_bundle(bundle)
    assert verified.valid is True
    assert bundle.spans[0].evidence_roots == binding.span.evidence_roots


def test_blocked_set_is_bound_as_evidence_without_becoming_authority():
    trace = new_trace("security-evidence-blocked")
    security_set = evidence_set(
        member=reference(disposition=SecurityDisposition.BLOCKED),
    )

    binding = bind_verified_security_evidence(trace, security_set.to_dict())

    assert binding.verification.integrity_valid is True
    assert binding.verification.complete is True
    assert binding.verification.aggregate_disposition == SecurityDisposition.BLOCKED
    assert binding.span.status == OK
    assert binding.span.authority_class == NO_AUTHORITY
    assert binding.span.control_state_before == binding.span.control_state_after == STATE0
    assert verify_trace_bundle(trace.close()).valid is True


def test_incomplete_set_remains_error_evidence_and_cannot_advance_state():
    trace = new_trace("security-evidence-incomplete")
    security_set = evidence_set(required_kinds=("GLASSWING", "OSV"))

    binding = bind_verified_security_evidence(trace, security_set.to_dict())

    assert binding.verification.integrity_valid is True
    assert binding.verification.complete is False
    assert binding.verification.aggregate_disposition == SecurityDisposition.ERROR
    assert "MISSING_REQUIRED_KIND:OSV" in binding.verification.reasons
    assert binding.span.authority_class == NO_AUTHORITY
    assert binding.span.control_state_before == binding.span.control_state_after == STATE0
    assert verify_trace_bundle(trace.close()).valid is True


def test_tampered_set_is_rejected_before_any_trace_span_is_committed():
    trace = new_trace("security-evidence-tampered")
    payload = evidence_set().to_dict()
    payload["members"][0]["evidence_digest"] = "9" * 64

    with pytest.raises(ProofTraceError) as exc:
        bind_verified_security_evidence(trace, payload)

    assert exc.value.code == "SECURITY_EVIDENCE_SET_INTEGRITY_INVALID"
    bundle = trace.close()
    assert bundle.spans == ()
    assert bundle.final_control_state_root == STATE0
    assert verify_trace_bundle(bundle).valid is True


def test_bridge_api_accepts_set_payload_not_preasserted_verifier_receipt():
    trace = new_trace("security-evidence-self-assertion")
    security_set = evidence_set()
    forged_receipt = {
        "integrity_valid": True,
        "complete": True,
        "aggregate_disposition": "CLEAN_WITHIN_COVERAGE",
        "verification_root": "f" * 64,
    }

    with pytest.raises(TypeError):
        bind_verified_security_evidence(
            trace,
            security_set.to_dict(),
            verification_receipt=forged_receipt,
        )


def test_attested_bridge_verifies_artifact_then_binds_provenance_root(tmp_path, monkeypatch):
    trace = new_trace("security-evidence-attested")
    security_set = evidence_set()
    artifact = tmp_path / "security-evidence-set.json"
    write_set(artifact, security_set)
    gh_path, args_path = fake_gh(tmp_path)
    monkeypatch.setenv("FAKE_GH_ARGS", str(args_path))

    binding = verify_and_bind_attested_security_evidence(
        trace,
        artifact_path=artifact,
        repository=REPOSITORY,
        signer_workflow=SIGNER_WORKFLOW,
        source_commit=COMMIT,
        source_ref=SOURCE_REF,
        gh_bin=str(gh_path),
    )

    assert binding.verification.integrity_valid is True
    assert binding.provenance.evidence_digest == security_set.set_digest
    assert binding.provenance.source_commit == COMMIT
    assert binding.span.span_kind == VERIFIER
    assert binding.span.authority_class == NO_AUTHORITY
    assert binding.span.epistemic_tier == T2
    assert binding.span.evidence_roots == (
        security_set.set_digest,
        binding.verification.verification_root,
        binding.provenance.receipt_digest,
    )
    assert binding.span.control_state_before == binding.span.control_state_after == STATE0
    assert verify_trace_bundle(trace.close()).valid is True

    args = json.loads(args_path.read_text(encoding="utf-8"))
    assert args[0:3] == ["attestation", "verify", str(artifact)]
    assert args[args.index("--source-digest") + 1] == COMMIT


def test_attested_bridge_failure_commits_no_span(tmp_path, monkeypatch):
    trace = new_trace("security-evidence-attestation-failure")
    security_set = evidence_set()
    artifact = tmp_path / "security-evidence-set.json"
    write_set(artifact, security_set)
    gh_path, args_path = fake_gh(tmp_path, fail=True)
    monkeypatch.setenv("FAKE_GH_ARGS", str(args_path))

    with pytest.raises(RuntimeError, match="GH_ATTESTATION_VERIFY_FAILED"):
        verify_and_bind_attested_security_evidence(
            trace,
            artifact_path=artifact,
            repository=REPOSITORY,
            signer_workflow=SIGNER_WORKFLOW,
            source_commit=COMMIT,
            source_ref=SOURCE_REF,
            gh_bin=str(gh_path),
        )

    bundle = trace.close()
    assert bundle.spans == ()
    assert bundle.final_control_state_root == STATE0
    assert verify_trace_bundle(bundle).valid is True


def test_attested_bridge_reads_artifact_and_rejects_tampered_set_before_trace(tmp_path, monkeypatch):
    trace = new_trace("security-evidence-attested-tamper")
    payload = evidence_set().to_dict()
    payload["members"][0]["evidence_digest"] = "9" * 64
    artifact = tmp_path / "security-evidence-set.json"
    artifact.write_text(json.dumps(payload), encoding="utf-8")
    gh_path, args_path = fake_gh(tmp_path)
    monkeypatch.setenv("FAKE_GH_ARGS", str(args_path))

    with pytest.raises(ProofTraceError) as exc:
        verify_and_bind_attested_security_evidence(
            trace,
            artifact_path=artifact,
            repository=REPOSITORY,
            signer_workflow=SIGNER_WORKFLOW,
            source_commit=COMMIT,
            source_ref=SOURCE_REF,
            gh_bin=str(gh_path),
        )

    assert exc.value.code == "SECURITY_EVIDENCE_SET_INTEGRITY_INVALID"
    assert trace.close().spans == ()


def test_attested_bridge_rejects_caller_supplied_provenance_receipt(tmp_path):
    trace = new_trace("security-evidence-provenance-injection")
    artifact = tmp_path / "security-evidence-set.json"
    write_set(artifact, evidence_set())

    with pytest.raises(TypeError):
        verify_and_bind_attested_security_evidence(
            trace,
            artifact_path=artifact,
            repository=REPOSITORY,
            signer_workflow=SIGNER_WORKFLOW,
            source_commit=COMMIT,
            source_ref=SOURCE_REF,
            provenance_receipt={"receipt_digest": "f" * 64},
        )
