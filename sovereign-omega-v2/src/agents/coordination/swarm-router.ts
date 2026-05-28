// ============================================================
// SOVEREIGN OMEGA — Multi-Model Constitutional Swarm Router
// EPISTEMIC TIER: T2 · Gate 199
//
// Distributes tasks across a registry of AI model endpoints
// and applies BFT quorum at 1/φ to determine the authoritative
// response. No single model speaks with authority alone.
//
// Architecture:
//   ModelRegistry (BTreeMap order) → per-model response hashing
//   → SwarmVote per model → tallyVotes() → SwarmRouterResult
//
// Constitutional invariants:
// - No model response is committed without 1/φ quorum
// - Every routing decision is hash-linked and replay-certifiable
// - ModelRegistry uses sorted keys — deterministic iteration
// - HysteresisFilter governs per-model trust (external, injected)
// ============================================================

import type { SHA256Hex, SequenceNumber } from '../../core/types.js'
import { hashValue } from '../../core/hashing.js'
import { deepFreeze } from '../../core/immutable.js'
import {
  tallyVotes,
  DEFAULT_QUORUM_THRESHOLD,
  type SwarmVote,
  type SwarmConvergenceRecord,
} from '../../consensus/swarm.js'

export const SWARM_ROUTER_SCHEMA_VERSION = '1.0.0' as const

// ─── Provider taxonomy ────────────────────────────────────

export type ModelProvider =
  | 'dashscope'   // Alibaba DashScope — Qwen family
  | 'anthropic'   // Anthropic — Claude family
  | 'openai'      // OpenAI-compatible endpoint
  | 'local'       // Local Ollama / llama.cpp endpoint

// ─── Model registry record ────────────────────────────────

export interface ModelEndpoint {
  readonly model_id: string        // e.g. "qwen-plus", "claude-opus-4-7"
  readonly provider: ModelProvider
  readonly endpoint_url: string
  readonly weight: number          // 0–1000 (same scale as HysteresisFilter)
  readonly is_active: boolean
}

// ─── Task — the unit of work dispatched to the swarm ─────

export interface SwarmTask {
  readonly task_id: SHA256Hex         // hashValue({prompt_hash, sequence[, constitution_hash]})
  readonly prompt_hash: SHA256Hex     // hashValue(raw prompt bytes) — not the prompt
  readonly schema_version: typeof SWARM_ROUTER_SCHEMA_VERSION
  readonly sequence: SequenceNumber
  readonly directive_hash?: SHA256Hex // optional: constitution fingerprint at dispatch time
  readonly is_replay_reconstructable: true
}

// ─── Per-model response (caller populates after API call) ─

export interface ModelResponse {
  readonly model_id: string
  readonly response_hash: SHA256Hex  // hashValue(response text)
  readonly task_id: SHA256Hex
  readonly sequence: SequenceNumber
}

// ─── Router output — frozen, hash-linked ─────────────────

export interface SwarmRouterResult {
  readonly task_id: SHA256Hex
  readonly quorum_reached: boolean
  readonly consensus_response_hash: SHA256Hex | null  // null if no quorum
  readonly vote_count: number            // votes cast for winning hash
  readonly total_responses: number       // how many models responded
  readonly quorum_threshold: number      // 1/φ
  readonly convergence: SwarmConvergenceRecord
  readonly result_hash: SHA256Hex
  readonly schema_version: typeof SWARM_ROUTER_SCHEMA_VERSION
  readonly sequence: SequenceNumber
  readonly is_replay_reconstructable: true
}

export class SwarmRouterError extends Error {
  override readonly name = 'SwarmRouterError'
  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

// ─── Model registry ───────────────────────────────────────

export class ModelRegistry {
  // Sorted by model_id — deterministic iteration order
  private readonly _entries: ReadonlyMap<string, ModelEndpoint>

  private constructor(entries: Map<string, ModelEndpoint>) {
    this._entries = entries
  }

  static empty(): ModelRegistry {
    return new ModelRegistry(new Map())
  }

  register(endpoint: ModelEndpoint): ModelRegistry {
    const next = new Map(this._entries)
    next.set(endpoint.model_id, deepFreeze(endpoint))
    // Rebuild as sorted array to preserve deterministic order
    const sorted = new Map(
      [...next.entries()].sort(([a], [b]) => a < b ? -1 : 1),
    )
    return new ModelRegistry(sorted)
  }

  get(model_id: string): ModelEndpoint | undefined {
    return this._entries.get(model_id)
  }

  activeModels(): readonly ModelEndpoint[] {
    return [...this._entries.values()].filter(e => e.is_active)
  }

  get size(): number { return this._entries.size }
}

// ─── Task factory ─────────────────────────────────────────

export async function buildSwarmTask(
  promptBytes: Uint8Array,
  sequence: SequenceNumber,
  constitutionHash?: SHA256Hex,
): Promise<SwarmTask> {
  const prompt_hash = await hashValue({ bytes: Array.from(promptBytes) })
  const task_id = await hashValue({
    prompt_hash,
    sequence: sequence.toString(),
    ...(constitutionHash !== undefined ? { constitution_hash: constitutionHash } : {}),
  })
  return deepFreeze<SwarmTask>({
    task_id,
    prompt_hash,
    schema_version: SWARM_ROUTER_SCHEMA_VERSION,
    sequence,
    ...(constitutionHash !== undefined ? { directive_hash: constitutionHash } : {}),
    is_replay_reconstructable: true,
  })
}

// ─── Core routing function ────────────────────────────────
//
// Takes model responses (already collected by the caller)
// and applies constitutional quorum to select the winner.
//
// The caller is responsible for:
//   1. Dispatching the prompt to each active model endpoint
//   2. Hashing each response: response_hash = hashValue(responseText)
//   3. Passing the array of ModelResponse objects here
//
// This function is pure — no network calls, no side effects.

export async function routeSwarmResponses(
  task: SwarmTask,
  responses: readonly ModelResponse[],
  quorumThreshold: number = DEFAULT_QUORUM_THRESHOLD,
): Promise<SwarmRouterResult> {
  if (responses.length === 0) {
    throw new SwarmRouterError('[SWARM_ROUTER] No responses to route')
  }

  for (const r of responses) {
    if (r.task_id !== task.task_id) {
      throw new SwarmRouterError(
        `[SWARM_ROUTER] Response task_id mismatch: expected ${task.task_id}, got ${r.task_id} from ${r.model_id}`,
      )
    }
    if (r.sequence !== task.sequence) {
      throw new SwarmRouterError(
        `[SWARM_ROUTER] Sequence mismatch from ${r.model_id}: expected ${task.sequence}, got ${r.sequence}`,
      )
    }
  }

  // Each model's response_hash becomes its vote topology_hash.
  // Models that independently produce the same response will produce
  // the same response_hash — that is the quorum signal.
  const votes: SwarmVote[] = responses.map(r => ({
    node_id: r.model_id,
    topology_hash: r.response_hash,
    sequence: task.sequence,
  }))

  const convergence = await tallyVotes(votes, quorumThreshold)

  const consensus_response_hash = convergence.quorum_reached
    ? convergence.quorum_hash
    : null

  const result_hash = await hashValue({
    task_id: task.task_id,
    quorum_reached: convergence.quorum_reached,
    consensus_response_hash: consensus_response_hash ?? 'no-quorum',
    convergence_hash: convergence.convergence_hash,
    sequence: task.sequence.toString(),
  })

  return deepFreeze<SwarmRouterResult>({
    task_id: task.task_id,
    quorum_reached: convergence.quorum_reached,
    consensus_response_hash,
    vote_count: convergence.vote_count,
    total_responses: responses.length,
    quorum_threshold: quorumThreshold,
    convergence,
    result_hash,
    schema_version: SWARM_ROUTER_SCHEMA_VERSION,
    sequence: task.sequence,
    is_replay_reconstructable: true,
  })
}
