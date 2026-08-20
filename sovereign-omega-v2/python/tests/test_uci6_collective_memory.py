"""UCI-6 preregistered collective-memory boundary.

This test is committed before ``harness.sdk.collective_memory`` exists. The
first exact-head execution must fail specifically on that missing module before
any production memory implementation is introduced.
"""

from harness.sdk.collective_memory import (
    CANONICAL_MEMORY_RECORD_KIND,
    QUARANTINED_MEMORY_RECORD_KIND,
    LocalSqliteCollectiveMemoryStoreV1,
    uci6_memory_policy_commitment,
)


def test_uci6_nominal_surface_exists() -> None:
    assert QUARANTINED_MEMORY_RECORD_KIND == "QUARANTINED_EVIDENCE_MEMORY_RECORD_V1"
    assert CANONICAL_MEMORY_RECORD_KIND == "CANONICAL_MEMORY_RECORD_V1"
    assert LocalSqliteCollectiveMemoryStoreV1.__name__ == "LocalSqliteCollectiveMemoryStoreV1"
    commitment = uci6_memory_policy_commitment()
    assert isinstance(commitment, str)
    assert len(commitment) == 64
