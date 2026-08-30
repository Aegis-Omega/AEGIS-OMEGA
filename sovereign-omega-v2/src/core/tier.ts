// ============================================================
// SOVEREIGN OMEGA — Epistemic Tier Classification
// EPISTEMIC TIER: T0 (mechanically enforced)
// Tier classification is metadata-driven only.
// No semantic inference. Fail closed on ambiguity.
// ============================================================

export enum EpistemicTier {
  T0 = 0,  // Mechanically proven / deterministic
  T1 = 1,  // Empirically validated
  T2 = 2,  // Engineering hypothesis
  T3 = 3,  // Research conjecture
  T4 = 4,  // Speculative systems vision
  T5 = 5,  // Creative / worldbuilding
}

export interface TierMetadata {
  readonly tier: EpistemicTier
  readonly standard: string
  readonly validation_requirement: string
  readonly promotion_condition: string
  readonly domain_ceiling: string
}

const TIER_DEFINITIONS: Record<EpistemicTier, TierMetadata> = {
  [EpistemicTier.T0]: {
    tier: EpistemicTier.T0,
    standard: 'Mechanically proven or deterministic',
    validation_requirement: 'Formal proof or deterministic test vector',
    promotion_condition: 'N/A — foundational tier',
    domain_ceiling: 'src/core, src/event, src/gate',
  },
  [EpistemicTier.T1]: {
    tier: EpistemicTier.T1,
    standard: 'Empirically validated',
    validation_requirement: 'Reproducible benchmark with defined success criterion',
    promotion_condition: 'Reproducible deployment evidence',
    domain_ceiling: 'src/verifier, src/calibration',
  },
  [EpistemicTier.T2]: {
    tier: EpistemicTier.T2,
    standard: 'Engineering hypothesis',
    validation_requirement: 'Defined measurement criteria',
    promotion_condition: 'Empirical validation across multiple deployments',
    domain_ceiling: 'src/projection, src/pipeline',
  },
  [EpistemicTier.T3]: {
    tier: EpistemicTier.T3,
    standard: 'Research conjecture',
    validation_requirement: 'Falsifiable prediction and experimental protocol',
    promotion_condition: 'Published result with peer review',
    domain_ceiling: 'docs/research',
  },
  [EpistemicTier.T4]: {
    tier: EpistemicTier.T4,
    standard: 'Speculative systems vision',
    validation_requirement: 'None — speculative tier',
    promotion_condition: 'Research conjecture with falsifiable test (→ T3)',
    domain_ceiling: 'docs/vision',
  },
  [EpistemicTier.T5]: {
    tier: EpistemicTier.T5,
    standard: 'Creative / worldbuilding',
    validation_requirement: 'None — creative tier',
    promotion_condition: 'Identification of load-bearing insight (→ T4)',
    domain_ceiling: 'docs/cycles',
  },
}

export function getTierMetadata(tier: EpistemicTier): TierMetadata {
  return TIER_DEFINITIONS[tier]
}

/**
 * Classify a file path to its maximum permitted epistemic tier.
 * Returns T0 for unrecognised paths — fail closed.
 */
export function classifyPathTier(filePath: string): EpistemicTier {
  if (filePath.startsWith('src/core/') || filePath.startsWith('src/event/') || filePath.startsWith('src/gate/')) return EpistemicTier.T0
  if (filePath.startsWith('src/verifier/') || filePath.startsWith('src/calibration/')) return EpistemicTier.T1
  if (filePath.startsWith('src/projection/') || filePath.startsWith('src/pipeline/') || filePath.startsWith('src/compliance/')) return EpistemicTier.T2
  if (filePath.startsWith('docs/research/')) return EpistemicTier.T3
  if (filePath.startsWith('docs/vision/')) return EpistemicTier.T4
  if (filePath.startsWith('docs/cycles/')) return EpistemicTier.T5
  // Fail closed: unrecognised paths get T0 ceiling
  return EpistemicTier.T0
}

/**
 * Assert that a construct's tier does not exceed its deployment context.
 * Throws if the construct tier is higher than the permitted ceiling.
 *
 * MIGRATION RULE: No T4/T5 construct may ground a T0–T2 claim
 * without explicit evidence review.
 */
export function assertTierCompatibility(
  constructTier: EpistemicTier,
  deploymentPath: string,
  constructName: string
): void {
  const ceilingTier = classifyPathTier(deploymentPath)
  if (constructTier > ceilingTier) {
    throw new TierViolationError(
      `Tier violation: '${constructName}' is T${constructTier} but deployment ` +
      `path '${deploymentPath}' has a T${ceilingTier} ceiling. ` +
      `Evidence review required before migration.`
    )
  }
}

export class TierViolationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'TierViolationError'
  }
}
