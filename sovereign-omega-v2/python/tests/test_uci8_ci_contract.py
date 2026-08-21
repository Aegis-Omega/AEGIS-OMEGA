from __future__ import annotations

from pathlib import Path

WORKFLOW = Path(".github/workflows/uci-8-evaluation-campaign.yml")
EXPECTED_PARENT = "1aa405975e2b3f3c1b1c0022a6b75e0b21d395ec"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_uci8_workflow_is_frozen_to_exact_parent_and_target_branch() -> None:
    text = _text()
    assert f"EXPECTED_PARENT_SHA: {EXPECTED_PARENT}" in text
    assert "- feat/uci-7-agi-evidence-protocol-v1" in text
    assert "test \"$PR_BASE_SHA\" = \"$EXPECTED_PARENT_SHA\"" in text


def test_every_piped_pytest_step_is_pipefail_protected() -> None:
    text = _text()
    for block in text.split("\n      - name:")[1:]:
        if "python -m pytest" in block and "| tee" in block:
            assert "set -euo pipefail" in block, block.splitlines()[0]


def test_uci8_reruns_complete_inherited_uci7_proofline_with_cardinality_locks() -> None:
    text = _text()
    required = (
        "test_transition_receipts_pr1.py",
        "test_uci5_atomic_admission.py",
        "test_uci6_collective_memory.py",
        "131 passed",
        "test_uci5_ci_contract.py",
        "3 passed",
        "test_uci7_agi_evidence_protocol.py",
        "test_uci7_agi_evidence_schemas.py",
        "13 passed",
        "test_uci7_ci_contract.py",
        "4 passed",
        "test_uci7_checker_provenance.py",
        "2 passed",
        "test_uci7_baseline_attribution.py",
        "5 passed",
    )
    for needle in required:
        assert needle in text, needle


def test_uci8_local_full_proofline_is_cardinality_locked() -> None:
    text = _text()
    local_tests = (
        "test_uci8_evaluation_campaign.py",
        "test_uci8_evaluation_campaign_schemas.py",
        "test_uci8_repetition_manifest.py",
        "test_uci8_checker_provenance.py",
        "test_uci8_portable_checker_attestation.py",
        "test_uci8_portable_attestation_schemas.py",
        "test_uci8_baseline_selection_integrity.py",
        "test_uci8_published_comparability.py",
        "test_uci8_measurement_resolution.py",
        "test_uci8_measurement_resolution_schema.py",
        "test_uci8_bundle_replay_promotion.py",
        "test_uci8_portable_pair_verification.py",
        "test_uci8_pair_verification_schemas.py",
        "test_uci8_campaign_verification_receipt.py",
        "test_uci8_structural_value_claim.py",
    )
    for needle in local_tests:
        assert needle in text, needle
    assert "59 passed" in text
