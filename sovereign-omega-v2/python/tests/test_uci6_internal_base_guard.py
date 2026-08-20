"""UCI-6 security regression: the prestate-less internal base is not a usable mutation surface."""

import pytest

from harness.sdk import _collective_memory_base as internal
from harness.sdk.collective_memory import (
    LocalSqliteCollectiveMemoryStoreV1,
    uci6_memory_policy_commitment,
)


def test_internal_base_store_direct_use_is_fail_closed(tmp_path) -> None:
    with pytest.raises(internal.CollectiveMemoryError) as ctx:
        internal.LocalSqliteCollectiveMemoryStoreV1(
            db_path=tmp_path / "forbidden-internal.sqlite3",
            memory_policy_commitment=internal.uci6_memory_policy_commitment(),
        )
    assert ctx.value.code == "MEMORY_INTERNAL_BASE_DIRECT_USE_FORBIDDEN"


def test_public_prestate_bound_store_remains_constructible(tmp_path) -> None:
    store = LocalSqliteCollectiveMemoryStoreV1(
        db_path=tmp_path / "public.sqlite3",
        memory_policy_commitment=uci6_memory_policy_commitment(),
    )
    state = store.read_memory_state()
    assert state.sequence == 0
    assert state.memory_policy_commitment == uci6_memory_policy_commitment()
