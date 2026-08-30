import { describe, it, expect } from 'vitest'
import {
  buildBranch, SimulationError, SIMULATION_SCHEMA_VERSION, MAX_SIMULATION_DEPTH,
} from '../../src/simulation/types.js'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'

const PARENT = 'c'.repeat(64) as SHA256Hex
const seq = (n: number) => BigInt(n) as SequenceNumber

describe('Simulation constants', () => {
  it('SIMULATION_SCHEMA_VERSION is 1.0.0', () => { expect(SIMULATION_SCHEMA_VERSION).toBe('1.0.0') })
  it('MAX_SIMULATION_DEPTH is 8 (F_6)', () => { expect(MAX_SIMULATION_DEPTH).toBe(8) })
})

describe('buildBranch', () => {
  it('produces frozen SimulationBranch', async () => {
    const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 1, outcome: 'STABLE', sequence: seq(1) })
    expect(Object.isFrozen(b)).toBe(true)
  })

  it('branch_id is 64-char hex', async () => {
    const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 1, outcome: 'STABLE', sequence: seq(1) })
    expect(b.branch_id).toMatch(/^[0-9a-f]{64}$/)
  })

  it('is_replay_reconstructable=true', async () => {
    const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 0, outcome: 'CONVERGENT', sequence: seq(1) })
    expect(b.is_replay_reconstructable).toBe(true)
  })

  it('schema_version=1.0.0', async () => {
    const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 0, outcome: 'STABLE', sequence: seq(1) })
    expect(b.schema_version).toBe('1.0.0')
  })

  it('branch_id is deterministic ×3', async () => {
    const run = () => buildBranch({ parent_topology_hash: PARENT, branch_index: 2, depth: 3, outcome: 'DRIFT', sequence: seq(7) })
    const [b1, b2, b3] = await Promise.all([run(), run(), run()])
    expect(b1.branch_id).toBe(b2.branch_id)
    expect(b2.branch_id).toBe(b3.branch_id)
  })

  it('different branch_index → different branch_id', async () => {
    const b1 = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 1, outcome: 'STABLE', sequence: seq(1) })
    const b2 = await buildBranch({ parent_topology_hash: PARENT, branch_index: 1, depth: 1, outcome: 'STABLE', sequence: seq(1) })
    expect(b1.branch_id).not.toBe(b2.branch_id)
  })

  it('depth at MAX_SIMULATION_DEPTH=8 succeeds', async () => {
    const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: MAX_SIMULATION_DEPTH, outcome: 'DRIFT', sequence: seq(1) })
    expect(b.depth).toBe(8)
  })

  it('depth > MAX_SIMULATION_DEPTH throws SimulationError', async () => {
    await expect(buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 9, outcome: 'STABLE', sequence: seq(1) }))
      .rejects.toBeInstanceOf(SimulationError)
  })

  it('negative depth throws SimulationError', async () => {
    await expect(buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: -1, outcome: 'STABLE', sequence: seq(1) }))
      .rejects.toBeInstanceOf(SimulationError)
  })

  it('all four BranchOutcome values accepted', async () => {
    const outcomes = ['STABLE', 'DRIFT', 'VIOLATION', 'CONVERGENT'] as const
    for (const outcome of outcomes) {
      const b = await buildBranch({ parent_topology_hash: PARENT, branch_index: 0, depth: 1, outcome, sequence: seq(1) })
      expect(b.outcome).toBe(outcome)
    }
  })
})

describe('SimulationError', () => {
  it('is an Error subclass with correct name', () => {
    const err = new SimulationError('test')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('SimulationError')
  })
})
