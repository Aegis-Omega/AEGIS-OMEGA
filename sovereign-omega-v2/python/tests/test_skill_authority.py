from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.skill_authority import (  # noqa: E402
    OBSERVED,
    UNOBSERVED,
    compute_registry_root,
    evaluate_registry,
    safe_competency_score,
    sanitize_legacy_tree,
)


def legacy_tree() -> dict:
    return {
        "version": "1.0.0",
        "phase": 1,
        "generated_at": "2026-05-31T09:25:24+00:00",
        "genesis_seal": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        "doc_count": 1,
        "skills": [{
            "skill_id": "example",
            "label": "Example",
            "domain": "test",
            "tier": "T0",
            "confidence": 0.95,
            "validated_runs": 0,
            "failure_rate": 0.0,
            "recency_score": 1.0,
            "domain_affinity": ["test"],
            "dependencies": [],
            "evidence_refs": ["evidence.md"],
            "last_validated": "2026-05-31T09:25:24+00:00",
            "description": "documentation only",
        }],
    }


def test_zero_run_documentation_is_not_operational_authority() -> None:
    tree = sanitize_legacy_tree(legacy_tree(), source_commit="a" * 40)
    skill = tree["skills"][0]
    assert skill["observation_state"] == UNOBSERVED
    assert skill["documentation_prior"] == 0.95
    assert skill["confidence"] == 0.0
    assert skill["recency_score"] == 0.0
    assert skill["last_validated"] is None
    assert safe_competency_score(skill) == 0.0


def test_under_observed_skill_fails_closed_even_with_high_metrics() -> None:
    skill = {
        "observation_state": OBSERVED,
        "validated_runs": 2,
        "confidence": 1.0,
        "recency_score": 1.0,
        "failure_rate": 0.0,
    }
    assert safe_competency_score(skill) == 0.0


def test_observed_claim_without_independent_receipts_is_non_authoritative() -> None:
    # Three declared runs are not three independently observed successes.
    skill = {
        "observation_state": OBSERVED,
        "validated_runs": 3,
        "confidence": 0.8,
        "recency_score": 0.5,
        "failure_rate": 0.25,
        "last_validated": "2026-07-19T00:00:00Z",
    }
    assert safe_competency_score(skill) == 0.0


def synthetic_receipt_skill() -> dict:
    """A pure contract fixture, never an authenticated production evaluation."""
    receipts = [{
        "schema_version": "1.0.0",
        "receipt_kind": "AEGIS_SKILL_OBSERVATION_RECEIPT_V1",
        "receipt_id": f"receipt-{index}",
        "run_id": f"run-{index}",
        "skill_id": "candidate",
        "outcome": "SUCCEEDED",
        "source_commit": "a" * 40,
        "task_sha256": "1" * 64,
        "result_sha256": "2" * 64,
        "evaluator_receipt_sha256": "3" * 64,
        "agent_id": "test-agent",
        "reviewer_id": "test-independent-evaluator",
        "reviewer_signature_ref": f"test-signature-{index}",
        "review_status": "PASSED",
        "adjudicated_confidence": 0.8,
        "observed_at": f"2026-11-14T00:00:0{index}Z",
    } for index in range(3)]
    return {
        "skill_id": "candidate",
        "observation_state": OBSERVED,
        "validated_runs": 3,
        "confidence": 0.8,
        "recency_score": 0.5,
        "failure_rate": 0.0,
        "failure_rate_observed": 0.0,
        "last_validated": receipts[-1]["observed_at"],
        "observation_receipts": receipts,
    }


def _test_only_admitted_receipt(receipt: dict) -> str:
    # Deliberately a test double, not a real signature/issuer verifier.
    return str(receipt["evaluator_receipt_sha256"])


def test_scoring_requires_host_authenticated_test_receipts() -> None:
    skill = synthetic_receipt_skill()
    assert safe_competency_score(skill) == 0.0
    assert safe_competency_score(
        skill, evidence_verifier=_test_only_admitted_receipt
    ) == pytest.approx(0.4)


def test_untrusted_verifier_digest_or_review_cannot_grant_score() -> None:
    skill = synthetic_receipt_skill()
    assert safe_competency_score(skill, evidence_verifier=lambda _: "0" * 64) == 0.0
    skill["observation_receipts"][0]["reviewer_id"] = "test-agent"
    assert safe_competency_score(
        skill, evidence_verifier=_test_only_admitted_receipt
    ) == 0.0


def test_injected_metrics_or_duplicate_runs_are_rejected() -> None:
    skill = synthetic_receipt_skill()
    skill["confidence"] = 0.99
    assert safe_competency_score(
        skill, evidence_verifier=_test_only_admitted_receipt
    ) == 0.0
    skill = synthetic_receipt_skill()
    skill["failure_rate"] = 0.1
    assert safe_competency_score(
        skill, evidence_verifier=_test_only_admitted_receipt
    ) == 0.0
    skill = synthetic_receipt_skill()
    skill["observation_receipts"][1]["run_id"] = skill["observation_receipts"][0]["run_id"]
    assert safe_competency_score(
        skill, evidence_verifier=_test_only_admitted_receipt
    ) == 0.0


def test_observed_registry_without_host_verifier_denied() -> None:
    skill = synthetic_receipt_skill()
    skill["evidence_refs"] = ["evidence.md"]
    tree = {
        "schema_version": "2.0.0",
        "authority_state": "NON_AUTHORITATIVE_UNTIL_OBSERVED",
        "skills": [skill],
    }
    tree["registry_root"] = compute_registry_root(tree)
    tree["genesis_seal"] = tree["registry_root"]
    assert evaluate_registry(tree).outcome == "DENIED"
    assert evaluate_registry(
        tree, evidence_verifier=_test_only_admitted_receipt
    ).outcome == "ADMITTED"


def test_sanitization_is_deterministic() -> None:
    first = sanitize_legacy_tree(legacy_tree(), source_commit="b" * 40)
    second = sanitize_legacy_tree(legacy_tree(), source_commit="b" * 40)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
    assert first["registry_root"] == second["registry_root"]


def test_registry_root_detects_tampering() -> None:
    tree = sanitize_legacy_tree(legacy_tree(), source_commit="c" * 40)
    tampered = copy.deepcopy(tree)
    tampered["skills"][0]["description"] = "changed"
    receipt = evaluate_registry(tampered)
    assert receipt.outcome == "DENIED"
    assert "TREE: registry_root mismatch" in receipt.violations
    assert compute_registry_root(tampered) != tree["registry_root"]


def test_unresolved_evidence_fails_closed(tmp_path: Path) -> None:
    tree = sanitize_legacy_tree(legacy_tree(), source_commit="d" * 40)
    receipt = evaluate_registry(tree, repo_root=tmp_path)
    assert receipt.outcome == "DENIED"
    assert any("unresolved evidence_ref" in item for item in receipt.violations)


def test_resolved_evidence_is_admitted(tmp_path: Path) -> None:
    (tmp_path / "evidence.md").write_text("# evidence\n", encoding="utf-8")
    tree = sanitize_legacy_tree(legacy_tree(), source_commit="e" * 40)
    receipt = evaluate_registry(tree, repo_root=tmp_path)
    assert receipt.outcome == "ADMITTED"
    assert receipt.violation_count == 0


def test_committed_registry_is_content_bound_and_non_authoritative() -> None:
    tree = json.loads((REPO_ROOT / "harness" / "skill_tree.json").read_text(encoding="utf-8"))
    receipt = evaluate_registry(tree)
    assert receipt.outcome == "ADMITTED"
    assert tree["authority_state"] == "NON_AUTHORITATIVE_UNTIL_OBSERVED"
    assert all(safe_competency_score(skill) == 0.0 for skill in tree["skills"] if skill["validated_runs"] == 0)
