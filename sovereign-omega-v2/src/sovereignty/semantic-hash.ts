/**
 * Semantic commit hash — sections 5.2 to 5.4 of the AEGIS OMEGA formal
 * reconstruction.
 *
 * EPISTEMIC TIER: T0 for the construction (RFC 8785 + SHA-256 are mechanically
 * determined); T2 for the claim that this pre-image is the right one to bind.
 *
 *   Hash_sem(v) = "sha256:" || Hex(SHA-256(f_JCS(P_v)))
 *   V_hash(v)   = 1 iff h_v = Hash_sem(v)
 *
 * The signature is excluded from P_v (section 5.2). Including it would make the
 * hash depend on a value computed over the hash.
 *
 * WHY THIS IS A SEPARATE MODULE. `admissionFailures` is a pure synchronous
 * decision function; `sha256Hex` is async. Rather than make admission async and
 * drag I/O into a decision path, the hash is computed here and its OUTCOME is
 * passed into admission as a boolean the caller must supply. Same separation as
 * verification in `authorization-inversion.ts`: computing and deciding stay
 * apart.
 */

import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { CommitVertex } from './commit-admission.js'

/** Section 1.3. Hybrid logical clock: (logical, counter, node). */
export interface HybridLogicalClock {
  readonly logical: number
  readonly counter: number
  readonly node: string
}

/**
 * A vertex carrying every field section 5.2 binds into the pre-image, plus the
 * hash it claims. `CommitVertex` alone is not enough to hash — admission needs
 * fewer fields than integrity does.
 */
export interface SemanticVertex extends CommitVertex {
  /** The hash this vertex asserts for itself. Checked, never trusted. */
  readonly semantic_hash: string
  readonly hlc: HybridLogicalClock
  readonly authority_delta: string | null
  readonly policy_delta: string | null
  readonly rollback_digest: string | null
  readonly root9: number
}

/**
 * Section 5.2. Every key is present; absent values serialize as explicit null
 * rather than being omitted, so two vertices differing only in which field is
 * missing cannot collide.
 *
 * The `?? null` coercions are what make that true. JCS follows JSON in dropping
 * a key whose value is `undefined`, and the types here do not stop `undefined`
 * arriving at runtime — a wire vertex that omits `policy_delta` yields
 * `undefined` on read. Without the coercion that vertex drops the key and hashes
 * differently from an otherwise identical one carrying `"policy_delta": null`,
 * even though the two documents mean the same thing. The bug is divergence
 * between equivalent inputs, not collision between distinct ones.
 */
export function semanticPreImage(v: SemanticVertex): Record<string, unknown> {
  return {
    id: v.id,
    parent: v.parent,
    causal_tuple: [
      v.causal_tuple[0] ?? null,
      v.causal_tuple[1] ?? null,
      v.causal_tuple[2] ?? null,
    ],
    transform: v.transform,
    hlc: { logical: v.hlc.logical, counter: v.hlc.counter, node: v.hlc.node },
    authority_delta: v.authority_delta ?? null,
    policy_delta: v.policy_delta ?? null,
    rollback_digest: v.rollback_digest ?? null,
    root9: v.root9,
    rebase_extension: v.rebase_extension ?? null,
  }
}

/** Section 5.3. */
export async function semanticHash(v: SemanticVertex): Promise<string> {
  const digest = await sha256Hex(canonicalizeJCS(semanticPreImage(v)))
  return `sha256:${digest}`
}

/**
 * Section 5.4. Recomputes and compares; it does not read `semantic_hash` as
 * evidence of anything.
 */
export async function verifySemanticHash(v: SemanticVertex): Promise<boolean> {
  return v.semantic_hash === (await semanticHash(v))
}
