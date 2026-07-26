/**
 * Pins the mechanically decidable fragment of the AEGIS OMEGA formal
 * reconstruction, and pins the four spec defects found while implementing it
 * so they cannot be reintroduced by someone reading the spec literally.
 */
import { describe, expect, it } from 'vitest'
import {
  HOT_GRAPH_CAPACITY,
  admissionFailures,
  cgcWeight,
  isAdmissible,
  isSha256Ref,
  root9Enforce,
  validProofs,
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

  it('SPEC GAP: a genesis vertex is unrepresentable — p_v = c_0 must be a real hash', () => {
    // Sections 1.1 and 3.2 give no bottom case for the first vertex, so the
    // root of the DAG cannot satisfy ValidTuple. Recorded, not worked around.
    const genesis = normalVertex({ parent: null, causal_tuple: ['', '', null] })
    expect(validTuple(genesis)).toBe(false)
  })
})

describe('section 10.3 — strategy alignment, and the fail-open it closes', () => {
  it('requires the strategy to match the transform pass', () => {
    expect(validStrategy(rebaseVertex())).toBe(true)
    expect(
      validStrategy(
        rebaseVertex({ transform: 'fork_from_archive', rebase_extension: ext({ strategy: 'fork_from_archived_parent' }) }),
      ),
    ).toBe(true)
  })

  it('SPEC DEFECT: a transform/strategy mismatch passes every conjunct section 9.2 lists', () => {
    const mismatched = rebaseVertex({ transform: 'fork_from_archive' }) // strategy stays reparent_*
    // Everything the spec's admission conjunction actually checks:
    expect(validTuple(mismatched)).toBe(true)
    expect(validProofs(mismatched)).toBe(true)
    // ...and the predicate the spec defines but never consults:
    expect(validStrategy(mismatched)).toBe(false)
    // This module consults it, so the vertex is refused. That is the deviation.
    expect(admissionFailures(mismatched, ledger(), SNAPSHOT)).toEqual(['invalid_strategy'])
  })
})

describe('section 10.4 — proof obligations', () => {
  it('requires the equivalence hash under pure relocation', () => {
    expect(validProofs(rebaseVertex())).toBe(true)
    expect(
      validProofs(rebaseVertex({ rebase_extension: ext({ proofs: proofs({ equivalence_proof_hash: null }) }) })),
    ).toBe(false)
  })

  it('requires the adaptation hash under state adaptation, and does not accept the other one', () => {
    const adapting = ext({ mode: 'state_adaptation', proofs: proofs({ adaptation_proof_hash: h('7') }) })
    expect(validProofs(rebaseVertex({ rebase_extension: adapting }))).toBe(true)
    // equivalence hash present, adaptation hash absent: the wrong obligation is not a substitute
    expect(validProofs(rebaseVertex({ rebase_extension: ext({ mode: 'state_adaptation' }) }))).toBe(false)
  })

  it('requires the verification key and circuit hashes to be well formed', () => {
    expect(
      validProofs(rebaseVertex({ rebase_extension: ext({ proofs: proofs({ verification_key_hash: 'nope' }) }) })),
    ).toBe(false)
  })

  it('a present proof hash asserts a declared obligation, never a verified one', () => {
    // The hash is arbitrary; nothing here verifies pi. Documented, and pinned so
    // no reader mistakes ValidProofs for proof checking.
    const bogus = ext({ proofs: proofs({ equivalence_proof_hash: h('f') }) })
    expect(validProofs(rebaseVertex({ rebase_extension: bogus }))).toBe(true)
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
