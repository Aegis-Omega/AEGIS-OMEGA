// ============================================================
// Collapse Extended Tests — memory/collapse.ts
// Targets uncovered throw branches:
//   converged_universe_ids.length === 0 → CollapseError
//   winner_id not found in registry   → CollapseError
// ============================================================

import { describe, it, expect } from 'vitest'
import type { SequenceNumber } from '../../src/core/types.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { collapseMultiverse, CollapseError } from '../../src/memory/collapse.js'
import { MultiverseRegistry, MULTIVERSE_SCHEMA_VERSION } from '../../src/memory/multiverse.js'
import { SWARM_SCHEMA_VERSION } from '../../src/consensus/swarm.js'

const ROOT = 'a0b1c2d3'.repeat(8) as SHA256Hex
const H    = '0'.repeat(64) as SHA256Hex
function seq(n: number): SequenceNumber { return BigInt(n) as SequenceNumber }

function makeSwarmRecord(quorum_reached: boolean, quorum_hash: SHA256Hex = H) {
  return {
    quorum_hash,
    vote_count: 1,
    quorum_reached,
    quorum_threshold: 0.618,
    sequence: seq(1),
    convergence_hash: H,
    schema_version: SWARM_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  }
}

function makeConvergence(universe_ids: readonly string[], quorum_reached = true) {
  return {
    swarm_record: makeSwarmRecord(quorum_reached),
    converged_universe_ids: universe_ids,
    total_universes: universe_ids.length,
    schema_version: MULTIVERSE_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  }
}

// ─── Empty converged_universe_ids → throw ────────────────

describe('collapseMultiverse: empty converged_universe_ids', () => {
  it('throws CollapseError when converged_universe_ids is empty', async () => {
    const registry = MultiverseRegistry.empty()
    const convergence = makeConvergence([])
    await expect(
      collapseMultiverse(registry, convergence, seq(10))
    ).rejects.toThrow(CollapseError)
  })

  it('error message mentions no converged universes', async () => {
    const registry = MultiverseRegistry.empty()
    const convergence = makeConvergence([])
    await expect(
      collapseMultiverse(registry, convergence, seq(10))
    ).rejects.toThrow('no converged universes')
  })
})

// ─── winner_id not found in registry → throw ─────────────

describe('collapseMultiverse: winner not in registry', () => {
  it('throws CollapseError when winner_id is not registered', async () => {
    // Registry has 'existing-universe' but convergence claims 'nonexistent-winner'
    let registry = MultiverseRegistry.empty()
    const r = await registry.fork('existing-universe', ROOT, seq(1))
    registry = r.registry

    const convergence = makeConvergence(['nonexistent-winner'])
    await expect(
      collapseMultiverse(registry, convergence, seq(10))
    ).rejects.toThrow(CollapseError)
  })

  it('error message names the missing winner_id', async () => {
    let registry = MultiverseRegistry.empty()
    const r = await registry.fork('u1', ROOT, seq(1))
    registry = r.registry

    const convergence = makeConvergence(['no-such-universe'])
    await expect(
      collapseMultiverse(registry, convergence, seq(10))
    ).rejects.toThrow("no-such-universe")
  })
})
