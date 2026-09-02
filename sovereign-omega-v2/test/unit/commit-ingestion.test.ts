/**
 * Section 9.3 — the ingestion operator, and the end-to-end proof that A3, A7,
 * A8 and V_hash compose rather than merely coexisting.
 */
import { describe, expect, it } from 'vitest'
import { GENESIS_ANCHOR, type LedgerState } from '../../src/sovereignty/commit-admission.js'
import { semanticHash, type SemanticVertex } from '../../src/sovereignty/semantic-hash.js'
import {
  admitCommit,
  applyIngestion,
  ingest,
} from '../../src/sovereignty/commit-ingestion.js'

const SNAPSHOT = `sha256:${'d'.repeat(64)}`

const base = (over: Partial<SemanticVertex> = {}): SemanticVertex => ({
  id: 'v0',
  parent: GENESIS_ANCHOR,
  causal_tuple: [GENESIS_ANCHOR, GENESIS_ANCHOR, null],
  transform: 'normal_commit',
  rebase_extension: null,
  semantic_hash: `sha256:${'0'.repeat(64)}`,
  hlc: { logical: 1, counter: 0, node: 'node-a' },
  authority_delta: null,
  policy_delta: null,
  rollback_digest: null,
  root9: 0,
  ...over,
})

/** Build a vertex carrying its own correct hash. */
async function sealed(over: Partial<SemanticVertex> = {}): Promise<SemanticVertex> {
  const draft = base(over)
  return { ...draft, semantic_hash: await semanticHash(draft) }
}

const emptyLedger = (over: Partial<LedgerState> = {}): LedgerState => ({
  active_count: 0,
  breaker_tripped: false,
  active_snapshot_hash: SNAPSHOT,
  known_ids: [],
  has_genesis: false,
  known_vertex_hashes: [],
  ...over,
})

describe('admitCommit — V_hash computed, not asserted', () => {
  it('admits a correctly sealed genesis vertex', async () => {
    const decision = await admitCommit(await sealed(), emptyLedger(), SNAPSHOT)
    expect(decision.admitted).toBe(true)
    expect(decision.computed_hash_verified).toBe(true)
    expect(decision.failures).toEqual([])
  })

  it('refuses a vertex whose claimed hash does not match its content', async () => {
    // The caller cannot assert its way past this: the hash is recomputed here.
    const decision = await admitCommit(base(), emptyLedger(), SNAPSHOT)
    expect(decision.computed_hash_verified).toBe(false)
    expect(decision.failures).toContain('semantic_hash_mismatch')
    expect(decision.admitted).toBe(false)
  })

  it('refuses content edited after sealing', async () => {
    const v = await sealed()
    const tampered: SemanticVertex = { ...v, root9: 999 }
    expect((await admitCommit(tampered, emptyLedger(), SNAPSHOT)).admitted).toBe(false)
  })
})

describe('applyIngestion — section 9.3', () => {
  it('advances every field the transition touches', async () => {
    const v = await sealed()
    const before = emptyLedger()
    const after = applyIngestion(v, before, await admitCommit(v, before, SNAPSHOT))

    expect(after).not.toBeNull()
    expect(after?.active_count).toBe(1)
    expect(after?.known_ids).toEqual(['v0'])
    expect(after?.known_vertex_hashes).toEqual([v.semantic_hash])
    expect(after?.has_genesis).toBe(true)
    // Untouched by the transition.
    expect(after?.breaker_tripped).toBe(false)
    expect(after?.active_snapshot_hash).toBe(SNAPSHOT)
  })

  it('returns bottom on denial and leaves the prior state untouched', async () => {
    const before = emptyLedger()
    const decision = await admitCommit(base(), before, SNAPSHOT) // unsealed
    expect(applyIngestion(base(), before, decision)).toBeNull()
    expect(before).toEqual(emptyLedger())
  })

  it('refuses a decision reached about a different vertex', async () => {
    // Deciding and applying are separate calls, so the two arguments can
    // disagree. An admit for one vertex must not carry another one in.
    const admitted = await sealed()
    const other = await sealed({ id: 'v-other', root9: 7 })
    const decision = await admitCommit(admitted, emptyLedger(), SNAPSHOT)

    expect(decision.admitted).toBe(true)
    expect(decision.vertex_hash).toBe(admitted.semantic_hash)
    expect(applyIngestion(other, emptyLedger(), decision)).toBeNull()
  })

  it('does not mutate the state it was given', async () => {
    const v = await sealed()
    const before = emptyLedger()
    const snapshot = JSON.stringify(before)
    applyIngestion(v, before, await admitCommit(v, before, SNAPSHOT))
    expect(JSON.stringify(before)).toBe(snapshot)
  })

  it('freezes the successor, so a later write fails rather than silently landing', async () => {
    const v = await sealed()
    const after = applyIngestion(v, emptyLedger(), await admitCommit(v, emptyLedger(), SNAPSHOT))
    expect(Object.isFrozen(after)).toBe(true)
    expect(Object.isFrozen(after?.known_vertex_hashes)).toBe(true)
  })
})

describe('end to end — the amendments compose', () => {
  it('genesis admits, then its child admits because A8 is now satisfied', async () => {
    const genesis = await sealed()
    const step1 = await ingest(genesis, emptyLedger(), SNAPSHOT)
    expect(step1.decision.admitted).toBe(true)
    expect(step1.next).not.toBeNull()

    // The child names the genesis vertex's real hash as its parent.
    const child = await sealed({
      id: 'v1',
      parent: genesis.semantic_hash,
      causal_tuple: [genesis.semantic_hash, genesis.semantic_hash, null],
      hlc: { logical: 2, counter: 0, node: 'node-a' },
      root9: 1,
    })
    const step2 = await ingest(child, step1.next as LedgerState, SNAPSHOT)
    expect(step2.decision.failures).toEqual([])
    expect(step2.next?.active_count).toBe(2)
    expect(step2.next?.known_vertex_hashes).toEqual([genesis.semantic_hash, child.semantic_hash])
  })

  it('the same child is refused against the empty ledger — order is load-bearing', async () => {
    const genesis = await sealed()
    const child = await sealed({
      id: 'v1',
      parent: genesis.semantic_hash,
      causal_tuple: [genesis.semantic_hash, genesis.semantic_hash, null],
      hlc: { logical: 2, counter: 0, node: 'node-a' },
      root9: 1,
    })
    const out = await ingest(child, emptyLedger(), SNAPSHOT)
    expect(out.decision.failures).toEqual(['parent_absent'])
    expect(out.next).toBeNull()
  })

  it('A7 still holds after a root is ingested — a second root is refused', async () => {
    const genesis = await sealed()
    const first = await ingest(genesis, emptyLedger(), SNAPSHOT)
    const rival = await sealed({ id: 'v0-bis', hlc: { logical: 9, counter: 0, node: 'node-b' } })
    const out = await ingest(rival, first.next as LedgerState, SNAPSHOT)
    expect(out.decision.failures).toContain('duplicate_genesis')
    expect(out.next).toBeNull()
  })
})
