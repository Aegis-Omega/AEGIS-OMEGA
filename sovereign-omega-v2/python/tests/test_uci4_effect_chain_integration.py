"""UCI-4 integration and security boundary over the frozen effect-verification proofline.

The original nominal-surface test was introduced before the UCI-4 implementation.
The additional falsifiers below are preregistered before the security hardening
patch: fabricated EffectWitness values must not verify, filesystem observation
must not be redirectable between path validation and open, observation size must
be bounded, and the native CI contract must stay bound to the frozen parent.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from unittest.mock import patch

import pytest

from harness.sdk.sovereign_execution import SCHEMA_VERSION
from harness.sdk.transition_receipts import (
    DECISION_RECEIPT_KIND,
    EFFECT_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    EXECUTION_SUCCEEDED,
    DEFER,
    WAITING,
    ExecutionReceipt,
    TransitionIdentity,
    admission_policy_commitment,
    decision_execution_allowed,
    decision_route,
    verifier_policy_commitment,
)
from harness.sdk.effect_adapters import (
    EFFECT_WITNESS_KIND,
    EffectAdapterError,
    EffectWitness,
    FilesystemEffectAdapter,
    is_adapter_bound_effect_evidence,
)
from harness.sdk.effect_verifier import FALSE, TRUE, EffectVerificationResult, EffectVerifier
from harness.sdk.complete_verifier import CompleteVerificationResult


HASHES = [f"{index:064x}" for index in range(1, 32)]
COMMIT = "c" * 40
FROZEN_PARENT = "ebec2f9c8fa00f54605d859df61512108ff3b71d"
FROZEN_PARENT_BRANCH = "feat/uci-1-collective-work-contract-v1"
REPO_ROOT = Path(__file__).resolve().parents[3]
WORKFLOW = REPO_ROOT / ".github/workflows/uci-4-effect-chain-contract.yml"


def _transition(*, pre_state_commitment: str) -> TransitionIdentity:
    return TransitionIdentity(
        schema_version=SCHEMA_VERSION,
        source_commit=COMMIT,
        pre_state_commitment=pre_state_commitment,
        identity_root=HASHES[1],
        delegation_commitment=HASHES[2],
        capability_commitment=HASHES[3],
        action_digest=HASHES[4],
        deterministic_nonce="nonce-uci4-security-review",
        fence_commitment=HASHES[5],
        verifier_policy_commitment=verifier_policy_commitment(),
        admission_policy_commitment=admission_policy_commitment(),
    )


def _execution(transition: TransitionIdentity) -> ExecutionReceipt:
    return ExecutionReceipt(
        receipt_kind=EXECUTION_RECEIPT_KIND,
        transition_id=transition.root,
        execution_instance_id="exec-uci4-security-review",
        outcome=EXECUTION_SUCCEEDED,
        result_digest=HASHES[6],
    )


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_uci4_nominal_effect_chain_surface_exists() -> None:
    assert DECISION_RECEIPT_KIND == "DECISION_RECEIPT_V1"
    assert EXECUTION_RECEIPT_KIND == "EXECUTION_RECEIPT_V1"
    assert EFFECT_RECEIPT_KIND == "EFFECT_RECEIPT_V1"
    assert decision_route(DEFER) == WAITING
    assert decision_execution_allowed(DEFER) is False
    assert EffectWitness.__name__ == "EffectWitness"
    assert EffectVerificationResult.__name__ == "EffectVerificationResult"
    assert CompleteVerificationResult.__name__ == "CompleteVerificationResult"


def test_fabricated_effect_witness_is_not_accepted_as_adapter_observation() -> None:
    transition = _transition(pre_state_commitment=HASHES[7])
    execution = _execution(transition)
    fabricated = EffectWitness(
        witness_kind=EFFECT_WITNESS_KIND,
        transition_id=transition.root,
        execution_instance_id=execution.execution_instance_id,
        target_identity="state.txt",
        observed_pre_state_commitment=transition.pre_state_commitment,
        observed_post_state_commitment=HASHES[8],
        effect_changed=True,
        pre_observation_provenance=HASHES[9],
        post_observation_provenance=HASHES[10],
        adapter_identity=FilesystemEffectAdapter.identity,
        adapter_version=FilesystemEffectAdapter.version,
    )

    assert is_adapter_bound_effect_evidence(witness=fabricated) is False
    result = EffectVerifier().verify_effect(
        transition=transition,
        execution_receipt=execution,
        witness=fabricated,
    )
    assert result.status == FALSE
    assert result.status != TRUE


def test_filesystem_observation_cannot_be_redirected_after_target_validation(tmp_path: Path) -> None:
    allowed = tmp_path / "allowed"
    allowed.mkdir()
    target = allowed / "state.txt"
    target.write_bytes(b"inside")
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"outside")

    adapter = FilesystemEffectAdapter(allowed_root=allowed)
    original_open = Path.open
    resolved_target = target.resolve()

    def redirected_open(self: Path, *args, **kwargs):
        if self == resolved_target:
            return original_open(outside, *args, **kwargs)
        return original_open(self, *args, **kwargs)

    with patch.object(Path, "open", new=redirected_open):
        observation = adapter._observe_state(target)

    assert observation.target_identity == "state.txt"
    assert observation.content_sha256 == hashlib.sha256(b"inside").hexdigest()


def test_filesystem_observation_enforces_explicit_size_bound(tmp_path: Path) -> None:
    target = tmp_path / "oversized.bin"
    target.write_bytes(b"123456789")
    adapter = FilesystemEffectAdapter(allowed_root=tmp_path)
    adapter.max_observation_bytes = 8

    with pytest.raises(EffectAdapterError, match="EFFECT_TARGET_TOO_LARGE"):
        adapter._observe_state(target)


def test_uci4_ci_binds_literal_frozen_parent_and_pr_base() -> None:
    text = _workflow_text()
    assert f"EXPECTED_PARENT_SHA: {FROZEN_PARENT}" in text
    assert "PR_BASE_SHA: ${{ github.event.pull_request.base.sha || '' }}" in text
    assert 'test "$PR_BASE_SHA" = "$EXPECTED_PARENT_SHA"' in text


def test_uci4_ci_runs_only_for_its_frozen_parent_pr() -> None:
    text = _workflow_text()
    assert "pull_request:\n    branches:\n      - " + FROZEN_PARENT_BRANCH in text


def test_uci4_ci_locks_expected_hardened_proofline_cardinality() -> None:
    text = _workflow_text()
    assert "grep -Eq '85 passed'" in text
    assert 'echo "UCI4_FULL_PROOFLINE_85=PASS"' in text
