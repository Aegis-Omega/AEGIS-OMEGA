/**
 * Production-facing, source-aware verification. A DEMO is never evidence.
 * Pure module so the contract can be tested without React, the network,
 * credentials or a browser DOM.
 */
export interface SystemCheck {
  label: string
  ok: boolean
  reason: string
}
export interface CheckStatusInput {
  contract_version: string
  chain_valid: boolean
}
export interface CheckCalibrationInput {
  homeostasis_zone: string
  recommendation: string
  stagnation_rate: number
  constitutional_factor_mean: number
}
const DEMO_FIELDS = [
  'Bridge reachable', 'Contract version', 'Hash chain valid',
  'Homeostasis', 'Stagnation guard', 'Constitutional factor',
] as const

export function deriveChecks(
  source: 'live' | 'demo', status: CheckStatusInput, cal: CheckCalibrationInput,
): SystemCheck[] {
  // Demo values can be syntactically correct or look healthy, but do not
  // attest that a live backend passed any check.
  if (source !== 'live') {
    return DEMO_FIELDS.map((label) => ({
      label, ok: false,
      reason: label === 'Bridge reachable'
        ? 'live bridge not verified; DEMO fallback engaged'
        : 'not verified: demonstration-only data',
    }))
  }
  return [
    { label: 'Bridge reachable', ok: true, reason: 'connected to live endpoint' },
    { label: 'Contract version', ok: status.contract_version === '1.0.0',
      reason: status.contract_version === '1.0.0' ? 'v1.0.0 matched' : `mismatch: ${status.contract_version}` },
    { label: 'Hash chain valid', ok: status.chain_valid,
      reason: status.chain_valid ? 'live endpoint reports valid chain' : 'live endpoint reports invalid chain' },
    { label: 'Homeostasis', ok: cal.homeostasis_zone === 'optimal' || cal.homeostasis_zone === 'slack',
      reason: `${cal.homeostasis_zone} · ${cal.recommendation}` },
    { label: 'Stagnation guard', ok: Number.isFinite(cal.stagnation_rate) && cal.stagnation_rate >= 0 && cal.stagnation_rate < 0.5,
      reason: Number.isFinite(cal.stagnation_rate) ? `${Math.round(cal.stagnation_rate * 100)}% of recent runs flagged` : 'invalid live metric' },
    { label: 'Constitutional factor', ok: Number.isFinite(cal.constitutional_factor_mean) && cal.constitutional_factor_mean >= 0.7 && cal.constitutional_factor_mean <= 1,
      reason: Number.isFinite(cal.constitutional_factor_mean) ? `mean ${cal.constitutional_factor_mean.toFixed(2)}` : 'invalid live metric' },
  ]
}
