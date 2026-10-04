from __future__ import annotations

import asyncio
import importlib.util
import json
import os
import sys
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "vertex" / "audit_chain_v2.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aegis_audit_chain_v2", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def _entries(mod, count: int):
    entries = []
    prev = mod.GENESIS_HASH
    for seq in range(count):
        observation = {"seq": seq, "signal": f"event-{seq}"}
        entry_hash = mod.compute_entry_hash(prev, seq, observation)
        entry = {
            "sequence": seq,
            "previous_entry_hash": prev,
            "entry_hash": entry_hash,
            "observation": observation,
            "tier": "T1",
        }
        entries.append(entry)
        prev = entry_hash
    return entries


def _redis_url() -> str:
    return os.environ.get("AEGIS_TEST_REDIS_URL", "redis://127.0.0.1:6379/15")


async def _cleanup(*states) -> None:
    seen = set()
    for state in states:
        if state.redis is not None and state.chain_key not in seen:
            await state.redis.delete(
                state.chain_key,
                state.seq_key,
                state.tail_key,
                state.anchor_key,
            )
            seen.add(state.chain_key)
    for state in states:
        if state.redis is not None:
            await state.redis.aclose()


def test_full_snapshot_certifies_from_genesis():
    mod = _load_module()
    entries = _entries(mod, 5)
    cert = mod.certify_snapshot(entries, mod.ChainAnchor(mod.GENESIS_HASH, 0))
    assert cert["is_valid"] is True
    assert cert["next_sequence"] == 5
    assert cert["terminal_hash"] == entries[-1]["entry_hash"]


def test_tampered_observation_fails_closed():
    mod = _load_module()
    entries = _entries(mod, 3)
    entries[1]["observation"] = {"seq": 1, "signal": "tampered"}
    cert = mod.certify_snapshot(entries, mod.ChainAnchor(mod.GENESIS_HASH, 0))
    assert cert["is_valid"] is False
    assert cert["tampered_at_sequence"] == 1
    assert cert["reason"] == "ENTRY_HASH_MISMATCH"


def test_trimmed_suffix_certifies_against_explicit_anchor():
    mod = _load_module()
    entries = _entries(mod, 6)
    retained = entries[3:]
    anchor = mod.ChainAnchor(entries[2]["entry_hash"], 3)
    cert = mod.certify_snapshot(retained, anchor)
    assert cert["is_valid"] is True
    assert cert["first_sequence"] == 3
    assert cert["next_sequence"] == 6
    assert cert["terminal_hash"] == entries[-1]["entry_hash"]


def test_trimmed_suffix_rejects_wrong_anchor():
    mod = _load_module()
    entries = _entries(mod, 6)
    retained = entries[3:]
    cert = mod.certify_snapshot(retained, mod.ChainAnchor(mod.GENESIS_HASH, 3))
    assert cert["is_valid"] is False
    assert cert["reason"] == "PREVIOUS_HASH_MISMATCH"


def test_sequence_gap_is_not_reinterpreted_as_valid_chain():
    mod = _load_module()
    entries = _entries(mod, 4)
    entries[2]["sequence"] = 9
    cert = mod.certify_snapshot(entries, mod.ChainAnchor(mod.GENESIS_HASH, 0))
    assert cert["is_valid"] is False
    assert cert["reason"] == "SEQUENCE_DISCONTINUITY"


def test_absolute_sequence_is_bound_into_hash():
    mod = _load_module()
    observation = {"signal": "same"}
    h1 = mod.compute_entry_hash(mod.GENESIS_HASH, 1, observation)
    h2 = mod.compute_entry_hash(mod.GENESIS_HASH, 2, observation)
    assert h1 != h2


def test_redis_concurrent_append_is_linearized():
    mod = _load_module()

    async def scenario():
        chain_key = f"aegis:test:concurrent:{uuid.uuid4().hex}"
        a = mod.ChainStateV2(_redis_url(), chain_key=chain_key, max_entries=500)
        b = mod.ChainStateV2(_redis_url(), chain_key=chain_key, max_entries=500)
        await a.init()
        await b.init()
        try:
            calls = []
            for i in range(80):
                state = a if i % 2 == 0 else b
                calls.append(state.append({"logical_input": i}, tier="T1"))
            await asyncio.gather(*calls)

            cert = await a.certify()
            assert cert["is_valid"] is True
            assert cert["entry_count"] == 80
            assert cert["first_sequence"] == 0
            assert cert["next_sequence"] == 80

            entries = await a.full_chain(limit=100)
            assert [entry["sequence"] for entry in entries] == list(range(80))
            assert len({entry["entry_hash"] for entry in entries}) == 80
        finally:
            await _cleanup(a, b)

    asyncio.run(scenario())


def test_redis_trim_advances_explicit_anchor_and_preserves_certification():
    mod = _load_module()

    async def scenario():
        chain_key = f"aegis:test:trim:{uuid.uuid4().hex}"
        state = mod.ChainStateV2(_redis_url(), chain_key=chain_key, max_entries=5)
        await state.init()
        try:
            for i in range(12):
                await state.append({"logical_input": i}, tier="T2")

            cert = await state.certify()
            assert cert["is_valid"] is True
            assert cert["entry_count"] == 5
            assert cert["first_sequence"] == 7
            assert cert["next_sequence"] == 12

            assert await state.get_entry(6) is None
            first = await state.get_entry(7)
            last = await state.get_entry(11)
            assert first is not None and first["sequence"] == 7
            assert last is not None and last["sequence"] == 11
        finally:
            await _cleanup(state)

    asyncio.run(scenario())


def test_redis_persistent_tamper_is_detected():
    mod = _load_module()

    async def scenario():
        chain_key = f"aegis:test:tamper:{uuid.uuid4().hex}"
        state = mod.ChainStateV2(_redis_url(), chain_key=chain_key, max_entries=20)
        await state.init()
        try:
            for i in range(3):
                await state.append({"logical_input": i}, tier="T1")

            raw = await state.redis.lindex(chain_key, 1)
            assert raw is not None
            entry = json.loads(raw)
            entry["observation"] = {"logical_input": "tampered"}
            await state.redis.lset(chain_key, 1, json.dumps(entry, separators=(",", ":")))

            cert = await state.certify()
            assert cert["is_valid"] is False
            assert cert["reason"] == "ENTRY_HASH_MISMATCH"
        finally:
            await _cleanup(state)

    asyncio.run(scenario())
