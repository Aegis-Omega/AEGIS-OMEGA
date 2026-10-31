/** Evidence-bound free-resource planning gate. This is NOT execution authority. */
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import type { SHA256Hex } from '../core/types.js'
import { selectProviderV1, type ProviderMeshSnapshotV1, type ProviderSelectionRequestV1, type ProviderSelectionReceiptV1 } from './provider-mesh.js'

const DEC = /^(0|[1-9][0-9]*)$/
const HASH = /^[0-9a-f]{64}$/
export type FreeResourceUnitV1 = 'REQUEST' | 'TOKEN' | 'SECOND' | 'NEURON'
export interface FreeResourceEvidenceV1 {
  provider_id: string
  source_id: string
  observation_generation: string
  unit: FreeResourceUnitV1
  remaining_units: string
  billing_mode: 'FREE_ONLY' | 'PAID' | 'UNKNOWN'
  overage: 'HARD_DENY' | 'POSSIBLE' | 'UNKNOWN'
  evidence_root: SHA256Hex
}
export interface FreeResourceRequestV1 extends ProviderSelectionRequestV1 {
  unit: FreeResourceUnitV1
  worst_case_units: string
}
export interface FreeResourceDecisionV1 {
  outcome: 'PLANNING_ELIGIBLE' | 'HOLD'
  provider_id: string | null
  capacity_root: SHA256Hex | null
  selection: ProviderSelectionReceiptV1
  decision_root: SHA256Hex
  authority_effect: 'NONE'
}
function unsigned(name: string, n: string): bigint {
  if (typeof n !== 'string' || !DEC.test(n)) throw new TypeError(name + ' must be canonical unsigned decimal')
  return BigInt(n)
}
export async function freeResourceEvidenceRootV1(e: Omit<FreeResourceEvidenceV1,'evidence_root'>): Promise<SHA256Hex> {
  return sha256Hex(canonicalizeJCS({ domain: 'AEGIS_FREE_RESOURCE_EVIDENCE_V1', evidence: e }))
}
/** Approved roots MUST originate outside the untrusted caller. No quota is reserved here. */
export async function planFreeResourceV1(
  snapshot: ProviderMeshSnapshotV1,
  request: FreeResourceRequestV1,
  evidence: readonly FreeResourceEvidenceV1[],
  approved_roots: readonly SHA256Hex[],
): Promise<FreeResourceDecisionV1> {
  const needed = unsigned('worst_case_units', request.worst_case_units)
  if (needed === 0n) throw new TypeError('worst_case_units must be positive')
  if (!(['REQUEST','TOKEN','SECOND','NEURON'] as string[]).includes(request.unit)) throw new TypeError('invalid unit')
  const current = unsigned('current_generation', request.current_generation)
  const maxAge = unsigned('max_observation_age_generations', request.max_observation_age_generations)
  if (!Array.isArray(evidence) || !Array.isArray(approved_roots) || approved_roots.some(r => !HASH.test(r))) {
    throw new TypeError('invalid approved roots')
  }
  const approved = new Set(approved_roots)
  const seen = new Set<string>()
  const safe = new Map<string,SHA256Hex>()
  for (const e of evidence) {
    if (!e || typeof e.provider_id !== 'string' || typeof e.source_id !== 'string'
      || !e.source_id.trim() || !HASH.test(e.evidence_root)) throw new TypeError('invalid evidence')
    if (seen.has(e.provider_id)) throw new TypeError('duplicate provider evidence')
    seen.add(e.provider_id)
    const { evidence_root, ...body } = e
    if (await freeResourceEvidenceRootV1(body) !== evidence_root) throw new TypeError('evidence root mismatch')
    const generation = unsigned('observation_generation', e.observation_generation)
    const remaining = unsigned('remaining_units', e.remaining_units)
    if (!approved.has(evidence_root) || e.unit !== request.unit
      || e.billing_mode !== 'FREE_ONLY' || e.overage !== 'HARD_DENY'
      || generation > current || current - generation > maxAge || remaining < needed) continue
    const observed = snapshot.observations.find(o => o.provider_id === e.provider_id)
    if (!observed || observed.observation_generation !== e.observation_generation) continue
    safe.set(e.provider_id, evidence_root)
  }
  const callerAllowed = request.allowed_providers
  const allowed_providers = [...safe.keys()].filter(id => callerAllowed === undefined || callerAllowed.includes(id)).sort()
  const selection = await selectProviderV1(snapshot, {
    required_capabilities: request.required_capabilities,
    allowed_providers,
    ...(request.preferred_provider_order === undefined ? {} : { preferred_provider_order: request.preferred_provider_order }),
    current_generation: request.current_generation,
    max_observation_age_generations: request.max_observation_age_generations,
  })
  const root = selection.provider_id ? safe.get(selection.provider_id) ?? null : null
  const result = {
    outcome: root ? 'PLANNING_ELIGIBLE' as const : 'HOLD' as const,
    provider_id: root ? selection.provider_id : null,
    capacity_root: root,
    selection,
    authority_effect: 'NONE' as const,
  }
  const decision_root = await sha256Hex(canonicalizeJCS({domain:'AEGIS_FREE_RESOURCE_DECISION_V1', request, result}))
  return {...result, decision_root}
}
