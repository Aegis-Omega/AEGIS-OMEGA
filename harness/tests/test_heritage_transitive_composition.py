from __future__ import annotations

import inspect
from dataclasses import fields

import pytest

import harness.sdk.meaning_heritage as mh


TC_CODES = (
    "TRANSIENT_ADDITION_LEAK",
    "UNDECLARED_COMPOSITE_LOSS",
    "UNDECLARED_COMPOSITE_ADDITION",
    "COMPOSITION_PRESERVATION_UNPROVEN",
    "COMPOSITION_MIXED_ANCESTRY",
    "COMPOSITION_PARTITION_MISMATCH",
)


@pytest.mark.parametrize("code", TC_CODES)
def test_tc_01_through_tc_06_are_preregistered_wire_codes(code: str) -> None:
    """RED contract: every ratified transitive-composition falsifier is wire-visible."""
    assert code in {item.value for item in mh.VerificationErrorCode}


def test_transitive_composition_trust_ports_and_receipts_exist() -> None:
    """RED contract: composition must resolve trusted state, never accept caller-authored H13."""
    required = (
        "TrustedSemanticLineageEnvelopeStore",
        "TrustedPreservationCompositionProofStore",
        "PreservationCompositionProofReceiptV1",
        "HeritageCompositionReceiptV1",
    )
    missing = tuple(name for name in required if not hasattr(mh, name))
    assert not missing, f"TRANSITIVE_COMPOSITION_RUNTIME_NOT_IMPLEMENTED:{missing}"


def test_compose_surface_removes_caller_authored_composed_state() -> None:
    """Caller may provide predecessor receipts and trust ports, not P13/O13/A13/H13."""
    params = inspect.signature(mh.HeritageVerifierV13.compose).parameters
    forbidden = {"composed_envelope", "source_claimset", "derived_claimset"}
    assert not (forbidden & set(params)), "CALLER_AUTHORED_COMPOSED_STATE_STILL_ACCEPTED"


def test_composition_receipt_wire_authority_is_none() -> None:
    receipt_type = getattr(mh, "HeritageCompositionReceiptV1", None)
    assert receipt_type is not None, "HERITAGE_COMPOSITION_RECEIPT_NOT_IMPLEMENTED"
    field_map = {item.name: item for item in fields(receipt_type)}
    assert "authority_class" in field_map
    assert field_map["authority_class"].default == "NONE"


def test_ratified_partition_meta_assertions_are_named_in_contract() -> None:
    """The GREEN runtime must enforce C1/dom+O13, C3/ran+A13 and empty mixed ancestry."""
    source = inspect.getsource(mh.HeritageVerifierV13.compose)
    required_markers = (
        "COMPOSITION_PARTITION_MISMATCH",
        "COMPOSITION_MIXED_ANCESTRY",
        "TRANSIENT_ADDITION_LEAK",
    )
    assert all(marker in source for marker in required_markers)
