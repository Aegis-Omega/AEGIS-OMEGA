// ============================================================
// Skill Harness — 3-Layer Network Resonance Propagation Gate
// EPISTEMIC TIER: T1 (empirically validated network model)
//
// Skill propagation through the swarm requires resonance at
// all three network layers simultaneously:
//
//   LAN (Layer 2-3) — Individual skill resonance at source node
//     gate: checkSkillResonance(skill).is_resonant
//
//   IP  (Layer 3-4) — Routing path resonance via INVERSE DIVERGENCE
//     gate: (1.0 - Σ hop_divergences) > 1/φ
//     key:  inverse_divergence IS the convergence signal.
//           When divergence → 0, convergence → 1 (fully self-referential).
//           Golden identity: 1/φ + 1/φ² = 1
//           Max tolerable path divergence: 1/φ² ≈ 0.382
//
//   WWW (Layer 7)  — Semantic resonance across agent domain spaces
//     gate: |source_domains ∩ target_domains| / |source_unique| ≥ 1/φ
//
// All three gates must pass. This implements:
//   "Every position of a character (x) must be in resonance."
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { checkSkillResonance, PHI_THRESHOLD } from './resonance.js'
import type { SkillRecord } from './types.js'

// PHI_SQ = 1/φ² = 1 - 1/φ ≈ 0.3819660112501051
// Maximum tolerable cumulative path divergence before IP gate blocks.
export const PHI_SQ_THRESHOLD = 1.0 - PHI_THRESHOLD

export interface NetworkResonanceReport {
  readonly lan_resonant: boolean          // source skill resonance (checkSkillResonance)
  readonly ip_resonant: boolean           // inverse_divergence > 1/φ
  readonly www_resonant: boolean          // semantic_alignment ≥ 1/φ
  readonly can_propagate: boolean         // lan AND ip AND www
  readonly inverse_divergence: number     // 1.0 - cumulative_path_divergence
  readonly cumulative_divergence: number  // Σ hop_divergences
  readonly semantic_alignment: number     // overlap ratio [0..1]
  readonly network_depth: number          // 0..3: satisfied layers
  readonly lan_coefficient: number        // source skill resonance_coefficient
}

export class PropagationError extends Error {
  override readonly name = 'PropagationError'
}

// Compute unique domain tags from a domain_affinity palindrome.
// ["a","b","a"] → ["a","b"] — deduplicated preserving first occurrence.
function uniqueDomains(domains: readonly string[]): readonly string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const d of domains) {
    if (!seen.has(d)) {
      seen.add(d)
      result.push(d)
    }
  }
  return result
}

// Check 3-layer network resonance for skill propagation.
//
// skill          — the SkillRecord to propagate (source node)
// hop_divergences — divergence_risk at each routing hop (empty = direct link)
// target_domains  — domain tags of the receiving agent
//
// Throws PropagationError if hop_divergences contains values outside [0,1].
export function checkPropagation(
  skill: SkillRecord,
  hop_divergences: readonly number[],
  target_domains: readonly string[],
): NetworkResonanceReport {
  for (const d of hop_divergences) {
    if (d < 0 || d > 1) {
      throw new PropagationError(
        `[PROPAGATION] hop divergence must be in [0,1], got ${d}`,
      )
    }
  }

  // LAN gate — source node resonance
  const lan_report = checkSkillResonance(skill)
  const lan_resonant = lan_report.is_resonant
  const lan_coefficient = lan_report.resonance_coefficient

  // IP gate — inverse divergence across routing path
  const cumulative_divergence = hop_divergences.reduce((sum, d) => sum + d, 0)
  const inverse_divergence = 1.0 - cumulative_divergence
  const ip_resonant = inverse_divergence > PHI_THRESHOLD

  // WWW gate — semantic alignment (domain affinity overlap)
  const source_unique = uniqueDomains(skill.domain_affinity)
  const target_set = new Set(target_domains)
  const overlap = source_unique.filter(d => target_set.has(d)).length
  const semantic_alignment =
    source_unique.length === 0 ? 0 : overlap / source_unique.length
  const www_resonant = semantic_alignment >= PHI_THRESHOLD

  const network_depth =
    (lan_resonant ? 1 : 0) +
    (ip_resonant ? 1 : 0) +
    (www_resonant ? 1 : 0)

  const can_propagate = lan_resonant && ip_resonant && www_resonant

  return deepFreeze({
    lan_resonant,
    ip_resonant,
    www_resonant,
    can_propagate,
    inverse_divergence,
    cumulative_divergence,
    semantic_alignment,
    network_depth,
    lan_coefficient,
  })
}

// Throws PropagationError if the skill cannot propagate through the given network path.
// Call before routing any skill to an agent position.
export function requirePropagable(
  skill: SkillRecord,
  hop_divergences: readonly number[],
  target_domains: readonly string[],
): void {
  const report = checkPropagation(skill, hop_divergences, target_domains)
  if (!report.can_propagate) {
    throw new PropagationError(
      `[PROPAGATION_BLOCKED] skill '${skill.skill_id}' blocked at ` +
      `lan=${report.lan_resonant} ip=${report.ip_resonant} www=${report.www_resonant} ` +
      `inv_div=${report.inverse_divergence.toFixed(4)} sem=${report.semantic_alignment.toFixed(4)}`,
    )
  }
}
