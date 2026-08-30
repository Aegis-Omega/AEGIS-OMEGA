// ============================================================
// Persistence Extended Tests — ledger/persistence.ts
// Targets uncovered branches in deserializeSnapshot:
//   non-object input, entries not array, entry_count not number,
//   merkle_root wrong, snapshot_sequence not string,
//   entry not object, entry.sequence not string,
//   entry.previous_hash wrong, entry.governance_hash wrong,
//   entry.timestamp_ms not number
// ============================================================

import { describe, it, expect } from 'vitest'
import {
  LedgerPersistenceError,
  deserializeSnapshot,
} from '../../src/ledger/persistence.js'
import { LEDGER_SCHEMA_VERSION } from '../../src/ledger/types.js'

// ─── Helpers ─────────────────────────────────────────────────

const GOOD_HASH = '0'.repeat(64)
const GOOD_ENTRY = {
  sequence: '1',
  previous_hash: GOOD_HASH,
  frame_hash: GOOD_HASH,
  governance_hash: GOOD_HASH,
  timestamp_ms: 1_600_000_000_000,
}

function minimalValid(overrides: Record<string, unknown> = {}): string {
  return JSON.stringify({
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
    entries: [],
    entry_count: 0,
    merkle_root: GOOD_HASH,
    snapshot_sequence: '0',
    ...overrides,
  })
}

function withEntry(entryOverride: Record<string, unknown>): string {
  const entry = { ...GOOD_ENTRY, ...entryOverride }
  return JSON.stringify({
    schema_version: LEDGER_SCHEMA_VERSION,
    is_replay_reconstructable: true,
    entries: [entry],
    entry_count: 1,
    merkle_root: GOOD_HASH,
    snapshot_sequence: '1',
  })
}

// ─── Non-object inputs ───────────────────────────────────────

describe('deserializeSnapshot: non-object JSON input', () => {
  it('throws on JSON null', () => {
    expect(() => deserializeSnapshot('null')).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot('null')).toThrow(/JSON object/)
  })

  it('throws on JSON array', () => {
    expect(() => deserializeSnapshot('[]')).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot('[]')).toThrow(/JSON object/)
  })

  it('throws on JSON number', () => {
    expect(() => deserializeSnapshot('42')).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot('42')).toThrow(/JSON object/)
  })

  it('throws on JSON string', () => {
    expect(() => deserializeSnapshot('"hello"')).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot('"hello"')).toThrow(/JSON object/)
  })
})

// ─── entries not array ───────────────────────────────────────

describe('deserializeSnapshot: entries not array', () => {
  it('throws when entries is a string', () => {
    expect(() => deserializeSnapshot(minimalValid({ entries: 'bad' }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(minimalValid({ entries: 'bad' }))).toThrow(/entries/)
  })

  it('throws when entries is null', () => {
    expect(() => deserializeSnapshot(minimalValid({ entries: null }))).toThrow(LedgerPersistenceError)
  })

  it('throws when entries is a number', () => {
    expect(() => deserializeSnapshot(minimalValid({ entries: 5 }))).toThrow(LedgerPersistenceError)
  })
})

// ─── entry_count not a number ────────────────────────────────

describe('deserializeSnapshot: entry_count not a number', () => {
  it('throws when entry_count is a string', () => {
    expect(() => deserializeSnapshot(minimalValid({ entry_count: '0' }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(minimalValid({ entry_count: '0' }))).toThrow(/entry_count/)
  })

  it('throws when entry_count is null', () => {
    expect(() => deserializeSnapshot(minimalValid({ entry_count: null }))).toThrow(LedgerPersistenceError)
  })
})

// ─── merkle_root wrong ───────────────────────────────────────

describe('deserializeSnapshot: merkle_root validation', () => {
  it('throws when merkle_root is not a string', () => {
    expect(() => deserializeSnapshot(minimalValid({ merkle_root: 42 }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(minimalValid({ merkle_root: 42 }))).toThrow(/merkle_root/)
  })

  it('throws when merkle_root is less than 64 chars', () => {
    expect(() => deserializeSnapshot(minimalValid({ merkle_root: 'a'.repeat(32) }))).toThrow(LedgerPersistenceError)
  })

  it('throws when merkle_root is more than 64 chars', () => {
    expect(() => deserializeSnapshot(minimalValid({ merkle_root: 'a'.repeat(65) }))).toThrow(LedgerPersistenceError)
  })
})

// ─── snapshot_sequence not a string ─────────────────────────

describe('deserializeSnapshot: snapshot_sequence not a string', () => {
  it('throws when snapshot_sequence is a number', () => {
    expect(() => deserializeSnapshot(minimalValid({ snapshot_sequence: 0 }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(minimalValid({ snapshot_sequence: 0 }))).toThrow(/snapshot_sequence/)
  })

  it('throws when snapshot_sequence is null', () => {
    expect(() => deserializeSnapshot(minimalValid({ snapshot_sequence: null }))).toThrow(LedgerPersistenceError)
  })
})

// ─── entry not an object ─────────────────────────────────────

describe('deserializeSnapshot: entry not an object', () => {
  it('throws when an entry is null', () => {
    const json = JSON.stringify({
      schema_version: LEDGER_SCHEMA_VERSION,
      is_replay_reconstructable: true,
      entries: [null],
      entry_count: 1,
      merkle_root: GOOD_HASH,
      snapshot_sequence: '1',
    })
    expect(() => deserializeSnapshot(json)).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(json)).toThrow(/entry\[0\]/)
  })

  it('throws when an entry is a string', () => {
    const json = JSON.stringify({
      schema_version: LEDGER_SCHEMA_VERSION,
      is_replay_reconstructable: true,
      entries: ['bad'],
      entry_count: 1,
      merkle_root: GOOD_HASH,
      snapshot_sequence: '1',
    })
    expect(() => deserializeSnapshot(json)).toThrow(LedgerPersistenceError)
  })
})

// ─── entry.sequence not a string ────────────────────────────

describe('deserializeSnapshot: entry.sequence not a string', () => {
  it('throws when entry.sequence is a number', () => {
    expect(() => deserializeSnapshot(withEntry({ sequence: 1 }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(withEntry({ sequence: 1 }))).toThrow(/sequence/)
  })

  it('throws when entry.sequence is null', () => {
    expect(() => deserializeSnapshot(withEntry({ sequence: null }))).toThrow(LedgerPersistenceError)
  })
})

// ─── entry.previous_hash wrong ───────────────────────────────

describe('deserializeSnapshot: entry.previous_hash validation', () => {
  it('throws when previous_hash is not a string', () => {
    expect(() => deserializeSnapshot(withEntry({ previous_hash: 42 }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(withEntry({ previous_hash: 42 }))).toThrow(/previous_hash/)
  })

  it('throws when previous_hash is too short', () => {
    expect(() => deserializeSnapshot(withEntry({ previous_hash: 'abc' }))).toThrow(LedgerPersistenceError)
  })
})

// ─── entry.governance_hash wrong ─────────────────────────────

describe('deserializeSnapshot: entry.governance_hash validation', () => {
  it('throws when governance_hash is not a string', () => {
    expect(() => deserializeSnapshot(withEntry({ governance_hash: null }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(withEntry({ governance_hash: null }))).toThrow(/governance_hash/)
  })

  it('throws when governance_hash is wrong length', () => {
    expect(() => deserializeSnapshot(withEntry({ governance_hash: 'bad' }))).toThrow(LedgerPersistenceError)
  })
})

// ─── entry.timestamp_ms not a number ─────────────────────────

describe('deserializeSnapshot: entry.timestamp_ms validation', () => {
  it('throws when timestamp_ms is a string', () => {
    expect(() => deserializeSnapshot(withEntry({ timestamp_ms: '1600000000000' }))).toThrow(LedgerPersistenceError)
    expect(() => deserializeSnapshot(withEntry({ timestamp_ms: '1600000000000' }))).toThrow(/timestamp_ms/)
  })

  it('throws when timestamp_ms is null', () => {
    expect(() => deserializeSnapshot(withEntry({ timestamp_ms: null }))).toThrow(LedgerPersistenceError)
  })
})

// ─── Valid minimal snapshot passes ────────────────────────────

describe('deserializeSnapshot: valid minimal snapshot', () => {
  it('accepts empty snapshot with correct fields', () => {
    expect(() => deserializeSnapshot(minimalValid())).not.toThrow()
  })

  it('accepts snapshot with one entry', () => {
    expect(() => deserializeSnapshot(withEntry({}))).not.toThrow()
  })
})
