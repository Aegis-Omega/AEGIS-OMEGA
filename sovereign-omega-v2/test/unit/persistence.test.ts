// ============================================================
// Gate 23 — Ledger Persistence Seam Tests
// ~18 tests: serialize/deserialize snapshot and chain,
//   determinism, error cases, frozen output
// ============================================================

import { describe, it, expect } from 'vitest'
import { LedgerChain } from '../../src/ledger/chain.js'
import {
  GENESIS_HASH,
  LEDGER_SCHEMA_VERSION,
  type LedgerEntry,
} from '../../src/ledger/types.js'
import { captureCheckpoint } from '../../src/ledger/checkpoint.js'
import {
  LedgerPersistenceError,
  serializeSnapshot,
  deserializeSnapshot,
  serializeChain,
  deserializeChain,
} from '../../src/ledger/persistence.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

// ─── Helpers ───────────────────────────────────────────────

const TS = 1_600_000_000_000  // fixed epoch constant — never Date.now()

function makeEntry(
  seq: bigint,
  previousHash: SHA256Hex = GENESIS_HASH,
): LedgerEntry {
  return Object.freeze({
    sequence: seq as SequenceNumber,
    previous_hash: previousHash,
    frame_hash: ('f'.repeat(64)) as SHA256Hex,
    governance_hash: ('e'.repeat(64)) as SHA256Hex,
    timestamp_ms: TS + Number(seq),
  })
}

async function buildChainWithSnapshot(length: number) {
  let chain = LedgerChain.empty()
  for (let i = 1; i <= length; i++) {
    chain = chain.append(makeEntry(BigInt(i)))
  }
  const snap = await captureCheckpoint(chain)
  return { chain, snap }
}

// ─── serializeSnapshot ─────────────────────────────────────

describe('serializeSnapshot', () => {
  it('produces a non-empty string', async () => {
    const { snap } = await buildChainWithSnapshot(1)
    const json = serializeSnapshot(snap)
    expect(typeof json).toBe('string')
    expect(json.length).toBeGreaterThan(0)
  })

  it('is deterministic — same snapshot → identical string 3 times', async () => {
    const { snap } = await buildChainWithSnapshot(3)
    const r1 = serializeSnapshot(snap)
    const r2 = serializeSnapshot(snap)
    const r3 = serializeSnapshot(snap)
    expect(r1).toBe(r2)
    expect(r2).toBe(r3)
  })

  it('empty chain snapshot serializes without error', async () => {
    const snap = await captureCheckpoint(LedgerChain.empty())
    const json = serializeSnapshot(snap)
    expect(typeof json).toBe('string')
    // Should contain entry_count: 0
    expect(json).toContain('"entry_count":0')
  })

  it('different snapshots produce different serializations', async () => {
    const { snap: snap1 } = await buildChainWithSnapshot(2)
    const { snap: snap2 } = await buildChainWithSnapshot(3)
    const s1 = serializeSnapshot(snap1)
    const s2 = serializeSnapshot(snap2)
    expect(s1).not.toBe(s2)
  })

  it('output is valid JSON (parseable)', async () => {
    const { snap } = await buildChainWithSnapshot(2)
    const json = serializeSnapshot(snap)
    expect(() => JSON.parse(json)).not.toThrow()
  })
})

// ─── deserializeSnapshot ───────────────────────────────────

describe('deserializeSnapshot', () => {
  it('roundtrip: serialize → deserialize preserves entry_count', async () => {
    const { snap } = await buildChainWithSnapshot(3)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(restored.entry_count).toBe(snap.entry_count)
  })

  it('roundtrip: serialize → deserialize preserves entries sequence numbers', async () => {
    const { snap } = await buildChainWithSnapshot(3)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(restored.entries).toHaveLength(3)
    expect(restored.entries[0]?.sequence).toBe(1n)
    expect(restored.entries[1]?.sequence).toBe(2n)
    expect(restored.entries[2]?.sequence).toBe(3n)
  })

  it('roundtrip: serialize → deserialize preserves merkle_root', async () => {
    const { snap } = await buildChainWithSnapshot(2)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(restored.merkle_root).toBe(snap.merkle_root)
  })

  it('roundtrip: serialize → deserialize preserves schema_version and flags', async () => {
    const { snap } = await buildChainWithSnapshot(1)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(restored.schema_version).toBe(LEDGER_SCHEMA_VERSION)
    expect(restored.is_replay_reconstructable).toBe(true)
  })

  it('roundtrip: serialize → deserialize preserves snapshot_sequence', async () => {
    const { snap } = await buildChainWithSnapshot(4)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(restored.snapshot_sequence).toBe(4n)
  })

  it('result is deeply frozen', async () => {
    const { snap } = await buildChainWithSnapshot(2)
    const json = serializeSnapshot(snap)
    const restored = deserializeSnapshot(json)
    expect(Object.isFrozen(restored)).toBe(true)
    expect(Object.isFrozen(restored.entries)).toBe(true)
    if (restored.entries[0]) {
      expect(Object.isFrozen(restored.entries[0])).toBe(true)
    }
  })

  it('throws LedgerPersistenceError on invalid JSON', () => {
    expect(() => deserializeSnapshot('not json {')).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot('not json {')).toThrow(/Invalid JSON/)
  })

  it('throws LedgerPersistenceError on wrong schema_version', async () => {
    const { snap } = await buildChainWithSnapshot(1)
    const json = serializeSnapshot(snap)
    const tampered = json.replace('"1.0.0"', '"2.0.0"')
    expect(() => deserializeSnapshot(tampered)).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(tampered)).toThrow(/schema_version mismatch/)
  })

  it('throws LedgerPersistenceError on wrong entry_count', async () => {
    const { snap } = await buildChainWithSnapshot(2)
    const json = serializeSnapshot(snap)
    // entry_count field is numeric; replace 2 with 99 carefully
    // We know entry_count:2 appears in the JSON — replace the value
    const parsed = JSON.parse(json) as Record<string, unknown>
    parsed['entry_count'] = 99
    const tampered = JSON.stringify(parsed)
    expect(() => deserializeSnapshot(tampered)).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(tampered)).toThrow(/entry_count mismatch/)
  })

  it('throws LedgerPersistenceError on is_replay_reconstructable false', async () => {
    const { snap } = await buildChainWithSnapshot(1)
    const json = serializeSnapshot(snap)
    const parsed = JSON.parse(json) as Record<string, unknown>
    parsed['is_replay_reconstructable'] = false
    const tampered = JSON.stringify(parsed)
    expect(() => deserializeSnapshot(tampered)).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(tampered)).toThrow(/is_replay_reconstructable/)
  })

  it('throws LedgerPersistenceError on missing required entry field (frame_hash)', async () => {
    const { snap } = await buildChainWithSnapshot(1)
    const json = serializeSnapshot(snap)
    const parsed = JSON.parse(json) as Record<string, unknown>
    const entries = parsed['entries'] as Array<Record<string, unknown>>
    if (entries[0]) {
      delete entries[0]['frame_hash']
    }
    const tampered = JSON.stringify(parsed)
    expect(() => deserializeSnapshot(tampered)).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(tampered)).toThrow(/frame_hash/)
  })
})

// ─── serializeChain / deserializeChain ─────────────────────

describe('serializeChain / deserializeChain', () => {
  it('roundtrip: serialize → deserialize produces chain with same length', async () => {
    const { chain } = await buildChainWithSnapshot(4)
    const json = await serializeChain(chain)
    const restored = await deserializeChain(json)
    expect(restored.length).toBe(4)
  })

  it('roundtrip: deserialized chain has correct sequence numbers', async () => {
    const { chain } = await buildChainWithSnapshot(3)
    const json = await serializeChain(chain)
    const restored = await deserializeChain(json)
    const all = restored.getAll()
    expect(all[0]?.sequence).toBe(1n)
    expect(all[1]?.sequence).toBe(2n)
    expect(all[2]?.sequence).toBe(3n)
  })

  it('roundtrip: empty chain serializes and deserializes to empty chain', async () => {
    const chain = LedgerChain.empty()
    const json = await serializeChain(chain)
    const restored = await deserializeChain(json)
    expect(restored.length).toBe(0)
    expect(restored.lastEntry).toBeNull()
  })

  it('deserializeChain throws LedgerPersistenceError on invalid JSON', async () => {
    await expect(deserializeChain('not json')).rejects.toThrow(LedgerPersistenceError)
  })

  it('deserialized chain allows further appends (correct lastSequence)', async () => {
    const { chain } = await buildChainWithSnapshot(2)
    const json = await serializeChain(chain)
    const restored = await deserializeChain(json)
    expect(restored.lastSequence).toBe(2n)
    // Should allow appending a higher sequence
    const extended = restored.append(makeEntry(3n))
    expect(extended.length).toBe(3)
  })
})
