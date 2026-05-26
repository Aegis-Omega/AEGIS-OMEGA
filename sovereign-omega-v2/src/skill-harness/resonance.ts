// ============================================================
// Skill Harness — Resonance Gate
// EPISTEMIC TIER: T1 (invariants proven) / T2 (application)
//
// Every character (agent) at position x in the swarm must be
// in resonance before their skill propagates. Constitutional law:
//   AdaptivePower(T) ≤ ReplayVerifiability(T)
// maps onto every skill as:
//   failure_rate < 1/φ          (phi_convergent)
//   domain_affinity palindrome  (ring_valid)
//   has validated evidence      (sequence_monotone)
//   name.length has triadic dr  (vortex_triadic)
//
// resonance_coefficient = depth × vortex_factor × phi_headroom
// > 5.0 → certified (T1 proof that the skill is constitutionally sound)
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import type { SkillRecord } from './types.js'

export const PHI_THRESHOLD = 0.6180339887498948  // 1/φ — same as swarm + martingale
export const RESONANCE_CERT_THRESHOLD = 5.0      // coefficient above this = certified

export interface SkillResonanceReport {
  readonly is_resonant: boolean          // phi_convergent AND ring_valid AND sequence_monotone
  readonly is_certified: boolean         // resonance_coefficient > 5.0
  readonly phi_convergent: boolean       // failure_rate < 1/φ
  readonly ring_valid: boolean           // domain_affinity is palindrome (A-B-C-B'-A')
  readonly sequence_monotone: boolean    // has validated evidence
  readonly vortex_triadic: boolean       // digital_root(name.length) ∈ {3,6,9}
  readonly resonance_depth: number       // 0..4: count of satisfied conditions
  readonly resonance_coefficient: number // depth × vortex_factor × phi_headroom
  readonly phi_headroom: number          // PHI_THRESHOLD - failure_rate
}

function digitalRoot(n: number): number {
  if (n === 0) return 9
  const r = n % 9
  return r === 0 ? 9 : r
}

function isPalindrome(arr: readonly string[]): boolean {
  if (arr.length === 0) return false
  const n = arr.length
  for (let i = 0; i < Math.floor(n / 2); i++) {
    if (arr[i] !== arr[n - 1 - i]) return false
  }
  return true
}

// Check whether a SkillRecord is in constitutional resonance.
// Pure function — same skill → same report every call.
// "Every position of a character (x) must be in resonance."
export function checkSkillResonance(skill: SkillRecord): SkillResonanceReport {
  const phi_headroom = PHI_THRESHOLD - skill.failure_rate
  const phi_convergent = phi_headroom > 0

  // Ring law: domain_affinity must be a palindrome (A-B-C-B'-A')
  const ring_valid = isPalindrome(skill.domain_affinity)

  // Sequence monotone: skill carries at least one validated run or evidence ref
  const sequence_monotone = skill.validated_runs > 0 || skill.evidence_refs.length > 0

  // Vortex: digital root of name character count determines triadic/hexadic family
  const dr = digitalRoot(skill.name.length)
  const vortex_triadic = dr === 3 || dr === 6 || dr === 9

  const resonance_depth =
    (phi_convergent ? 1 : 0) +
    (ring_valid ? 1 : 0) +
    (sequence_monotone ? 1 : 0) +
    (vortex_triadic ? 1 : 0)

  const vortex_factor = vortex_triadic ? 3.0 : 1.0
  const headroom_clamped = Math.max(phi_headroom, 0)
  const resonance_coefficient = resonance_depth * vortex_factor * headroom_clamped

  const is_resonant = phi_convergent && ring_valid && sequence_monotone
  const is_certified = resonance_coefficient > RESONANCE_CERT_THRESHOLD

  return deepFreeze({
    is_resonant,
    is_certified,
    phi_convergent,
    ring_valid,
    sequence_monotone,
    vortex_triadic,
    resonance_depth,
    resonance_coefficient,
    phi_headroom,
  })
}

export class SkillResonanceError extends Error {
  override readonly name = 'SkillResonanceError'
}

// Throws SkillResonanceError if the skill is not resonant.
// Call before admitting any skill to the catalog or swarm.
export function requireResonant(skill: SkillRecord): void {
  const report = checkSkillResonance(skill)
  if (!report.is_resonant) {
    throw new SkillResonanceError(
      `[RESONANCE_BREACH] skill '${skill.skill_id}' not resonant — ` +
      `phi_convergent=${report.phi_convergent} ring_valid=${report.ring_valid} ` +
      `sequence_monotone=${report.sequence_monotone} depth=${report.resonance_depth}`
    )
  }
}
