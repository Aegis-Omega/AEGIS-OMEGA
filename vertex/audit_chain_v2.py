"""Redis-backed concurrent audit chain for the AEGIS platform.

V2 removes process-local sequence authority. Appends use a Redis compare-and-set
Lua transaction over the absolute sequence and tail hash, so concurrent Cloud Run
instances cannot independently claim the same chain position. Trimming advances
an explicit anchor, preserving certification of the retained suffix.
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any

import redis.asyncio as aioredis

GENESIS_HASH = "0" * 64
CHAIN_VERSION = "AEGIS_AUDIT_CHAIN_V2"
MAX_APPEND_RETRIES = 128

_APPEND_CAS_LUA = r"""
local list_key = KEYS[1]
local seq_key = KEYS[2]
local tail_key = KEYS[3]
local anchor_key = KEYS[4]

local expected_seq = tonumber(ARGV[1])
local expected_tail = ARGV[2]
local new_entry = ARGV[3]
local new_tail = ARGV[4]
local max_entries = tonumber(ARGV[5])

local current_seq_raw = redis.call('GET', seq_key)
local current_tail = redis.call('GET', tail_key)
if not current_seq_raw or not current_tail then
  return -2
end

local current_seq = tonumber(current_seq_raw)
if current_seq ~= expected_seq or current_tail ~= expected_tail then
  return 0
end

redis.call('RPUSH', list_key, new_entry)
redis.call('SET', seq_key, tostring(expected_seq + 1))
redis.call('SET', tail_key, new_tail)

local len = redis.call('LLEN', list_key)
if len > max_entries then
  local remove_count = len - max_entries
  local removed_raw = redis.call('LINDEX', list_key, remove_count - 1)
  local retained_raw = redis.call('LINDEX', list_key, remove_count)
  if not removed_raw or not retained_raw then
    return -3
  end
  local removed = cjson.decode(removed_raw)
  local retained = cjson.decode(retained_raw)
  local anchor = {
    schema_version = '2.0.0',
    previous_entry_hash = removed['entry_hash'],
    next_sequence = retained['sequence']
  }
  redis.call('SET', anchor_key, cjson.encode(anchor))
  redis.call('LTRIM', list_key, remove_count, -1)
end

return 1
"""

_SNAPSHOT_LUA = r"""
local anchor = redis.call('GET', KEYS[1])
local seq = redis.call('GET', KEYS[2])
local tail = redis.call('GET', KEYS[3])
local entries = redis.call('LRANGE', KEYS[4], 0, -1)
return {anchor, seq, tail, entries}
"""

_GET_ENTRY_LUA = r"""
local anchor_raw = redis.call('GET', KEYS[1])
if not anchor_raw then
  return nil
end
local anchor = cjson.decode(anchor_raw)
local index = tonumber(ARGV[1]) - tonumber(anchor['next_sequence'])
if index < 0 then
  return nil
end
return redis.call('LINDEX', KEYS[2], index)
"""


def _canonical(obj: Any) -> bytes:
    return json.dumps(
        obj,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def compute_entry_hash(prev_hash: str, seq: int, observation: dict[str, Any]) -> str:
    payload = prev_hash.encode("ascii") + seq.to_bytes(8, "big") + _canonical(observation)
    return hashlib.sha256(payload).hexdigest()


@dataclass(frozen=True)
class ChainAnchor:
    previous_entry_hash: str
    next_sequence: int

    def to_json(self) -> str:
        return json.dumps(
            {
                "schema_version": "2.0.0",
                "previous_entry_hash": self.previous_entry_hash,
                "next_sequence": self.next_sequence,
            },
            sort_keys=True,
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, raw: str | None) -> "ChainAnchor":
        if raw is None:
            return cls(GENESIS_HASH, 0)
        value = json.loads(raw)
        previous = value.get("previous_entry_hash")
        sequence = value.get("next_sequence")
        if not isinstance(previous, str) or len(previous) != 64:
            raise RuntimeError("AUDIT_ANCHOR_INVALID_HASH")
        if not isinstance(sequence, int) or sequence < 0:
            raise RuntimeError("AUDIT_ANCHOR_INVALID_SEQUENCE")
        return cls(previous, sequence)


def certify_snapshot(entries: list[dict[str, Any]], anchor: ChainAnchor) -> dict[str, Any]:
    prev = anchor.previous_entry_hash
    expected_seq = anchor.next_sequence
    for entry in entries:
        seq = entry.get("sequence")
        observation = entry.get("observation")
        if seq != expected_seq:
            return {
                "is_valid": False,
                "entry_count": len(entries),
                "first_sequence": anchor.next_sequence,
                "tampered_at_sequence": seq,
                "reason": "SEQUENCE_DISCONTINUITY",
            }
        if not isinstance(observation, dict):
            return {
                "is_valid": False,
                "entry_count": len(entries),
                "first_sequence": anchor.next_sequence,
                "tampered_at_sequence": seq,
                "reason": "OBSERVATION_INVALID",
            }
        if entry.get("previous_entry_hash") != prev:
            return {
                "is_valid": False,
                "entry_count": len(entries),
                "first_sequence": anchor.next_sequence,
                "tampered_at_sequence": seq,
                "reason": "PREVIOUS_HASH_MISMATCH",
            }
        expected_hash = compute_entry_hash(prev, seq, observation)
        if entry.get("entry_hash") != expected_hash:
            return {
                "is_valid": False,
                "entry_count": len(entries),
                "first_sequence": anchor.next_sequence,
                "tampered_at_sequence": seq,
                "reason": "ENTRY_HASH_MISMATCH",
            }
        prev = expected_hash
        expected_seq += 1

    return {
        "is_valid": True,
        "entry_count": len(entries),
        "first_sequence": anchor.next_sequence,
        "next_sequence": expected_seq,
        "terminal_hash": prev,
        "anchor_previous_hash": anchor.previous_entry_hash,
        "chain_version": CHAIN_VERSION,
    }


class ChainStateV2:
    def __init__(self, redis_url: str, *, chain_key: str = "aegis:chain", max_entries: int = 50_000):
        self.redis_url = redis_url
        self.chain_key = chain_key
        self.seq_key = f"{chain_key}:next_sequence:v2"
        self.tail_key = f"{chain_key}:tail_hash:v2"
        self.anchor_key = f"{chain_key}:anchor:v2"
        self.max_entries = max_entries
        self.redis: aioredis.Redis | None = None
        # Serialize callers inside one process to avoid a local thundering herd.
        # Cross-process authority still lives exclusively in Redis CAS.
        self._append_lock = asyncio.Lock()
        # Compatibility field expected by serve.py. It is observational only;
        # Redis metadata remains the authority.
        self.anthropic = None

    async def init(self) -> None:
        self.redis = aioredis.from_url(self.redis_url, decode_responses=True)
        await self.redis.ping()
        await self._initialize_or_validate_metadata()

        # serve.py expects state.anthropic. Import here to avoid making the chain
        # module itself depend on provider configuration.
        import os
        import anthropic

        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        self.anthropic = anthropic.AsyncAnthropic(api_key=api_key) if api_key else None

    async def _initialize_or_validate_metadata(self) -> None:
        assert self.redis is not None
        seq_raw, tail_raw, anchor_raw, length = await asyncio.gather(
            self.redis.get(self.seq_key),
            self.redis.get(self.tail_key),
            self.redis.get(self.anchor_key),
            self.redis.llen(self.chain_key),
        )

        if seq_raw is None and tail_raw is None:
            if length == 0:
                anchor = ChainAnchor(GENESIS_HASH, 0)
                async with self.redis.pipeline(transaction=True) as pipe:
                    pipe.set(self.seq_key, "0", nx=True)
                    pipe.set(self.tail_key, GENESIS_HASH, nx=True)
                    pipe.set(self.anchor_key, anchor.to_json(), nx=True)
                    await pipe.execute()
                return

            raw_entries = await self.redis.lrange(self.chain_key, 0, -1)
            entries = [json.loads(raw) for raw in raw_entries]
            first_seq = entries[0].get("sequence") if entries else None
            if first_seq != 0:
                raise RuntimeError(
                    "AUDIT_CHAIN_LEGACY_TRIMMED_WITHOUT_ANCHOR: cannot prove retained-prefix provenance"
                )
            anchor = ChainAnchor(GENESIS_HASH, 0)
            cert = certify_snapshot(entries, anchor)
            if not cert.get("is_valid"):
                raise RuntimeError(f"AUDIT_CHAIN_LEGACY_INVALID:{cert.get('reason')}")
            next_seq = int(cert["next_sequence"])
            tail = str(cert["terminal_hash"])
            async with self.redis.pipeline(transaction=True) as pipe:
                pipe.set(self.seq_key, str(next_seq), nx=True)
                pipe.set(self.tail_key, tail, nx=True)
                pipe.set(self.anchor_key, anchor.to_json(), nx=True)
                await pipe.execute()
            return

        if seq_raw is None or tail_raw is None or anchor_raw is None:
            raise RuntimeError("AUDIT_CHAIN_METADATA_PARTIAL")

        try:
            next_seq = int(seq_raw)
        except ValueError as exc:
            raise RuntimeError("AUDIT_CHAIN_SEQUENCE_METADATA_INVALID") from exc
        anchor = ChainAnchor.from_json(anchor_raw)
        raw_entries = await self.redis.lrange(self.chain_key, 0, -1)
        entries = [json.loads(raw) for raw in raw_entries]
        cert = certify_snapshot(entries, anchor)
        if not cert.get("is_valid"):
            raise RuntimeError(f"AUDIT_CHAIN_INVALID:{cert.get('reason')}")
        if int(cert["next_sequence"]) != next_seq:
            raise RuntimeError("AUDIT_CHAIN_SEQUENCE_METADATA_MISMATCH")
        if str(cert["terminal_hash"]) != tail_raw:
            raise RuntimeError("AUDIT_CHAIN_TAIL_METADATA_MISMATCH")

    async def append(self, observation: dict[str, Any], tier: str = "T1") -> dict[str, Any]:
        assert self.redis is not None
        async with self._append_lock:
            for attempt in range(MAX_APPEND_RETRIES):
                seq_raw, prev_hash = await asyncio.gather(
                    self.redis.get(self.seq_key),
                    self.redis.get(self.tail_key),
                )
                if seq_raw is None or prev_hash is None:
                    raise RuntimeError("AUDIT_CHAIN_METADATA_MISSING")
                seq = int(seq_raw)
                entry_hash = compute_entry_hash(prev_hash, seq, observation)
                entry = {
                    "sequence": seq,
                    "previous_entry_hash": prev_hash,
                    "entry_hash": entry_hash,
                    "observation": observation,
                    "tier": tier,
                    "timestamp_ms": int(time.time() * 1000),
                    "chain_version": CHAIN_VERSION,
                }
                raw = json.dumps(entry, separators=(",", ":"), ensure_ascii=False, allow_nan=False)
                result = await self.redis.eval(
                    _APPEND_CAS_LUA,
                    4,
                    self.chain_key,
                    self.seq_key,
                    self.tail_key,
                    self.anchor_key,
                    str(seq),
                    prev_hash,
                    raw,
                    entry_hash,
                    str(self.max_entries),
                )
                if result == 1:
                    return entry
                if result == -2:
                    raise RuntimeError("AUDIT_CHAIN_METADATA_MISSING")
                if result == -3:
                    raise RuntimeError("AUDIT_CHAIN_TRIM_INVARIANT_FAILED")
                # Bounded backoff prevents two busy instances from repeatedly
                # colliding on the same observed tail while retaining fail-closed
                # exhaustion semantics.
                await asyncio.sleep(min(0.0005 * (attempt + 1), 0.01))
        raise RuntimeError("AUDIT_CHAIN_CONTENTION_RETRY_EXHAUSTED")

    async def certify(self) -> dict[str, Any]:
        assert self.redis is not None
        snapshot = await self.redis.eval(
            _SNAPSHOT_LUA,
            4,
            self.anchor_key,
            self.seq_key,
            self.tail_key,
            self.chain_key,
        )
        if not isinstance(snapshot, list) or len(snapshot) != 4:
            return {"is_valid": False, "reason": "AUDIT_CHAIN_SNAPSHOT_INVALID"}
        anchor_raw, seq_raw, tail_raw, raw_entries = snapshot
        if anchor_raw is None or seq_raw is None or tail_raw is None or not isinstance(raw_entries, list):
            return {"is_valid": False, "reason": "AUDIT_CHAIN_METADATA_MISSING"}
        try:
            anchor = ChainAnchor.from_json(anchor_raw)
            entries = [json.loads(raw) for raw in raw_entries]
            cert = certify_snapshot(entries, anchor)
        except Exception as exc:  # fail closed; certification is evidence, never best-effort
            return {"is_valid": False, "reason": f"AUDIT_CHAIN_PARSE_FAILURE:{type(exc).__name__}"}
        if cert.get("is_valid"):
            if int(cert["next_sequence"]) != int(seq_raw):
                return {**cert, "is_valid": False, "reason": "SEQUENCE_METADATA_MISMATCH"}
            if str(cert["terminal_hash"]) != tail_raw:
                return {**cert, "is_valid": False, "reason": "TAIL_METADATA_MISMATCH"}
        return cert

    async def get_entry(self, seq: int) -> dict[str, Any] | None:
        assert self.redis is not None
        if seq < 0:
            return None
        raw = await self.redis.eval(
            _GET_ENTRY_LUA,
            2,
            self.anchor_key,
            self.chain_key,
            str(seq),
        )
        if raw is None:
            return None
        entry = json.loads(raw)
        return entry if entry.get("sequence") == seq else None

    async def full_chain(self, limit: int = 200) -> list[dict[str, Any]]:
        assert self.redis is not None
        if limit <= 0:
            return []
        raw_entries = await self.redis.lrange(self.chain_key, -min(limit, self.max_entries), -1)
        return [json.loads(raw) for raw in raw_entries]
