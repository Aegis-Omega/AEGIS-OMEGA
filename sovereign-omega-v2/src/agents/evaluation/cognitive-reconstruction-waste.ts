export interface DiscoveryEvent {
  readonly source_commit: string
  readonly artifact_digest: string
  readonly symbol: string
  readonly operation: string
  readonly purpose: string
  readonly tokens_consumed: number
}

export interface HypothesisEvaluationEvent {
  readonly id: string
  readonly is_redundant: boolean
}

export interface VerifiedEffectCount {
  readonly effect_class: string
  readonly count: number
}

export interface CRWWeights {
  readonly w1: number
  readonly w2: number
  readonly w3: number
  readonly w4: number
}

export interface CalculateCRWInput {
  readonly discoveries: readonly DiscoveryEvent[]
  readonly hypotheses: readonly HypothesisEvaluationEvent[]
  readonly total_reasoning_tokens: number
  readonly total_actions: number
  readonly redundant_action_count: number
  readonly verified_effects: readonly VerifiedEffectCount[]
  readonly weights?: CRWWeights
}

export interface CRWMetrics {
  readonly Rd: number
  readonly Rh: number
  readonly Rt: number
  readonly Ra: number
  readonly CRW: number
  readonly tokens_per_verified_effect: Readonly<Record<string, number>>
  readonly actions_per_verified_effect: Readonly<Record<string, number>>
}

const DEFAULT_WEIGHTS: CRWWeights = Object.freeze({ w1: 0.3, w2: 0.2, w3: 0.3, w4: 0.2 })

function assertNonNegativeFinite(name: string, value: number): void {
  if (!Number.isFinite(value) || value < 0) throw new RangeError(`${name} must be finite and non-negative`)
}

function discoveryIdentity(event: DiscoveryEvent): string {
  // Set identity only; not an integrity hash. The five-element tuple is the
  // evaluator's normalization key D=(commit, artifact, symbol, op, purpose).
  return JSON.stringify([
    event.source_commit,
    event.artifact_digest,
    event.symbol,
    event.operation,
    event.purpose,
  ])
}

export class CRWEvaluator {
  public static calculate(input: CalculateCRWInput): CRWMetrics {
    assertNonNegativeFinite('total_reasoning_tokens', input.total_reasoning_tokens)
    assertNonNegativeFinite('total_actions', input.total_actions)
    assertNonNegativeFinite('redundant_action_count', input.redundant_action_count)
    if (input.redundant_action_count > input.total_actions) {
      throw new RangeError('redundant_action_count cannot exceed total_actions')
    }

    const weights = input.weights ?? DEFAULT_WEIGHTS
    for (const [name, value] of Object.entries(weights)) assertNonNegativeFinite(name, value)

    const seen = new Set<string>()
    let redundantDiscoveryCount = 0
    let reconstructionTokens = 0
    for (const discovery of input.discoveries) {
      assertNonNegativeFinite('tokens_consumed', discovery.tokens_consumed)
      const identity = discoveryIdentity(discovery)
      if (seen.has(identity)) {
        redundantDiscoveryCount += 1
        reconstructionTokens += discovery.tokens_consumed
      } else {
        seen.add(identity)
      }
    }

    const redundantHypotheses = input.hypotheses.filter(event => event.is_redundant).length
    const Rd = input.discoveries.length === 0 ? 0 : redundantDiscoveryCount / input.discoveries.length
    const Rh = input.hypotheses.length === 0 ? 0 : redundantHypotheses / input.hypotheses.length
    const Rt = input.total_reasoning_tokens === 0 ? 0 : reconstructionTokens / input.total_reasoning_tokens
    const Ra = input.total_actions === 0 ? 0 : input.redundant_action_count / input.total_actions
    const CRW = weights.w1 * Rd + weights.w2 * Rh + weights.w3 * Rt + weights.w4 * Ra

    const effectCounts = new Map<string, number>()
    for (const effect of input.verified_effects) {
      assertNonNegativeFinite(`verified_effects.${effect.effect_class}`, effect.count)
      effectCounts.set(effect.effect_class, (effectCounts.get(effect.effect_class) ?? 0) + effect.count)
    }

    const tokensPerVerifiedEffect: Record<string, number> = {}
    const actionsPerVerifiedEffect: Record<string, number> = {}
    for (const [effectClass, count] of effectCounts) {
      tokensPerVerifiedEffect[effectClass] = count === 0
        ? Number.POSITIVE_INFINITY
        : input.total_reasoning_tokens / count
      actionsPerVerifiedEffect[effectClass] = count === 0
        ? Number.POSITIVE_INFINITY
        : input.total_actions / count
    }

    return Object.freeze({
      Rd,
      Rh,
      Rt,
      Ra,
      CRW,
      tokens_per_verified_effect: Object.freeze(tokensPerVerifiedEffect),
      actions_per_verified_effect: Object.freeze(actionsPerVerifiedEffect),
    })
  }
}
