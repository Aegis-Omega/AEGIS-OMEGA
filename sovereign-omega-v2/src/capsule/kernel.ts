// ============================================================
// SOVEREIGN OMEGA — Constitutional Capsule Kernel
// EPISTEMIC TIER: T2 · Gate 32
//
// Pure deterministic capsule execution engine.
// All functions are side-effect-free; no network, no I/O.
//
// Execution flow (constitutional):
//   1. buildManifest()   — content-addressed manifest
//   2. capabilityGranted() — capability grammar check
//   3. runCapsule()      — entropy evaluation + event commit
//                          → COMMITTED | REJECTED | ROLLED_BACK
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import {
  CAPSULE_SCHEMA_VERSION,
  CapsuleError,
  type CapsuleCapability,
  type CapsuleCapabilityType,
  type CapsuleManifest,
  type CapsuleResult,
} from './types.js'
import { canonicalizeJCS } from '../core/canonicalize.js'

// ─── Manifest builder ──────────────────────────────────────

export interface ManifestInput {
  readonly capabilities: readonly CapsuleCapability[]
  readonly entropy_budget: number
}

/**
 * Build a content-addressed CapsuleManifest.
 * capsule_id = hashValue(canonical manifest payload without capsule_id).
 * Throws CapsuleError if entropy_budget is negative.
 */
export async function buildManifest(input: ManifestInput): Promise<CapsuleManifest> {
  if (input.entropy_budget < 0) {
    throw new CapsuleError(`entropy_budget must be >= 0, got ${input.entropy_budget}`)
  }
  const capsule_id = await hashValue({
    capabilities: input.capabilities,
    entropy_budget: input.entropy_budget,
    is_rollback_safe: true,
    schema_version: CAPSULE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  }) as string
  return deepFreeze<CapsuleManifest>({
    capsule_id,
    capabilities: input.capabilities,
    entropy_budget: input.entropy_budget,
    is_rollback_safe: true,
    schema_version: CAPSULE_SCHEMA_VERSION,
    is_replay_reconstructable: true,
  })
}

// ─── Capability check ──────────────────────────────────────

/**
 * True iff the manifest grants the requested capability type for target.
 * Constitutional note: an empty capabilities array grants nothing.
 */
export function capabilityGranted(
  manifest: CapsuleManifest,
  type: CapsuleCapabilityType,
  target: string,
): boolean {
  return manifest.capabilities.some(c => c.type === type && c.target === target)
}

// ─── Capsule execution ─────────────────────────────────────

export interface CapsuleInput {
  readonly manifest: CapsuleManifest
  readonly capability_type: CapsuleCapabilityType
  readonly target: string
  readonly payload: unknown
  readonly sequence: SequenceNumber
  readonly parent_lineage_hash: SHA256Hex | null
}

/**
 * Execute a capsule deterministically.
 *
 * REJECTED  — capability not granted by manifest
 * ROLLED_BACK — entropy_consumed > manifest.entropy_budget
 * COMMITTED — capability granted and within entropy budget
 *
 * entropy_consumed = canonical byte length of payload.
 * event_hash      = hashValue({capsule_id, capability_type, target, sequence})
 * attestation_hash = hashValue({event_hash, parent_lineage_hash, outcome, sequence})
 */
export async function runCapsule(input: CapsuleInput): Promise<CapsuleResult> {
  const { manifest, capability_type, target, payload, sequence, parent_lineage_hash } = input

  // Step 1 — capability check
  if (!capabilityGranted(manifest, capability_type, target)) {
    const event_hash = await hashValue({ capsule_id: manifest.capsule_id, capability_type, target, sequence })
    const attestation_hash = await hashValue({ event_hash, parent_lineage_hash, outcome: 'REJECTED', sequence })
    return deepFreeze<CapsuleResult>({
      capsule_id: manifest.capsule_id,
      outcome: 'REJECTED',
      entropy_consumed: 0,
      event_hash: event_hash as SHA256Hex,
      attestation_hash: attestation_hash as SHA256Hex,
      sequence,
      reason: `Capability ${capability_type}:${target} not in manifest`,
      is_replay_reconstructable: true,
    })
  }

  // Step 2 — entropy evaluation
  const entropy_consumed = canonicalizeJCS(payload).byteLength

  if (entropy_consumed > manifest.entropy_budget) {
    const event_hash = await hashValue({ capsule_id: manifest.capsule_id, capability_type, target, sequence })
    const attestation_hash = await hashValue({ event_hash, parent_lineage_hash, outcome: 'ROLLED_BACK', sequence })
    return deepFreeze<CapsuleResult>({
      capsule_id: manifest.capsule_id,
      outcome: 'ROLLED_BACK',
      entropy_consumed,
      event_hash: event_hash as SHA256Hex,
      attestation_hash: attestation_hash as SHA256Hex,
      sequence,
      reason: `Entropy ${entropy_consumed}B exceeds budget ${manifest.entropy_budget}B`,
      is_replay_reconstructable: true,
    })
  }

  // Step 3 — event commit
  const event_hash = await hashValue({ capsule_id: manifest.capsule_id, capability_type, target, payload, sequence })
  const attestation_hash = await hashValue({ event_hash, parent_lineage_hash, outcome: 'COMMITTED', sequence })

  return deepFreeze<CapsuleResult>({
    capsule_id: manifest.capsule_id,
    outcome: 'COMMITTED',
    entropy_consumed,
    event_hash: event_hash as SHA256Hex,
    attestation_hash: attestation_hash as SHA256Hex,
    sequence,
    is_replay_reconstructable: true,
  })
}
