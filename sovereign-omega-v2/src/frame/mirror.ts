// ============================================================
// SOVEREIGN OMEGA — Governance Mirror Stream
// EPISTEMIC TIER: T1 · Gate 36
//
// Read-only observability surface. Each observe() snapshots a
// GovernanceTopology into a frozen GovernanceObservation without
// mutating state. Enables metacognitive feedback loop.
// primitive_mapping: CANONICALIZE · replay_mapping: PROPAGATE
// topology_mapping: all GovernanceTopology fields
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { SITRState } from '../sitr/types.js'
import type { GlobalState } from '../aoie/types.js'
import type { ConstitutionalVerdict } from '../constitutional/types.js'
import type { GovernanceTopology } from './topology.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const MIRROR_SCHEMA_VERSION = '1.0.0' as const

export interface GovernanceObservation {
  readonly observed_topology_hash: SHA256Hex
  readonly sitr_state: SITRState
  readonly aoie_global_state: GlobalState
  readonly constitutional_verdict: ConstitutionalVerdict
  readonly sequence: SequenceNumber
  readonly observation_hash: SHA256Hex
  readonly schema_version: typeof MIRROR_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class MirrorError extends Error {
  override readonly name = 'MirrorError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

export class MirrorStream {
  private constructor(
    private readonly _entries: readonly GovernanceObservation[],
    private readonly _lastSequence: SequenceNumber | null,
  ) {}

  static empty(): MirrorStream {
    return new MirrorStream([], null)
  }

  get length(): number { return this._entries.length }
  get latestSequence(): SequenceNumber | null { return this._lastSequence }

  async observe(
    topology: GovernanceTopology,
  ): Promise<{ stream: MirrorStream; observation: GovernanceObservation }> {
    if (this._lastSequence !== null && topology.sequence <= this._lastSequence) {
      throw new MirrorError(
        `Non-monotonic sequence: ${topology.sequence} ≤ ${this._lastSequence}`,
      )
    }

    const observation_hash = await hashValue({
      observed_topology_hash: topology.topology_hash,
      sequence: topology.sequence.toString(),
    })

    const observation = deepFreeze<GovernanceObservation>({
      observed_topology_hash: topology.topology_hash,
      sitr_state: topology.sitr_state,
      aoie_global_state: topology.aoie_global_state,
      constitutional_verdict: topology.constitutional_verdict,
      sequence: topology.sequence,
      observation_hash,
      schema_version: MIRROR_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })

    const stream = new MirrorStream(
      Object.freeze([...this._entries, observation]),
      topology.sequence,
    )

    return { stream, observation }
  }

  getAll(): readonly GovernanceObservation[] {
    return this._entries
  }
}
