// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional mapping:
//   primitive_mapping: HASH      — grace_hash chains every fault recovery event
//   replay_mapping:    LOCK      — Grace Loop IS the LOCK boundary after fault detection
//   topology_mapping:  DFA       — state machine: HEALTHY → FAULTED → RECOVERING → HEALTHY
//
// GraceSupervisor — fault-tolerant execution wrapper around MultiverseRegistry.
//
// Constitutional translation of the Self-Healing Runtime Grace Loop:
//   "Trap Interception"    → catch(MultiverseError | AdaptiveLineageError)
//   "Cell Quarantine"      → faulted operation not committed (immutable pattern guarantees this)
//   "State Reversion"      → pre-fault MultiverseRegistry snapshot retained automatically
//   "Restitution Phase"    → GraceEvent frozen record commits fault to audit chain
//   "Telemetry log"        → grace_chain_hash in GraceCertificate
//
// Dual-memory model from the Wasm spec:
//   memory 0 (durable)  → AdaptiveLineage (hash-chained, never discarded)
//   memory 1 (volatile) → working state NOT committed on fault (immutable pattern)
//
// Because MultiverseRegistry uses the immutable pattern throughout, "state reversion"
// is free: if an operation throws, the caller retains the pre-fault registry.
// GraceSupervisor makes this explicit and auditable.

import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import { MultiverseRegistry, MultiverseError } from './multiverse.js'
import { AdaptiveLineageError } from '../frame/adaptive-lineage.js'

export const GRACE_SCHEMA_VERSION = '1.0.0' as const

export type FaultClass =
  | 'ECOLOGY_OVERFLOW'      // MAX_UNIVERSES exceeded
  | 'DUPLICATE_UNIVERSE'    // universe_id already registered
  | 'SEQUENCE_VIOLATION'    // non-monotone sequence
  | 'GENERATION_SATURATED'  // BoundedGeneration reached ⊥

export interface GraceEvent {
  readonly fault_class:          FaultClass
  readonly faulted_universe_id:  string
  readonly pre_fault_node_count: number      // universeCount at time of fault
  readonly grace_hash:           SHA256Hex   // hashValue({fault_class, faulted_universe_id, pre_fault_node_count, sequence})
  readonly sequence:             SequenceNumber
  readonly schema_version:       typeof GRACE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface GraceCertificate {
  readonly grace_event_count:  number
  readonly fault_class_counts: Readonly<Record<FaultClass, number>>
  readonly grace_chain_hash:   SHA256Hex   // hashValue(all grace_hashes in order + sequence)
  readonly sequence:           SequenceNumber
  readonly schema_version:     typeof GRACE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export class GraceError extends Error {
  override readonly name = 'GraceError'
}

function classifyFault(err: unknown): FaultClass {
  /* c8 ignore next -- caller at L108 only passes MultiverseError|AdaptiveLineageError, both extend Error */
  if (err instanceof Error) {
    const msg = err.message
    if (msg.includes('ecology') || msg.includes('MAX_UNIVERSES') || msg.includes('ECOLOGY'))
      return 'ECOLOGY_OVERFLOW'
    if (msg.includes('already') || msg.includes('DUPLICATE') || msg.includes('exists'))
      return 'DUPLICATE_UNIVERSE'
    if (msg.includes('generation') || msg.includes('SATURATED') || msg.includes('saturated'))
      return 'GENERATION_SATURATED'
  }
  return 'SEQUENCE_VIOLATION'
}

export class GraceSupervisor {
  readonly #registry: MultiverseRegistry
  readonly #events:   readonly GraceEvent[]

  private constructor(registry: MultiverseRegistry, events: readonly GraceEvent[]) {
    this.#registry = registry
    this.#events   = events
  }

  static create(registry: MultiverseRegistry): GraceSupervisor {
    return new GraceSupervisor(registry, [])
  }

  get registry(): MultiverseRegistry { return this.#registry }
  get graceEventCount(): number { return this.#events.length }

  // Execute an operation on the current registry.
  // On success: returns new supervisor with updated registry, faulted=false, grace_event=null.
  // On recoverable fault (MultiverseError | AdaptiveLineageError):
  //   records a GraceEvent, retains PRE-FAULT registry, faulted=true.
  // On unclassifiable error: rethrows (unrecoverable).
  async executeWithGrace(
    operation: (registry: MultiverseRegistry) => Promise<{ registry: MultiverseRegistry }>,
    faulted_universe_id: string,
    sequence: SequenceNumber,
  ): Promise<{ supervisor: GraceSupervisor; faulted: boolean; grace_event: GraceEvent | null }> {
    try {
      const result = await operation(this.#registry)
      return {
        supervisor: new GraceSupervisor(result.registry, this.#events),
        faulted:     false,
        grace_event: null,
      }
    } catch (err) {
      if (!(err instanceof MultiverseError) && !(err instanceof AdaptiveLineageError)) {
        throw err  // unrecoverable — propagate up
      }
      const fault_class = classifyFault(err)
      const grace_hash = await hashValue({
        fault_class,
        faulted_universe_id,
        pre_fault_node_count: this.#registry.universeCount,
        sequence: sequence.toString(),
      }) as SHA256Hex

      const event = deepFreeze<GraceEvent>({
        fault_class,
        faulted_universe_id,
        pre_fault_node_count: this.#registry.universeCount,
        grace_hash,
        sequence,
        schema_version:             GRACE_SCHEMA_VERSION,
        is_replay_reconstructable:  true,
      })

      return {
        // Retain pre-fault registry — the immutable pattern makes this zero-cost
        supervisor: new GraceSupervisor(this.#registry, [...this.#events, event]),
        faulted:     true,
        grace_event: event,
      }
    }
  }

  getGraceEvents(): readonly GraceEvent[] { return this.#events }

  async certify(sequence: SequenceNumber): Promise<GraceCertificate> {
    const counts: Record<FaultClass, number> = {
      ECOLOGY_OVERFLOW:    0,
      DUPLICATE_UNIVERSE:  0,
      SEQUENCE_VIOLATION:  0,
      GENERATION_SATURATED: 0,
    }
    for (const e of this.#events) counts[e.fault_class]++

    const grace_chain_hash = await hashValue({
      grace_hashes: this.#events.map(e => e.grace_hash),
      sequence:     sequence.toString(),
    }) as SHA256Hex

    return deepFreeze<GraceCertificate>({
      grace_event_count:  this.#events.length,
      fault_class_counts: Object.freeze(counts),
      grace_chain_hash,
      sequence,
      schema_version:            GRACE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }
}
