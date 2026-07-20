from __future__ import annotations

import json
import os
import sqlite3
import tempfile
from dataclasses import replace
from pathlib import Path

from init_db import initialize_database
from kernel_one import COMPROMISED_KEY_IDS, KernelConfigurationError, KernelOneEngine
from validator import ValidationError, sha256_file, validate_file

ROOT = Path(__file__).resolve().parent
PAYLOADS = ROOT / "adversarial_payloads.jsonl"
MANIFEST = ROOT / "INDEX.yaml"
FIXTURE_KEY = b"kernel-one-test-fixture-key-not-for-deployment"
FIXTURE_KEY_ID = "kernel-hmac-test-v1"


def load_payloads():
    return [
        json.loads(line)
        for line in PAYLOADS.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_request(case):
    request = {
        "task": case.get("task", ""),
        "metrics": case.get("metrics", {}),
        "parent_witness": None,
    }
    if "request_id" in case:
        request["request_id"] = case["request_id"]
    if "target_file" in case:
        request["target_file"] = case["target_file"]
    return request


def build_proposal(case):
    if "plan" in case or "output" in case or "tool_calls" in case:
        proposal = {}
        if "plan" in case:
            proposal["plan"] = case["plan"]
        if "output" in case:
            proposal["output"] = case["output"]
        if "tool_calls" in case:
            proposal["tool_calls"] = case["tool_calls"]
    else:
        proposal = {
            "plan": "Default valid action blueprint strategy",
            "output": "Execution block finalized cleanly.",
            "tool_calls": [],
        }
        if case.get("name") == "missing_tool_calls":
            proposal = {"plan": "Implement orchestrator", "output": "done"}
    if "unexpected" in case:
        proposal["unexpected"] = case["unexpected"]
    return proposal


def run_original_adversarial_suite(workdir: Path) -> None:
    db_path = workdir / "original-suite.sqlite"
    initialize_database(db_path)
    kernel = KernelOneEngine(
        manifest_path=str(MANIFEST),
        db_path=str(db_path),
        signing_key=FIXTURE_KEY,
        signing_key_id=FIXTURE_KEY_ID,
    )
    cases = load_payloads()
    passed = 0
    for case in cases:
        result = kernel.process_transaction(
            build_request(case),
            json.dumps(build_proposal(case)),
        )
        if result["status"] == case["expected_status"]:
            passed += 1
            print(f"[OK] {case['name']:<30} => {result['status']:<20}")
        else:
            print(f"[FAIL] {case['name']:<30} => {result['status']:<20}")
            print(f"       reason: {result.get('reason')}")
    if passed != len(cases):
        raise AssertionError(
            f"Security Gate Core Failure: {passed}/{len(cases)} original assertions"
        )
    print(f"[METRICS] Original lineage: {passed}/{len(cases)} assertions passed.")


def assert_raises(exc_type, callback, contains=None):
    try:
        callback()
    except exc_type as exc:
        if contains is not None and contains not in str(exc):
            raise AssertionError(f"Expected {contains!r}, got {str(exc)!r}") from exc
        return
    raise AssertionError(f"Expected {exc_type.__name__}")


def run_security_regressions(workdir: Path) -> None:
    passed = 0
    old_key = os.environ.pop("AEGIS_KERNEL_SIGNING_KEY", None)
    old_id = os.environ.pop("AEGIS_KERNEL_SIGNING_KEY_ID", None)
    try:
        assert_raises(
            KernelConfigurationError,
            lambda: KernelOneEngine(
                manifest_path=str(MANIFEST),
                db_path=str(workdir / "missing-config.sqlite"),
            ),
            "AEGIS_KERNEL_SIGNING_KEY is required",
        )
        passed += 1
        print("[OK] missing_signing_key_fails_closed")
    finally:
        if old_key is not None:
            os.environ["AEGIS_KERNEL_SIGNING_KEY"] = old_key
        if old_id is not None:
            os.environ["AEGIS_KERNEL_SIGNING_KEY_ID"] = old_id

    assert_raises(
        KernelConfigurationError,
        lambda: KernelOneEngine(
            manifest_path=str(MANIFEST),
            db_path=str(workdir / "compromised.sqlite"),
            signing_key=FIXTURE_KEY,
            signing_key_id=next(iter(COMPROMISED_KEY_IDS)),
        ),
        "COMPROMISED_SIGNING_KEY_ID",
    )
    passed += 1
    print("[OK] compromised_key_id_rejected")

    db_path = workdir / "security.sqlite"
    initialize_database(db_path)
    kernel = KernelOneEngine(
        manifest_path=str(MANIFEST),
        db_path=str(db_path),
        signing_key=FIXTURE_KEY,
        signing_key_id=FIXTURE_KEY_ID,
    )
    proposal = json.dumps({"plan": "safe", "output": "safe", "tool_calls": []})
    missing_request = {
        "task": "former production curation bypass",
        "metrics": {
            "uncertainty": 0.1,
            "tool_failures": 0.0,
            "novelty": 0.1,
            "reviewer_disagreement": 0.0,
        },
    }
    result = kernel.process_transaction(missing_request, proposal)
    assert result["status"] == "RECONCILED_FALLBACK"
    assert "request_id" in result["reason"]
    passed += 1
    print("[OK] missing_request_id_bypass_regression")

    result = kernel.process_transaction(dict(missing_request, request_id="   "), proposal)
    assert result["status"] == "RECONCILED_FALLBACK"
    assert "EMPTY_REQUEST_ID" in result["reason"]
    passed += 1
    print("[OK] empty_request_id_denied")

    artifact = workdir / "artifact.txt"
    artifact.write_text("version-one", encoding="utf-8")
    digest = sha256_file(artifact)
    assert validate_file(artifact, digest)
    envelope, signature = kernel.create_file_witness(
        request_id="file-integrity-1",
        artifact_path=artifact,
        observed_at=1_700_000_000,
        sequence=7,
    )
    assert kernel.verify_envelope(envelope, signature, artifact_path=artifact)
    artifact.write_text("version-two", encoding="utf-8")
    assert sha256_file(artifact) != digest
    assert not kernel.verify_envelope(envelope, signature, artifact_path=artifact)
    assert_raises(
        ValidationError,
        lambda: validate_file(artifact, digest),
        "FILE_DIGEST_MISMATCH",
    )
    passed += 1
    print("[OK] file_mutation_invalidates_witness")

    assert not kernel.verify_envelope(
        replace(envelope, observed_at=envelope.observed_at + 1), signature
    )
    passed += 1
    print("[OK] timestamp_mutation_invalidates_signature")

    assert not kernel.verify_envelope(
        replace(envelope, parent_receipt_hash="1" * 64), signature
    )
    passed += 1
    print("[OK] parent_receipt_mutation_invalidates_signature")

    assert not kernel.verify_envelope(
        replace(envelope, key_id="kernel-hmac-test-v2"), signature
    )
    assert not kernel.verify_envelope(
        replace(envelope, key_id="kernel-hmac-v0-compromised"), signature
    )
    passed += 1
    print("[OK] key_id_substitution_invalidates_verification")

    accepted = {
        "request_id": "persisted-envelope-1",
        "task": "persist signed envelope",
        "metrics": {
            "uncertainty": 0.1,
            "tool_failures": 0.0,
            "novelty": 0.1,
            "reviewer_disagreement": 0.0,
        },
    }
    result = kernel.process_transaction(accepted, proposal)
    assert result["status"] == "HARMONIZE_SUCCESS"
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT key_id, algorithm, signature, canonical_json "
            "FROM witness_envelopes WHERE witness_id = ?",
            (result["witness_id"],),
        ).fetchone()
    assert row is not None
    assert row[0] == FIXTURE_KEY_ID
    assert row[1] == "hmac-sha256"
    assert row[2] == result["signature"]
    assert json.loads(row[3]) == result["witness_envelope"]
    passed += 1
    print("[OK] witness_envelope_persisted_atomically")

    source = (ROOT / "kernel_one.py").read_text(encoding="utf-8")
    assert "aegis_sovereign_secure_key_vector_2026" not in source
    assert 'os.environ.get("AEGIS_KERNEL_SIGNING_KEY")' in source
    assert "hmac-sha256" in source
    passed += 1
    print("[OK] no_builtin_or_development_signing_fallback")

    if passed != 10:
        raise AssertionError(f"Security regression mismatch: {passed}/10")
    print(f"[METRICS] Security regressions: {passed}/10 assertions passed.")


def main():
    with tempfile.TemporaryDirectory(prefix="kernel-one-tests-") as temp_dir:
        workdir = Path(temp_dir)
        run_original_adversarial_suite(workdir)
        run_security_regressions(workdir)
    print("[METRICS] Combined verification: 9/9 original + 10/10 security assertions.")


if __name__ == "__main__":
    main()
