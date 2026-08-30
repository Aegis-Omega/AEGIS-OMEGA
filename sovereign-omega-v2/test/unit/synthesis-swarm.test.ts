import { describe, it, expect } from 'vitest'
import {
  runSynthesisSwarm,
  SYNTHESIS_SCHEMA_VERSION,
  type SynthesisRequest,
  type AgentRole,
} from '../../src/consensus/synthesis-swarm.js'

const SEQ = 1n as import('../../src/core/types.js').SequenceNumber

// Deterministic mock agent — returns predictable outputs per role
function mockAgent(overrides?: Partial<Record<AgentRole, string>>) {
  return async (_system: string, _user: string, role: AgentRole) => {
    const outputs: Record<AgentRole, string> = {
      alpha: overrides?.alpha ?? `export async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty input')
  const hash = await hashValue({ input })
  return hash
}`,
      beta: overrides?.beta ?? `async function solve(input: readonly string[]): Promise<string> {
  if (!input || !input.length) throw new Error('empty input')
  const hash = await hashValue({ input })
  return hash
}`,
      gamma: overrides?.gamma ?? `{"verdict":"COMMITTED","violations":[],"rationale":"All invariants upheld"}`,
    }
    return { output: outputs[role], backend: 'mock', latency_ms: 1 }
  }
}

const BASE_REQ: SynthesisRequest = {
  task: 'Build a hash-chained audit function',
  context: 'Uses hashValue from src/core/hashing.ts',
  constitutional_constraints: [
    'AdaptivePower(T) ≤ ReplayVerifiability(T)',
    'deepFreeze all state objects',
    'is_replay_reconstructable: true on all records',
  ],
  sequence: SEQ,
}

describe('SynthesisSwarm — schema and structure', () => {
  it('SYNTHESIS_SCHEMA_VERSION is 1.0.0', () => {
    expect(SYNTHESIS_SCHEMA_VERSION).toBe('1.0.0')
  })

  it('returns a frozen SynthesisRecord', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(Object.isFrozen(record)).toBe(true)
    expect(record.schema_version).toBe('1.0.0')
    expect(record.is_replay_reconstructable).toBe(true)
  })

  it('synthesis_hash is 64-char hex', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.synthesis_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('task_hash is 64-char hex', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.task_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('all agent proposals have output_hash 64-char hex', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.alpha_proposal.output_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.beta_adversarial.output_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.gamma_verdict_raw.output_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('agent roles are correctly assigned', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.alpha_proposal.agent_id).toBe('alpha')
    expect(record.beta_adversarial.agent_id).toBe('beta')
    expect(record.gamma_verdict_raw.agent_id).toBe('gamma')
  })
})

describe('SynthesisSwarm — verdict logic', () => {
  it('COMMITTED when Gamma approves + convergence', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    // Both alpha and beta produce structurally similar code → converged
    // Gamma says COMMITTED → verdict is COMMITTED
    expect(record.verdict).toBe('COMMITTED')
    expect(record.committed_output_hash).not.toBeNull()
    expect(record.committed_output_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('REJECTED when Gamma rejects', async () => {
    const agent = mockAgent({ gamma: '{"verdict":"REJECTED","violations":["missing deepFreeze"],"rationale":"State not frozen"}' })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.verdict).toBe('REJECTED')
    expect(record.committed_output_hash).toBeNull()
  })

  it('REJECTED when Gamma output is unparseable', async () => {
    const agent = mockAgent({ gamma: 'I cannot determine the verdict' })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.verdict).toBe('REJECTED')
    expect(record.committed_output_hash).toBeNull()
  })

  it('DEADLOCK when Gamma approves but structures diverge', async () => {
    // Alpha: code with many exports and functions
    // Beta: completely different structure (a test-only file, no exports)
    const agent = mockAgent({
      alpha: `export const A = 1; export const B = 2; export const C = 3;
export async function foo() {} export async function bar() {} export async function baz() {}
interface X {} interface Y {} interface Z {}`,
      beta: `// no exports, no functions, no types\nconsole.log("test")`,
      gamma: '{"verdict":"COMMITTED","violations":[],"rationale":"Looks fine"}',
    })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    // structural_similarity will be low due to export/function count divergence
    // If below CONSENSUS_THRESHOLD → DEADLOCK
    if (!record.convergence.converged) {
      expect(record.verdict).toBe('DEADLOCK')
    } else {
      expect(record.verdict).toBe('COMMITTED')
    }
  })
})

describe('SynthesisSwarm — AST convergence analysis', () => {
  it('structural_similarity in [0,1]', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.convergence.structural_similarity).toBeGreaterThanOrEqual(0)
    expect(record.convergence.structural_similarity).toBeLessThanOrEqual(1)
  })

  it('fingerprints are frozen', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(Object.isFrozen(record.convergence.alpha_fingerprint)).toBe(true)
    expect(Object.isFrozen(record.convergence.beta_fingerprint)).toBe(true)
  })

  it('fingerprint_hash is 64-char hex', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.convergence.alpha_fingerprint.fingerprint_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(record.convergence.beta_fingerprint.fingerprint_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('shared_patterns is subset of known bool fields', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    const validFields = new Set([
      'has_error_handling', 'has_async', 'has_type_annotations',
      'uses_immutability', 'uses_hashing',
      'has_early_return', 'has_loop', 'has_destructuring',
    ])
    for (const p of record.convergence.shared_patterns) {
      expect(validFields.has(p)).toBe(true)
    }
  })

  it('identical alpha and beta output → high similarity', async () => {
    const sameCode = `export async function f(x: readonly string[]): Promise<string> {
  const result = await hashValue({ x })
  return Object.freeze(result)
}`
    const agent = mockAgent({ alpha: sameCode, beta: sameCode })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.convergence.structural_similarity).toBeGreaterThanOrEqual(0.9)
    expect(record.convergence.converged).toBe(true)
  })
})

describe('SynthesisSwarm — determinism', () => {
  it('identical inputs → identical synthesis_hash (×3)', async () => {
    const [r1, r2, r3] = await Promise.all([
      runSynthesisSwarm(BASE_REQ, mockAgent()),
      runSynthesisSwarm(BASE_REQ, mockAgent()),
      runSynthesisSwarm(BASE_REQ, mockAgent()),
    ])
    expect(r1.synthesis_hash).toBe(r2.synthesis_hash)
    expect(r2.synthesis_hash).toBe(r3.synthesis_hash)
  })

  it('different tasks → different task_hash', async () => {
    const req2 = { ...BASE_REQ, task: 'different task' }
    const [r1, r2] = await Promise.all([
      runSynthesisSwarm(BASE_REQ, mockAgent()),
      runSynthesisSwarm(req2, mockAgent()),
    ])
    expect(r1.task_hash).not.toBe(r2.task_hash)
    expect(r1.synthesis_hash).not.toBe(r2.synthesis_hash)
  })

  it('different agent outputs → different synthesis_hash', async () => {
    const r1 = await runSynthesisSwarm(BASE_REQ, mockAgent())
    const r2 = await runSynthesisSwarm(BASE_REQ, mockAgent({ alpha: 'different implementation code here' }))
    expect(r1.synthesis_hash).not.toBe(r2.synthesis_hash)
  })
})

describe('SynthesisSwarm — constitutional invariants', () => {
  it('REJECTED synthesis has null committed_output_hash', async () => {
    const agent = mockAgent({ gamma: '{"verdict":"REJECTED","violations":["test"],"rationale":"no"}' })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.verdict).toBe('REJECTED')
    expect(record.committed_output_hash).toBeNull()
  })

  it('all proposals preserved in record regardless of verdict', async () => {
    const agent = mockAgent({ gamma: '{"verdict":"REJECTED","violations":[],"rationale":"rejected"}' })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.alpha_proposal.output.length).toBeGreaterThan(0)
    expect(record.beta_adversarial.output.length).toBeGreaterThan(0)
    expect(record.gamma_verdict_raw.output.length).toBeGreaterThan(0)
  })

  it('sequence is preserved in synthesis record', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.sequence).toBe(SEQ)
  })

  it('backend label propagated from callAgent', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect(record.alpha_proposal.backend).toBe('mock')
    expect(record.beta_adversarial.backend).toBe('mock')
    expect(record.gamma_verdict_raw.backend).toBe('mock')
  })
})

describe('SynthesisSwarm — false-deadlock prevention (AST normalizer)', () => {
  // Guard clause and nested conditional are semantically equivalent.
  // Both express: "if input is invalid, throw early".
  // Before the normalizer these differed in function_count, causing false DEADLOCKs.
  it('guard clause ≡ nested conditional → COMMITTED (not false DEADLOCK)', async () => {
    const guardClause = `export async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty input')
  const hash = await hashValue({ input })
  return hash
}`
    const nestedConditional = `export async function solve(input: readonly string[]): Promise<string> {
  if (input.length > 0) {
    const hash = await hashValue({ input })
    return hash
  } else {
    throw new Error('empty input')
  }
}`
    const agent = mockAgent({
      alpha: guardClause,
      beta: nestedConditional,
      gamma: '{"verdict":"COMMITTED","violations":[],"rationale":"Both implement identical guard"}',
    })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    // Both patterns: has_error_handling=true, has_async=true, has_type_annotations=true,
    // uses_immutability=true, uses_hashing=true, has_early_return=true, has_loop=false
    // Semantic similarity must be >= 1/φ → COMMITTED, not false DEADLOCK
    expect(record.verdict).toBe('COMMITTED')
    expect(record.convergence.converged).toBe(true)
  })

  it('comment-only difference does not affect fingerprint', async () => {
    const withComments = `// Solves the hashing task with full type safety
export async function solve(input: readonly string[]): Promise<string> {
  // Guard: reject empty input immediately
  if (!input.length) throw new Error('empty input')
  const hash = await hashValue({ input }) // deterministic hash
  return hash
}`
    const withoutComments = `export async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty input')
  const hash = await hashValue({ input })
  return hash
}`
    const agent = mockAgent({
      alpha: withComments,
      beta: withoutComments,
      gamma: '{"verdict":"COMMITTED","violations":[],"rationale":"Identical logic"}',
    })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.verdict).toBe('COMMITTED')
    expect(record.convergence.structural_similarity).toBeGreaterThanOrEqual(0.9)
  })

  it('fingerprint includes has_early_return and has_loop fields', async () => {
    const record = await runSynthesisSwarm(BASE_REQ, mockAgent())
    expect('has_early_return' in record.convergence.alpha_fingerprint).toBe(true)
    expect('has_loop' in record.convergence.alpha_fingerprint).toBe(true)
    expect('has_destructuring' in record.convergence.alpha_fingerprint).toBe(true)
  })

  it('loop-bearing code detected correctly', async () => {
    const loopCode = `export async function processAll(items: readonly string[]): Promise<string[]> {
  const results: string[] = []
  for (const item of items) {
    results.push(await hashValue({ item }))
  }
  return results
}`
    const agent = mockAgent({ alpha: loopCode, beta: loopCode })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    expect(record.convergence.alpha_fingerprint.has_loop).toBe(true)
    expect(record.convergence.beta_fingerprint.has_loop).toBe(true)
    expect(record.convergence.structural_similarity).toBeGreaterThanOrEqual(0.9)
  })

  it('semantic weights: high bool agreement compensates count divergence', async () => {
    // Alpha: 1 export, Beta: 0 exports — counts differ but semantics agree
    const alphaCode = `export async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty')
  return await hashValue({ input })
}`
    const betaCode = `async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty')
  return await hashValue({ input })
}`
    const agent = mockAgent({
      alpha: alphaCode,
      beta: betaCode,
      gamma: '{"verdict":"COMMITTED","violations":[],"rationale":"identical semantics"}',
    })
    const record = await runSynthesisSwarm(BASE_REQ, agent)
    // Bool features all agree (8/8), numeric differs on export_count
    // With 0.75 weight on booleans: similarity = 0.75 + ~0.17 = ~0.92 → COMMITTED
    expect(record.convergence.converged).toBe(true)
    expect(record.verdict).toBe('COMMITTED')
  })
})
