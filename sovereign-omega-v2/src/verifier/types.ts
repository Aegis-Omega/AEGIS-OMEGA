// ============================================================
// SOVEREIGN OMEGA — Verifier Type Contracts
// EPISTEMIC TIER: T0
// PRIMITIVE 5: Hard Trust Partitioning
// ============================================================

import type { CalibrationDomain, VerifierClass, SHA256Hex } from '../core/types.js'

export interface VerifierDefinition {
  readonly verifier_id: string
  readonly verifier_class: VerifierClass
  readonly trust_class: CalibrationDomain
  readonly version: string
  readonly description: string
  readonly max_latency_ms: number        // registration requirement: p95 < 30s
  readonly is_deterministic: boolean     // must be true for V1/V2
}

export interface VerifierInput {
  readonly claim_id: string
  readonly domain: string
  readonly content: unknown
  readonly context?: unknown
}

export interface VerifierOutput {
  readonly verifier_id: string
  readonly claim_id: string
  readonly passed: boolean
  readonly raw_confidence: number | null
  readonly evidence_refs: readonly string[]
  readonly latency_ms: number
  readonly determinism_flag: boolean
  readonly verifier_version: string
  readonly trust_class: CalibrationDomain
  readonly artifact_hash: SHA256Hex
}

export interface Verifier {
  readonly definition: VerifierDefinition
  verify(input: VerifierInput): Promise<VerifierOutput>
}

// ─── Built-in Verifier Implementations ────────────────────

export interface SchemaVerifierConfig {
  readonly schema: object
  readonly strict: boolean
}

export interface ExecutionVerifierConfig {
  readonly timeout_ms: number
  readonly sandbox_type: 'node-vm' | 'iframe' | 'worker'
}
