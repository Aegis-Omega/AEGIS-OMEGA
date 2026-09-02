from __future__ import annotations

from pathlib import Path

import pytest

from scripts.avd.airgap_protocol import AirgapTrialContract, AirgapViolation
from scripts.avd.oracle_manifest import MUTATION_SPECS, MutationClass
from scripts.avd.submission_policy import SubmissionPolicyError, validate_submission_surface


def test_oracle_manifest_freezes_all_sixteen_mutants() -> None:
    ids = [m.mutation_id for m in MUTATION_SPECS]
    assert ids == [f"MUT_{i:02d}" for i in range(16)]
    assert MUTATION_SPECS[0].expected_decision == "ACCEPT"
    assert MUTATION_SPECS[-1].expected_decision == "ACCEPT"
    assert all(m.expected_decision == "REJECT" for m in MUTATION_SPECS[1:15])

    by_class = {cls: [m.mutation_id for m in MUTATION_SPECS if m.mutation_class == cls] for cls in MutationClass}
    assert by_class[MutationClass.CANDIDATE_SEMANTIC] == [
        "MUT_00", "MUT_01", "MUT_02", "MUT_03", "MUT_04", "MUT_05", "MUT_06", "MUT_15"
    ]
    assert by_class[MutationClass.PROOF_INTEGRITY] == ["MUT_07", "MUT_08", "MUT_09", "MUT_10"]
    assert by_class[MutationClass.PROVENANCE_VERIFIER] == ["MUT_11", "MUT_12", "MUT_13", "MUT_14"]


def test_submission_policy_allows_only_target_production_file(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    target = Path("sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v")
    spec = Path("sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v")
    for root in (baseline, candidate):
        (root / target.parent).mkdir(parents=True)
        (root / spec.parent).mkdir(parents=True)
        (root / spec).write_text("frozen spec", encoding="utf-8")
    # RED baseline intentionally lacks the production target.
    (candidate / target).write_text("candidate", encoding="utf-8")
    changed = validate_submission_surface(baseline, candidate, allowed_path=target)
    assert changed == (target.as_posix(),)

    (candidate / "sovereign-omega-v2/formal/theories/Weil/AnalyticDefinitions.v").write_text("shadow", encoding="utf-8")
    with pytest.raises(SubmissionPolicyError, match="UNAUTHORIZED_PATH_CHANGE"):
        validate_submission_surface(baseline, candidate, allowed_path=target)


def test_submission_policy_rejects_frozen_spec_mutation(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline"
    candidate = tmp_path / "candidate"
    target = Path("sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v")
    spec = Path("sovereign-omega-v2/formal/tests/Weil/CornO0MorphismBridgeSpec.v")
    for root in (baseline, candidate):
        (root / target.parent).mkdir(parents=True)
        (root / spec.parent).mkdir(parents=True)
        (root / spec).write_text("frozen", encoding="utf-8")
    (candidate / target).write_text("candidate", encoding="utf-8")
    (candidate / spec).write_text("mutated", encoding="utf-8")
    with pytest.raises(SubmissionPolicyError, match="UNAUTHORIZED_PATH_CHANGE"):
        validate_submission_surface(baseline, candidate, allowed_path=target)


def test_airgap_contract_requires_clean_context_and_network_none(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    contract = AirgapTrialContract(
        workspace_root=workspace,
        target_relative_path="sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v",
        fresh_clean_room_context=True,
        external_repo_tools_disabled=True,
        candidate_network_mode="NONE",
    )
    attestation = contract.preflight(probe_network=False)
    assert attestation["workspace_git_metadata_absent"] is True
    assert attestation["future_solution_absent_at_start"] is True
    assert attestation["fresh_clean_room_context"] is True
    assert attestation["external_repo_tools_disabled"] is True
    assert attestation["candidate_network_mode"] == "NONE"

    contaminated = AirgapTrialContract(
        workspace_root=workspace,
        target_relative_path="sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v",
        fresh_clean_room_context=False,
        external_repo_tools_disabled=True,
        candidate_network_mode="NONE",
    )
    with pytest.raises(AirgapViolation, match="PARTICIPANT_CONTEXT_CONTAMINATED"):
        contaminated.preflight(probe_network=False)


def test_airgap_contract_rejects_future_solution_in_baseline(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    target = workspace / "sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v"
    target.parent.mkdir(parents=True)
    target.write_text("future solution", encoding="utf-8")
    contract = AirgapTrialContract(
        workspace_root=workspace,
        target_relative_path="sovereign-omega-v2/formal/theories/Weil/CornO0MorphismBridge.v",
        fresh_clean_room_context=True,
        external_repo_tools_disabled=True,
        candidate_network_mode="NONE",
    )
    with pytest.raises(AirgapViolation, match="FUTURE_SOLUTION_PRESENT_IN_BASELINE"):
        contract.preflight(probe_network=False)
