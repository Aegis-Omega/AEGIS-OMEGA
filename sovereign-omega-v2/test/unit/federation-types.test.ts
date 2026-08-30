import { describe, it, expect } from 'vitest'
import {
  buildSyncRecord, buildNodeManifest, FederationError, FEDERATION_SCHEMA_VERSION,
} from '../../src/federation/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const HASH_A = 'a'.repeat(64) as SHA256Hex
const HASH_B = 'b'.repeat(64) as SHA256Hex
const seq = (n: number) => BigInt(n) as SequenceNumber

describe('FEDERATION_SCHEMA_VERSION', () => {
  it('is 1.0.0', () => { expect(FEDERATION_SCHEMA_VERSION).toBe('1.0.0') })
})

describe('buildSyncRecord', () => {
  it('produces frozen FederationSyncRecord', async () => {
    const r = await buildSyncRecord({ source_node_id: 'node-a', target_node_id: 'node-b', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    expect(Object.isFrozen(r)).toBe(true)
  })

  it('sync_hash is 64-char hex', async () => {
    const r = await buildSyncRecord({ source_node_id: 'na', target_node_id: 'nb', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    expect(r.sync_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable=true', async () => {
    const r = await buildSyncRecord({ source_node_id: 'na', target_node_id: 'nb', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    expect(r.is_replay_reconstructable).toBe(true)
  })

  it('schema_version=1.0.0', async () => {
    const r = await buildSyncRecord({ source_node_id: 'na', target_node_id: 'nb', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    expect(r.schema_version).toBe('1.0.0')
  })

  it('sync_hash is deterministic ×3', async () => {
    const run = () => buildSyncRecord({ source_node_id: 'n1', target_node_id: 'n2', lineage_terminal_hash: HASH_A, sequence: seq(5) })
    const [r1, r2, r3] = await Promise.all([run(), run(), run()])
    expect(r1.sync_hash).toBe(r2.sync_hash)
    expect(r2.sync_hash).toBe(r3.sync_hash)
  })

  it('different source → different sync_hash', async () => {
    const r1 = await buildSyncRecord({ source_node_id: 'n1', target_node_id: 'n2', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    const r2 = await buildSyncRecord({ source_node_id: 'n3', target_node_id: 'n2', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    expect(r1.sync_hash).not.toBe(r2.sync_hash)
  })

  it('different lineage_terminal_hash → different sync_hash', async () => {
    const r1 = await buildSyncRecord({ source_node_id: 'n1', target_node_id: 'n2', lineage_terminal_hash: HASH_A, sequence: seq(1) })
    const r2 = await buildSyncRecord({ source_node_id: 'n1', target_node_id: 'n2', lineage_terminal_hash: HASH_B, sequence: seq(1) })
    expect(r1.sync_hash).not.toBe(r2.sync_hash)
  })

  it('empty source_node_id throws FederationError', async () => {
    await expect(buildSyncRecord({ source_node_id: '', target_node_id: 'nb', lineage_terminal_hash: HASH_A, sequence: seq(1) }))
      .rejects.toBeInstanceOf(FederationError)
  })

  it('empty target_node_id throws FederationError', async () => {
    await expect(buildSyncRecord({ source_node_id: 'na', target_node_id: '', lineage_terminal_hash: HASH_A, sequence: seq(1) }))
      .rejects.toBeInstanceOf(FederationError)
  })
})

describe('buildNodeManifest', () => {
  it('produces frozen SovereignNodeManifest', async () => {
    const m = await buildNodeManifest({ node_id: 'node-1', role: 'sovereign-node', public_key_fingerprint: 'fp-stub', lineage_root_hash: HASH_A })
    expect(Object.isFrozen(m)).toBe(true)
  })

  it('is_replay_reconstructable=true', async () => {
    const m = await buildNodeManifest({ node_id: 'n1', role: 'constitutional-witness', public_key_fingerprint: 'fp', lineage_root_hash: HASH_A })
    expect(m.is_replay_reconstructable).toBe(true)
  })

  it('schema_version=1.0.0', async () => {
    const m = await buildNodeManifest({ node_id: 'n1', role: 'federation-relay', public_key_fingerprint: 'fp', lineage_root_hash: HASH_A })
    expect(m.schema_version).toBe('1.0.0')
  })

  it('empty node_id throws FederationError', async () => {
    await expect(buildNodeManifest({ node_id: '', role: 'sovereign-node', public_key_fingerprint: 'fp', lineage_root_hash: HASH_A }))
      .rejects.toBeInstanceOf(FederationError)
  })

  it('all three roles accepted', async () => {
    const roles = ['sovereign-node', 'constitutional-witness', 'federation-relay'] as const
    for (const role of roles) {
      const m = await buildNodeManifest({ node_id: 'n', role, public_key_fingerprint: 'fp', lineage_root_hash: HASH_A })
      expect(m.role).toBe(role)
    }
  })
})

describe('FederationError', () => {
  it('is an Error subclass with correct name', () => {
    const err = new FederationError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('FederationError')
  })
})
