from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "aedr-multilayer-dag.yml"
ATTEST_ACTION_SHA = "1e69f48acb82d1966a394da916b4c1698aa569d6"
PREDICATE_TYPE = "https://aegisomega.com/attestations/aedr-falsification-surface/v1"


def _workflow() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_iap_workflow_has_minimum_signing_permissions() -> None:
    text = _workflow()
    assert "permissions:\n  contents: read\n  id-token: write\n  attestations: write\n" in text


def test_iap_workflow_pins_current_attest_v4_commit() -> None:
    text = _workflow()
    assert f"uses: actions/attest@{ATTEST_ACTION_SHA}" in text
    assert f"predicate-type: {PREDICATE_TYPE}" in text
    assert "subject-path: ${{ runner.temp }}/aedr-surface.json" in text
    assert "predicate-path: ${{ runner.temp }}/aedr-iap-predicate.json" in text


def test_iap_workflow_generates_predicate_then_verifies_attestation_before_upload() -> None:
    text = _workflow()
    produce = text.index("Produce exact-run AEDR falsification surface")
    predicate = text.index("Build exact-run IAP predicate")
    attest = text.index("Attest exact-run AEDR falsification surface")
    verify = text.index("Verify exact-run AEDR IAP identity")
    upload = text.index("Upload exact-run AEDR falsification surface")

    assert produce < predicate < attest < verify < upload
    assert "python scripts/aedr/iap_verifier.py predicate" in text
    assert "python scripts/aedr/iap_verifier.py verify" in text
    assert '--expected-pr "$AEDR_PR_NUMBER"' in text
    assert '--expected-head-sha "$AEDR_HEAD_SHA"' in text
    assert '--expected-run-id "$AEDR_RUN_ID"' in text
    assert '--receipt-output "$RUNNER_TEMP/aedr-iap-receipt.json"' in text


def test_surface_artifact_shape_remains_single_descriptor_compatible() -> None:
    text = _workflow()
    upload_section = text[text.index("Upload exact-run AEDR falsification surface") :]
    assert "path: ${{ runner.temp }}/aedr-surface.json" in upload_section
    assert "aedr-iap-predicate.json" not in upload_section
    assert "aedr-iap-receipt.json" not in upload_section
