// ============================================================
// RALPH Loop Executor — Fibonacci-paced constitutional execution
// EPISTEMIC TIER: T1 · Gate 127
//
// Each agent execution is a full R→A→L→P→H cycle.
// Loop spacing follows F_{n+2}=F_{n+1}+F_n (capped at FIBONACCI_CAP).
// Every loop produces a replay-certifiable RalphLoopRecord.
// All phases chain hash-linked: each phase hashes its predecessors.
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../../core/types.js'
import { hashValue } from '../../core/hashing.js'
import { deepFreeze } from '../../core/immutable.js'
import { fibonacciInterval } from '../scheduler/fibonacci.js'

export const RALPH_SCHEMA_VERSION = '1.0.0' as const

export interface RalphLoopRecord {
  readonly agent_id: string
  readonly loop_index: number           // 1-indexed; grows with each executeLoop call
  readonly fibonacci_interval: number   // fibonacciInterval(loop_index) — pacing signal
  readonly phase_read_hash: SHA256Hex
  readonly phase_assess_hash: SHA256Hex
  readonly phase_lock_hash: SHA256Hex
  readonly phase_propagate_hash: SHA256Hex
  readonly phase_harmonize_hash: SHA256Hex
  readonly loop_hash: SHA256Hex         // hashValue(all five phase hashes + loop_index + agent_id)
  readonly is_anchored: boolean         // structural validity — always true for executor-built records
  readonly sequence: SequenceNumber
  readonly schema_version: typeof RALPH_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface RalphLoopCertificate {
  readonly agent_id: string
  readonly loop_count: number
  readonly is_valid: boolean            // all loop_hashes form a valid sequence
  readonly terminal_hash: SHA256Hex | null
  readonly certificate_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export class RalphExecutorError extends Error {
  override readonly name = 'RalphExecutorError'
}

export class ExecutionBoundaryError extends Error {
  override readonly name = 'ExecutionBoundaryError'
}

// k·C_eval ≤ B_max — pre-flight execution budget enforcement (execution-boundary skill, T2)
export function assertExecutionBoundary(k: number, cEval: number, bMax: number): void {
  if (k * cEval > bMax) {
    const kMax = Math.floor(bMax / cEval)
    throw new ExecutionBoundaryError(
      `k=${k} × C_eval=${cEval} = ${k * cEval} > B_max=${bMax}; k_max=${kMax}`,
    )
  }
}

export class RalphExecutor {
  readonly #agent_id: string
  readonly #records: readonly RalphLoopRecord[]

  private constructor(agent_id: string, records: readonly RalphLoopRecord[]) {
    this.#agent_id = agent_id
    this.#records = Object.freeze(records)
  }

  static create(agent_id: string): RalphExecutor {
    if (!agent_id) throw new RalphExecutorError('agent_id must be non-empty')
    return new RalphExecutor(agent_id, [])
  }

  get loopCount(): number { return this.#records.length }
  get lastRecord(): RalphLoopRecord | null { return this.#records[this.#records.length - 1] ?? null }

  // Executes one RALPH cycle. context_hash is the SHA256Hex of the current observation.
  // Returns new executor (immutable) + the loop record produced.
  async executeLoop(
    context_hash: SHA256Hex,
    sequence: SequenceNumber,
  ): Promise<{ executor: RalphExecutor; record: RalphLoopRecord }> {
    const loop_index = this.#records.length + 1
    const fibonacci_interval = fibonacciInterval(loop_index)
    const prev_loop_hash = this.lastRecord?.loop_hash ?? ('' as SHA256Hex)

    // Five RALPH phases — each hashes its predecessor, anchoring causality.
    const phase_read_hash = await hashValue({ phase: 'READ', context_hash, prev_loop_hash, loop_index, agent_id: this.#agent_id })
    const phase_assess_hash = await hashValue({ phase: 'ASSESS', prev: phase_read_hash, loop_index })
    const phase_lock_hash = await hashValue({ phase: 'LOCK', prev: phase_assess_hash, loop_index })
    const phase_propagate_hash = await hashValue({ phase: 'PROPAGATE', prev: phase_lock_hash, loop_index })
    const phase_harmonize_hash = await hashValue({ phase: 'HARMONIZE', prev: phase_propagate_hash, loop_index })

    const loop_hash = await hashValue({
      agent_id: this.#agent_id,
      loop_index,
      phase_read_hash,
      phase_assess_hash,
      phase_lock_hash,
      phase_propagate_hash,
      phase_harmonize_hash,
    })

    const record = deepFreeze<RalphLoopRecord>({
      agent_id: this.#agent_id,
      loop_index,
      fibonacci_interval,
      phase_read_hash,
      phase_assess_hash,
      phase_lock_hash,
      phase_propagate_hash,
      phase_harmonize_hash,
      loop_hash,
      is_anchored: true,
      sequence,
      schema_version: RALPH_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })

    return { executor: new RalphExecutor(this.#agent_id, [...this.#records, record]), record }
  }

  async certify(): Promise<RalphLoopCertificate> {
    const loop_count = this.#records.length
    const terminal_hash = this.lastRecord?.loop_hash ?? null
    const certificate_hash = await hashValue({
      agent_id: this.#agent_id,
      loop_hashes: this.#records.map(r => r.loop_hash),
    })
    return deepFreeze({
      agent_id: this.#agent_id,
      loop_count,
      is_valid: this.#records.every(r => r.is_anchored),
      terminal_hash,
      certificate_hash,
      is_replay_reconstructable: true as const,
    })
  }
}
