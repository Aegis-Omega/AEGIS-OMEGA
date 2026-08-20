"""UCI-4 integration boundary over the frozen effect-verification proofline.

This test is intentionally introduced before the UCI-4 implementation. On the
#275 parent it must fail during import because the effect-chain SDK modules are
not present. That RED witness prevents a green-by-construction transplant.
"""

from harness.sdk.transition_receipts import (
    DECISION_RECEIPT_KIND,
    EFFECT_RECEIPT_KIND,
    EXECUTION_RECEIPT_KIND,
    DEFER,
    WAITING,
    decision_execution_allowed,
    decision_route,
)
from harness.sdk.effect_adapters import EffectWitness
from harness.sdk.effect_verifier import EffectVerificationResult
from harness.sdk.complete_verifier import CompleteVerificationResult


def test_uci4_nominal_effect_chain_surface_exists() -> None:
    assert DECISION_RECEIPT_KIND == "DECISION_RECEIPT_V1"
    assert EXECUTION_RECEIPT_KIND == "EXECUTION_RECEIPT_V1"
    assert EFFECT_RECEIPT_KIND == "EFFECT_RECEIPT_V1"
    assert decision_route(DEFER) == WAITING
    assert decision_execution_allowed(DEFER) is False
    assert EffectWitness.__name__ == "EffectWitness"
    assert EffectVerificationResult.__name__ == "EffectVerificationResult"
    assert CompleteVerificationResult.__name__ == "CompleteVerificationResult"
