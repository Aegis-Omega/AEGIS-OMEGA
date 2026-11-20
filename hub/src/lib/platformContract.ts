/**
 * Platform console contract boundary. Pure, dependency-free and fail-closed.
 * Never turns a failed or malformed provider response into synthetic telemetry.
 */
export type HomeostasisZone = 'slack' | 'optimal' | 'stressed' | 'critical'
export type CalibrationRecommendation = 'EASE' | 'MAINTAIN' | 'TIGHTEN'
export type Tier = 'explorer' | 'operator' | 'sovereign'

export interface CalibrationStatus {
  homeostasis_zone: HomeostasisZone
  recommendation: CalibrationRecommendation
  fitness_mean: number
  fitness_variance: number
  hd_equivalent: number
  stagnation_rate: number
  window_size: number
  trend: 'rising' | 'falling' | 'stable'
  constitutional_factor_mean: number
}

export interface AgentTool {
  api_name: string
  endpoint_url: string
  capabilities: string[]
  tier_required: Tier
}

export interface PlatformStatus {
  version: string
  contract_version: string
  total_agents: number
  chain_valid: boolean
  audit_chain_hash: string
  available: boolean
}

export interface SystemCheck {
  label: string
  ok: boolean
  reason: string
}

export type ConsoleSnapshot =
  | {
      source: 'live'
      reason: string
      status: PlatformStatus
      calibration: CalibrationStatus
      tools: AgentTool[]
      checks: SystemCheck[]
    }
  | {
      source: 'unknown'
      reason: string
      status: null
      calibration: null
      tools: []
      checks: SystemCheck[]
    }

function record(x: unknown): x is Record<string, unknown> {
  return typeof x === 'object' && x !== null && !Array.isArray(x)
}

function finite(x: unknown): x is number {
  return typeof x === 'number' && Number.isFinite(x)
}

function member<T extends string>(x: unknown, options: readonly T[]): x is T {
  return typeof x === 'string' && options.includes(x as T)
}

export function isPlatformStatus(x: unknown): x is PlatformStatus {
  if (!record(x)) return false
  return typeof x.version === 'string' && x.version.length > 0 &&
    typeof x.contract_version === 'string' && x.contract_version.length > 0 &&
    Number.isSafeInteger(x.total_agents) && (x.total_agents as number) >= 0 &&
    typeof x.chain_valid === 'boolean' &&
    typeof x.audit_chain_hash === 'string' &&
    typeof x.available === 'boolean'
}

export function isCalibrationStatus(x: unknown): x is CalibrationStatus {
  if (!record(x)) return false
  return member(x.homeostasis_zone, ['slack', 'optimal', 'stressed', 'critical']) &&
    member(x.recommendation, ['EASE', 'MAINTAIN', 'TIGHTEN']) &&
    finite(x.fitness_mean) && finite(x.fitness_variance) &&
    finite(x.hd_equivalent) && finite(x.stagnation_rate) &&
    Number.isSafeInteger(x.window_size) && (x.window_size as number) >= 0 &&
    member(x.trend, ['rising', 'falling', 'stable']) &&
    finite(x.constitutional_factor_mean)
}

export function isAgentTool(x: unknown): x is AgentTool {
  return record(x) && typeof x.api_name === 'string' &&
    typeof x.endpoint_url === 'string' &&
    Array.isArray(x.capabilities) && x.capabilities.every(v => typeof v === 'string') &&
    member(x.tier_required, ['explorer', 'operator', 'sovereign'])
}

export function unknownSnapshot(reason = 'Platform telemetry unavailable or schema invalid'): ConsoleSnapshot {
  return {
    source: 'unknown', reason, status: null, calibration: null, tools: [],
    checks: [{ label: 'Platform evidence', ok: false, reason: `UNKNOWN: ${reason}` }],
  }
}

/** API self-reports are observations, not independent verification. */
export function deriveChecks(status: PlatformStatus, cal: CalibrationStatus): SystemCheck[] {
  return [
    { label: 'Platform availability (API)', ok: status.available,
      reason: status.available ? 'API reports available' : 'API reports unavailable' },
    { label: 'Contract version', ok: status.contract_version === '1.0.0',
      reason: status.contract_version === '1.0.0' ? 'v1.0.0 matched' : `mismatch: ${status.contract_version}` },
    { label: 'Hash chain (API self-report)', ok: status.chain_valid,
      reason: status.chain_valid ? 'API reports valid; independent replay not established' : 'API reports invalid' },
    { label: 'Homeostasis (API)', ok: cal.homeostasis_zone === 'optimal' || cal.homeostasis_zone === 'slack',
      reason: `${cal.homeostasis_zone} / ${cal.recommendation}` },
    { label: 'Stagnation guard', ok: cal.stagnation_rate < 0.5,
      reason: `${Math.round(cal.stagnation_rate * 100)}% of recent runs flagged` },
    { label: 'Constitutional factor', ok: cal.constitutional_factor_mean >= 0.7,
      reason: `API mean ${cal.constitutional_factor_mean.toFixed(2)}` },
  ]
}

/**
 * Only data passing the expected shapes is eligible for a live display.
 * Tools data is optional: malformed data becomes an empty list, never demo tools.
 */
export function toConsoleSnapshot(
  rawStatus: unknown,
  rawCalibration: unknown,
  rawToolsEnvelope: unknown,
): ConsoleSnapshot {
  if (!isPlatformStatus(rawStatus) || !isCalibrationStatus(rawCalibration)) {
    return unknownSnapshot('Required /platform/status or /platform/calibration evidence missing or invalid')
  }
  const validTools = record(rawToolsEnvelope) && Array.isArray(rawToolsEnvelope.tools) &&
    rawToolsEnvelope.tools.every(isAgentTool)
  const tools: AgentTool[] = validTools ? rawToolsEnvelope.tools as AgentTool[] : []
  return {
    source: 'live',
    reason: validTools ? 'Validated live API response' : 'Validated status/calibration; tools UNKNOWN',
    status: rawStatus,
    calibration: rawCalibration,
    tools,
    checks: deriveChecks(rawStatus, rawCalibration),
  }
}
