"""Regression tests for archival mesh integrity and authenticated input binding.

This runs against the repository's evaluator.py, not a reimplemented verifier.
No network, model invocation, token usage or real contract approval.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "sovereign-mesh/nodes/auditor/evaluator.py"
_SPEC = importlib.util.spec_from_file_location("aegis_mesh_integrity_under_test", SOURCE)
assert _SPEC is not None and _SPEC.loader is not None
mesh = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = mesh
_SPEC.loader.exec_module(mesh)


def digest(content: str) -> str:
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


@pytest.mark.parametrize("wrong", ["", "0" * 64, "f" * 64, "bad", None])
def test_reject_wrong_or_missing_digest(wrong):
    assert mesh.GenesisVerifier().verify_artifact(
        "tampered artifact with sufficient characters", wrong
    )[0] is False


def test_reject_short_prefix_even_if_it_matches():
    content = "actual artifact"
    assert mesh.GenesisVerifier().verify_artifact(content, digest(content)[:8])[0] is False


def test_accept_full_digest_then_reject_single_byte_change():
    verifier = mesh.GenesisVerifier()
    assert verifier.verify_artifact("payload", digest("payload"))[0] is True
    assert verifier.verify_artifact("payload!", digest("payload"))[0] is False


def test_sprint_result_full_hash_only():
    verifier = mesh.GenesisVerifier()
    result = {"run": "r1", "value": 1}
    raw = json.dumps(result, sort_keys=True, separators=(",", ":"),
                     ensure_ascii=False, allow_nan=False).encode("utf-8")
    expected = hashlib.sha256(raw).hexdigest()
    assert verifier.verify_sprint_result(result, expected) is True
    assert verifier.verify_sprint_result(result, expected[:8]) is False
    assert verifier.verify_sprint_result(result, "") is False
    assert verifier.verify_sprint_result({"value": float("nan")}, expected) is False


def evaluate(tmp_path: Path, *, contract_hashes=None, artifact_content="legitimate output",
             tamper_directive=False, artifacts_override=None, artifact_claim=False):
    directive = "build a testable solution"
    contract = {
        "sprint_id": "test-001",
        "directive": directive + "!" if tamper_directive else directive,
        "nuqta_seal": digest(directive),
    }
    if contract_hashes is not None:
        contract["artifact_sha256"] = contract_hashes
    artifacts = [{"file_path": "src/main.py", "content": artifact_content}]
    if artifact_claim:
        artifacts[0]["sha256"] = digest(artifact_content)
    payload = {
        "artifacts": artifacts if artifacts_override is None else artifacts_override,
        "documentation": "",
    }
    contract_path = tmp_path / "contract.json"
    result_path = tmp_path / "result.json"
    contract_path.write_text(json.dumps(contract), encoding="utf-8")
    result_path.write_text(json.dumps(payload), encoding="utf-8")
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"state_dir": str(tmp_path / "state")}), encoding="utf-8")
    node = mesh.EvaluatorNode(str(config_path))
    # Isolate the integrity gate; simulated tests do not constitute admission.
    node.playwright.run_tests = lambda _: {"coverage": 1.0, "tests_failed": 0, "tests_passed": 1}
    return node.evaluate_sprint(str(result_path), str(contract_path))


def test_missing_contract_artifact_manifest_fails_closed(tmp_path):
    result = evaluate(tmp_path)
    assert result.genesis_seal_verified is False
    assert result.verdict is mesh.Verdict.REJECT_REROLL


def test_self_claimed_artifact_digest_is_not_trusted(tmp_path):
    assert evaluate(tmp_path, artifact_claim=True).genesis_seal_verified is False


def test_empty_artifact_list_does_not_vacuously_verify(tmp_path):
    assert evaluate(tmp_path, contract_hashes={}, artifacts_override=[]).genesis_seal_verified is False


def test_trusted_contract_hash_can_match_bytes(tmp_path):
    expected = {"src/main.py": digest("legitimate output")}
    assert evaluate(tmp_path, contract_hashes=expected).genesis_seal_verified is True


def test_tampered_artifact_fails_with_original_manifest(tmp_path):
    expected = {"src/main.py": digest("legitimate output")}
    assert evaluate(
        tmp_path, contract_hashes=expected, artifact_content="modified output",
    ).genesis_seal_verified is False


def test_tampered_directive_fails_even_if_artifact_matches(tmp_path):
    expected = {"src/main.py": digest("legitimate output")}
    assert evaluate(
        tmp_path, contract_hashes=expected, tamper_directive=True,
    ).genesis_seal_verified is False


def test_extra_manifest_reference_fails(tmp_path):
    expected = {"src/main.py": digest("legitimate output"), "src/ghost.py": "f" * 64}
    assert evaluate(tmp_path, contract_hashes=expected).genesis_seal_verified is False


def test_missing_or_duplicate_artifact_paths_fail(tmp_path):
    good_hash = digest("legitimate output")
    expected = {"src/main.py": good_hash, "src/extra.py": good_hash}
    dup = [
        {"file_path": "src/main.py", "content": "legitimate output"},
        {"file_path": "src/main.py", "content": "legitimate output"},
    ]
    assert evaluate(
        tmp_path, contract_hashes=expected, artifacts_override=dup,
    ).genesis_seal_verified is False
    assert evaluate(tmp_path, contract_hashes=expected, artifacts_override=None).genesis_seal_verified is False
