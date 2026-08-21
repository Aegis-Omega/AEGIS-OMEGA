from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]
MODULE_PATH = ROOT / "vertex" / "audit_chain_v2.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("aegis_audit_chain_v2", MODULE_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
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
