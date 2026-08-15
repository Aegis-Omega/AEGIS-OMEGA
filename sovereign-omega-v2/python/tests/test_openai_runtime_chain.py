import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from openai_runtime.chain import ChainOrderError, OmegaChain
from openai_runtime.types import ChainLayer, RuntimeErrorCode


def test_chain_admission_digests_are_deterministic_and_ordered():
    chain = OmegaChain()
    first = chain.admit(
        ChainLayer.INTENT,
        input_artifact={"operator": "intent", "n": 1},
        output_artifact={"normalized": True},
    )
    second = chain.admit(
        ChainLayer.AUTHORITY,
        input_artifact={"normalized": True},
        output_artifact={"admitted": True},
        evidence_digests=["a" * 64],
    )

    other = OmegaChain()
    first_other = other.admit(
        ChainLayer.INTENT,
        input_artifact={"n": 1, "operator": "intent"},
        output_artifact={"normalized": True},
    )

    assert first.input_digest == first_other.input_digest
    assert [r.layer for r in chain.receipts] == [ChainLayer.INTENT, ChainLayer.AUTHORITY]
    assert second.evidence_digests == ["a" * 64]


def test_chain_cannot_skip_a_layer():
    chain = OmegaChain()
    with pytest.raises(ChainOrderError):
        chain.admit(
            ChainLayer.AUTHORITY,
            input_artifact={"x": 1},
            output_artifact={"admitted": True},
        )


def test_denial_is_terminal_and_carries_obstruction_code():
    chain = OmegaChain()
    chain.admit(ChainLayer.INTENT, input_artifact="x", output_artifact="normalized")
    denied = chain.deny(
        ChainLayer.AUTHORITY,
        input_artifact="normalized",
        obstruction_code=RuntimeErrorCode.CAPABILITY_NOT_GRANTED,
    )

    assert denied.admitted is False
    assert denied.obstruction_code == RuntimeErrorCode.CAPABILITY_NOT_GRANTED.value
    with pytest.raises(ChainOrderError):
        chain.admit(
            ChainLayer.MODEL_RUNTIME,
            input_artifact="denied",
            output_artifact="must-not-run",
        )
