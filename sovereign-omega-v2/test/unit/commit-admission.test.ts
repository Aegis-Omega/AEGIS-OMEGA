/**
 * Pins the mechanically decidable fragment of the AEGIS OMEGA formal
 * reconstruction, post-amendment (A1, A2, A3, A6).
 *
 * Two kinds of test live here. Most pin intended behaviour. A few pin a defect
 * or an unenforced gap on purpose, named so in the test title, so that a reader
 * of the spec alone cannot reintroduce it and cannot mistake silence for
 * coverage.
 */
import { describe, expect, it } from 'vitest'
import {
  HOT_GRAPH_CAPACITY,
  GENESIS_ANCHOR,
  admissionFailures,
  cgcWeight,
  isAdmissible,
  isSha256Ref,
  root9Enforce,
  isGenesis,
  isGenesisAnchor,
  proofReferencesPresent,
  validStrategy,
  validTuple,
  type CommitVertex,
  type LedgerState,
  type RebaseExtension,
} from '../../src/sovereignty/commit-admission.js'

const h = (d: string) => `sha256:${d.repeat(64)}`
const PARENT = h('a')
const INTENDED = h('b')
const DECISION = h('c')
const SNAPSHOT = h('d')
const PROOF = h('e')

const proofs = (over: Record<string, string | null> = {}) => ({
  equivalence_proof_hash: PROOF,
  adaptation_proof_hash: null,
  verification_key_hash: h('1'),
  circuit_hash: h('2'),
  ...over,
})

const ext = (over: Partial<RebaseExtension> = {}): RebaseExtension => ({
  strategy: 'reparent_to_active_sibling',
  mode: 'pure_relocation',
  original_intended_parent_hash: INTENDED,
  selected_parent_hash: PARENT,
  decision_record_hash: DECISION,
  proofs: proofs(),
  ...over,
})

const rebaseVertex = (over: Partial<CommitVertex> = {}): CommitVertex => ({
  id: 'v1',
  parent: PARENT,
  causal_tuple: [PARENT, INTENDED, DECISION],
  transform: 'rebase_to_active_sibling',
  rebase_extension: ext(),
  ...over,
})

const normalVertex = (over: Partial<CommitVertex> = {}): CommitVertex => ({
  id: 'v2',
  parent: PARENT,
  causal_tuple: [PARENT, PARENT, null],
  transform: 'normal_commit',
  rebase_extension: null,
  ...over,
})

const ledger = (over: Partial<LedgerState> = {}): LedgerState => ({
  active_count: 10,
  breaker_tripped: false,
  active_snapshot_hash: SNAPSHOT,
  known_ids: [],
  ...over,
})

describe('section 10.1 — hash syntax', () => {
  it('accepts only the exact sha256 reference form', () => {
    expect(isSha256Ref(PARENT)).toBe(true)
    expect(isSha256Ref(null)).toBe(false)
    expect(isSha256Ref('sha256:' + 'A'.repeat(64))).toBe(false) // uppercase hex
    expect(isSha256Ref('sha256:' + 'a'.repeat(63))).toBe(false) // short
    expect(isSha256Ref('sha256:' + 'a'.repeat(65))).toBe(false) // long
    expect(isSha256Ref('a'.repeat(64))).toBe(false) // no prefix
  })
})

describe('section 7.3 — Root9 step enforcement', () => {
  it('maps each band to its action', () => {
    expect(root9Enforce(0)).toBe('accept')
    expect(root9Enforce(107)).toBe('accept')
    expect(root9Enforce(108)).toBe('score_branches')
    expect(root9Enforce(511)).toBe('score_branches')
    expect(root9Enforce(512)).toBe('expand_cgc')
    expect(root9Enforce(1023)).toBe('expand_cgc')
    expect(root9Enforce(1024)).toBe('fail_closed')
  })

  it('agrees with the section 9.2 capacity assertion at the boundary', () => {
    // N+1 <= 1024 admits at N=1023 and refuses at N=1024; E(N) fail-closes at 1024.
    expect(isAdmissible(normalVertex(), ledger({ active_count: 1023 }), SNAPSHOT)).toBe(true)
    expect(admissionFailures(normalVertex(), ledger({ active_count: 1024 }), SNAPSHOT)).toContain(
      'capacity_exhausted',
    )
    expect(root9Enforce(HOT_GRAPH_CAPACITY)).toBe('fail_closed')
  })
})

describe('section 7.4 — CGC weight', () => {
  it('is continuous at the top and discontinuous at both lower thresholds', () => {
    expect(cgcWeight(107)).toBe(0)
    expect(cgcWeight(108)).toBe(0.2)
    expect(cgcWeight(511)).toBe(0.2)
    expect(cgcWeight(512)).toBe(0.6) // SPEC DEFECT: jumps 0.2 -> 0.6, a 3x step
    expect(cgcWeight(768)).toBeCloseTo(0.8, 10)
    expect(cgcWeight(1023)).toBeCloseTo(0.6 + (0.4 * 511) / 512, 10)
    expect(cgcWeight(1024)).toBe(1.0) // continuous here: the linear arm reaches 1.0
  })

  it('never leaves [0, 1]', () => {
    for (const n of [0, 107, 108, 511, 512, 900, 1023, 1024, 5000]) {
      expect(cgcWeight(n)).toBeGreaterThanOrEqual(0)
      expect(cgcWeight(n)).toBeLessThanOrEqual(1)
    }
  })
})

describe('section 10.2 — causal tuple validity', () => {
  it('accepts a well-formed rebase tuple and a well-formed degenerate tuple', () => {
    expect(validTuple(rebaseVertex())).toBe(true)
    expect(validTuple(normalVertex())).toBe(true)
  })

  it('rejects a rebase tuple whose components disagree with its extension', () => {
    expect(validTuple(rebaseVertex({ causal_tuple: [PARENT, h('9'), DECISION] }))).toBe(false)
    expect(validTuple(rebaseVertex({ causal_tuple: [PARENT, INTENDED, h('9')] }))).toBe(false)
  })

  it('rejects a non-rebase vertex that smuggles a decision hash into c2', () => {
    expect(validTuple(normalVertex({ causal_tuple: [PARENT, PARENT, DECISION] }))).toBe(false)
  })

})

describe('A3 — genesis anchor', () => {
  const genesis = (over: Partial<CommitVertex> = {}): CommitVertex =>
    normalVertex({
      id: 'v0',
      parent: GENESIS_ANCHOR,
      causal_tuple: [GENESIS_ANCHOR, GENESIS_ANCHOR, null],
      ...over,
    })

  it('the anchor is outside H, so no digest can ever collide with it', () => {
    expect(isSha256Ref(GENESIS_ANCHOR)).toBe(false)
    expect(isGenesisAnchor(GENESIS_ANCHOR)).toBe(true)
    expect(isGenesisAnchor(PARENT)).toBe(false)
  })

  it('admits the root vertex that was unrepresentable before the amendment', () => {
    expect(isGenesis(genesis())).toBe(true)
    expect(validTuple(genesis())).toBe(true)
    expect(isAdmissible(genesis(), ledger({ active_count: 0 }), SNAPSHOT)).toBe(true)
  })

  it('does not let a non-root vertex borrow the root exemption', () => {
    // Anchor in c0 but a real parent hash: not genesis, and c0 !== parent.
    expect(validTuple(genesis({ parent: PARENT }))).toBe(false)
    // Anchor in only one tuple slot.
    expect(validTuple(genesis({ causal_tuple: [GENESIS_ANCHOR, PARENT, null] }))).toBe(false)
    expect(validTuple(genesis({ causal_tuple: [PARENT, GENESIS_ANCHOR, null] }))).toBe(false)
  })

  it('refuses a genesis vertex that carries a decision hash or a rebase pass', () => {
    expect(validTuple(genesis({ causal_tuple: [GENESIS_ANCHOR, GENESIS_ANCHOR, DECISION] }))).toBe(false)
    expect(validTuple(genesis({ transform: 'merge_commit' }))).toBe(false)
    expect(
      validTuple(genesis({ transform: 'rebase_to_active_sibling', rebase_extension: ext() })),
    ).toBe(false)
  })

  it('NOT ENFORCED: nothing bounds a ledger to one genesis vertex', () => {
    // Found while implementing A3. Admission is per-vertex and section 9.2 has
    // no assertion over the ledger's existing roots, so a second genesis is
    // admissible and the DAG becomes a forest. Recorded, not silently fixed —
    // whether roots must be unique is a spec decision.
    const second = genesis({ id: 'v0-bis' })
    expect(isAdmissible(second, ledger({ known_ids: ['v0'] }), SNAPSHOT)).toBe(true)
  })
})

describe('section 10.3 / A1 — strategy alignment, and the fail-open it closes', () => {
  it('requires the strategy to match the transform pass', () => {
    expect(validStrategy(rebaseVertex())).toBe(true)
    expect(
      validStrategy(
        rebaseVertex({ transform: 'fork_from_archive', rebase_extension: ext({ strategy: 'fork_from_archived_parent' }) }),
      ),
    ).toBe(true)
  })

  it('A1: a transform/strategy mismatch passed every conjunct 9.2 originally listed', () => {
    const mismatched = rebaseVertex({ transform: 'fork_from_archive' }) // strategy stays reparent_*
    // Everything the spec's admission conjunction actually checks:
    expect(validTuple(mismatched)).toBe(true)
    expect(proofReferencesPresent(mismatched)).toBe(true)
    // ...and the predicate the spec defines but never consults:
    expect(validStrategy(mismatched)).toBe(false)
    // Amendment A1 makes consulting it normative, so the vertex is refused.
    expect(admissionFailures(mismatched, ledger(), SNAPSHOT)).toEqual(['invalid_strategy'])
  })
})

describe('section 10.4 / A6 — proof reference presence', () => {
  it('requires the equivalence hash under pure relocation', () => {
    expect(proofReferencesPresent(rebaseVertex())).toBe(true)
    expect(
      proofReferencesPresent(rebaseVertex({ rebase_extension: ext({ proofs: proofs({ equivalence_proof_hash: null }) }) })),
    ).toBe(false)
  })

  it('requires the adaptation hash under state adaptation, and does not accept the other one', () => {
    const adapting = ext({ mode: 'state_adaptation', proofs: proofs({ adaptation_proof_hash: h('7') }) })
    expect(proofReferencesPresent(rebaseVertex({ rebase_extension: adapting }))).toBe(true)
    // equivalence hash present, adaptation hash absent: the wrong obligation is not a substitute
    expect(proofReferencesPresent(rebaseVertex({ rebase_extension: ext({ mode: 'state_adaptation' }) }))).toBe(false)
  })

  it('requires the verification key and circuit hashes to be well formed', () => {
    expect(
      proofReferencesPresent(rebaseVertex({ rebase_extension: ext({ proofs: proofs({ verification_key_hash: 'nope' }) }) })),
    ).toBe(false)
  })

  it('a present proof hash asserts a declared obligation, never a verified one', () => {
    // The hash is arbitrary; nothing here verifies pi. Documented, and pinned so
    // no reader mistakes ValidProofs for proof checking.
    const bogus = ext({ proofs: proofs({ equivalence_proof_hash: h('f') }) })
    expect(proofReferencesPresent(rebaseVertex({ rebase_extension: bogus }))).toBe(true)
  })
})

describe('section 9.2 — admission', () => {
  it('admits a vertex satisfying every assertion', () => {
    expect(isAdmissible(normalVertex(), ledger(), SNAPSHOT)).toBe(true)
    expect(isAdmissible(rebaseVertex(), ledger(), SNAPSHOT)).toBe(true)
  })

  it('reports every independent failure rather than the first', () => {
    const failures = admissionFailures(
      rebaseVertex({ causal_tuple: [PARENT, h('9'), DECISION] }),
      ledger({ breaker_tripped: true, active_count: HOT_GRAPH_CAPACITY, known_ids: ['v1'] }),
      h('0'),
    )
    expect(failures).toEqual([
      'breaker_tripped',
      'capacity_exhausted',
      'duplicate_id',
      'policy_snapshot_mismatch',
      'invalid_tuple',
    ])
  })

  it('fails closed on a stale policy snapshot', () => {
    expect(admissionFailures(normalVertex(), ledger(), h('9'))).toEqual(['policy_snapshot_mismatch'])
  })

  it('is deterministic across repeated evaluation', () => {
    const v = rebaseVertex()
    const runs = [0, 1, 2].map(() => JSON.stringify(admissionFailures(v, ledger(), SNAPSHOT)))
    expect(new Set(runs).size).toBe(1)
  })
})
