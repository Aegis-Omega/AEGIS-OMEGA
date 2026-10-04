"""UCI-6 regression contract: admitted memory actions bind memory pre-state."""

from harness.sdk.collective_memory import (
    MEMORY_CONTROL_REQUEST_KIND,
    MEMORY_PROJECTION_REQUEST_KIND,
    REVOKE,
    MemoryControlRequestV1,
    MemoryProjectionRequestV1,
    uci6_memory_policy_commitment,
)

HASH = "a" * 64
ZERO = "0" * 64


def test_projection_request_binds_expected_memory_prestate() -> None:
    request = MemoryProjectionRequestV1(
        request_kind=MEMORY_PROJECTION_REQUEST_KIND,
        quarantine_root="1" * 64,
        content_digest="2" * 64,
        memory_class="WORK_RESULT",
        epistemic_tier="T2",
        memory_policy_commitment=uci6_memory_policy_commitment(),
        expected_memory_sequence=0,
        expected_memory_event_root=ZERO,
        nonce="projection-prestate",
    )
    assert request.expected_memory_sequence == 0
    assert request.expected_memory_event_root == ZERO


def test_control_request_binds_expected_memory_prestate() -> None:
    request = MemoryControlRequestV1(
        request_kind=MEMORY_CONTROL_REQUEST_KIND,
        operation=REVOKE,
        target_memory_root=HASH,
        replacement_memory_root=None,
        memory_policy_commitment=uci6_memory_policy_commitment(),
        expected_memory_sequence=7,
        expected_memory_event_root="b" * 64,
        nonce="control-prestate",
    )
    assert request.expected_memory_sequence == 7
    assert request.expected_memory_event_root == "b" * 64
