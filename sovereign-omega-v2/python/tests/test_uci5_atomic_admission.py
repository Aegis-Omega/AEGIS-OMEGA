"""UCI-5 preregistered atomic-admission boundary.

This file is committed before the UCI-5 production module. The first exact-head
execution must fail specifically because ``harness.sdk.atomic_admission`` does
not exist. That RED witness is required before implementation begins.
"""

from harness.sdk.atomic_admission import (
    ADMISSION_RECORD_KIND,
    LocalSqliteAtomicAdmissionStoreV1,
    uci5_admission_policy_commitment,
)


def test_uci5_nominal_surface_exists() -> None:
    assert ADMISSION_RECORD_KIND == "ADMISSION_RECORD_V1"
    assert LocalSqliteAtomicAdmissionStoreV1.__name__ == "LocalSqliteAtomicAdmissionStoreV1"
    commitment = uci5_admission_policy_commitment()
    assert isinstance(commitment, str)
    assert len(commitment) == 64
