import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pytest

from openai_runtime.receipts import ReceiptConstructionError, build_mutation_receipt, digest_receipt
from openai_runtime.types import ActionClass, OmegaRunContext, OmegaRunRequest, RuntimeErrorCode, ToolEvidence


def _context():
    return OmegaRunContext(
        execution_id="exec-123",
        caller_email="operator@example.invalid",
        caller_tier="sovereign",
        model="gpt-5.6-sol",
        request_digest="1" * 64,
    )


def _request():
    return OmegaRunRequest(
        input="apply approved patch",
        allowed_capabilities=["implementation-proposal"],
        allowed_tools=["apply-patch"],
        action_class=ActionClass.D2,
        approvals=["approve:apply-patch"],
    )


def _complete_evidence():
    return ToolEvidence(
        tool="apply-patch",
        success=True,
        result_digest="2" * 64,
        evidence_digests=["3" * 64],
        mutates=True,
        target_digest="4" * 64,
        pre_state_digest="5" * 64,
        post_state_digest="6" * 64,
    )


def test_incomplete_mutation_evidence_cannot_produce_receipt():
    evidence = _complete_evidence().model_copy(update={"post_state_digest": None})
    with pytest.raises(ReceiptConstructionError) as exc:
        build_mutation_receipt(
            context=_context(),
            request=_request(),
            evidence=evidence,
            workspace_binding="7" * 64,
            policy_decision_root="8" * 64,
            authority_score="1.000000",
            authority_domain="repository",
            requested_action_digest="9" * 64,
            parent_receipt="0" * 64,
            sequence=1,
        )
    assert exc.value.code == RuntimeErrorCode.RECEIPT_INCOMPLETE


def test_read_only_evidence_cannot_be_misrepresented_as_mutation_receipt():
    evidence = ToolEvidence(
        tool="read-evidence",
        success=True,
        result_digest="2" * 64,
        evidence_digests=["3" * 64],
        mutates=False,
    )
    with pytest.raises(ReceiptConstructionError):
        build_mutation_receipt(
            context=_context(),
            request=_request(),
            evidence=evidence,
            workspace_binding="7" * 64,
            policy_decision_root="8" * 64,
            authority_score="1.000000",
            authority_domain="repository",
            requested_action_digest="9" * 64,
            parent_receipt="0" * 64,
            sequence=1,
        )


def test_complete_mutation_receipt_matches_schema_shape_and_is_digestable():
    receipt = build_mutation_receipt(
        context=_context(),
        request=_request(),
        evidence=_complete_evidence(),
        workspace_binding="7" * 64,
        policy_decision_root="8" * 64,
        authority_score="1.000000",
        authority_domain="repository",
        requested_action_digest="9" * 64,
        parent_receipt="0" * 64,
        sequence=1,
    )
    assert receipt["receipt_version"] == "1.0.0"
    assert receipt["action_class"] == "D2"
    assert receipt["tool"] == "apply-patch"
    assert receipt["outcome"] == "SUCCEEDED"
    assert receipt["denial_code"] == "NONE"
    assert len(digest_receipt(receipt)) == 64
