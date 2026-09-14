import { computeMerkleRootFromValues, hashValue } from '../../core/hashing.js'
import type { SHA256Hex } from '../../core/types.js'
import type {
  CanonicalEvidenceRef,
  WorkingCognitiveStateV1,
} from './cognitive-state.js'

export type InheritancePolicy =
  | 'PRESERVE'
  | 'RAW_EVIDENCE_ONLY'
  | 'CLEAN_ROOM'
  | 'SELECTIVE'

export type SelectableCognitiveSurface =
  | 'active_plan'
  | 'hypotheses'
  | 'falsified_hypotheses'
  | 'unresolved_obligations'
  | 'next_actions'
  | 'provider_continuation'

export interface CognitiveLineageReceiptV1 {
  readonly receipt_kind: 'COGNITIVE_LINEAGE_RECEIPT_V1'
  readonly schema_version: '1.0.0'
  readonly parent_lineage_root: SHA256Hex
  readonly child_lineage_root: SHA256Hex
  readonly inheritance_policy: InheritancePolicy
  readonly inherited_surface_digest: SHA256Hex
  readonly excluded_surface_digest: SHA256Hex
  readonly evidence_root: SHA256Hex
  readonly provider_state_digest?: SHA256Hex
  readonly authority_class: 'NONE'
  readonly receipt_hash: SHA256Hex
}

export interface CognitiveCompactionReceiptV1 {
  readonly receipt_kind: 'COGNITIVE_COMPACTION_RECEIPT_V1'
  readonly schema_version: '1.0.0'
  readonly source_lineage_root: SHA256Hex
  readonly source_event_range: Readonly<{
    from_seq: number
    to_seq: number
  }>
  readonly source_state_digest: SHA256Hex
  readonly compaction_policy_digest: SHA256Hex
  readonly retained_surface_digest: SHA256Hex
  readonly discarded_surface_classes: readonly string[]
  readonly provider_compaction_digest?: SHA256Hex
  readonly result_state_digest: SHA256Hex
  readonly authority_class: 'NONE'
  readonly receipt_hash: SHA256Hex
}

export interface BuildCognitiveCompactionReceiptV1Input {
  readonly source_lineage_root: SHA256Hex
  readonly source_event_range: Readonly<{
    from_seq: number
    to_seq: number
  }>
  readonly source_state_digest: SHA256Hex
  readonly compaction_policy_digest: SHA256Hex
  readonly retained_surface_digest: SHA256Hex
  readonly discarded_surface_classes: readonly string[]
  readonly provider_compaction_digest?: SHA256Hex
  readonly result_state_digest: SHA256Hex
}

function cloneEvidenceRefs(refs: readonly CanonicalEvidenceRef[]): readonly CanonicalEvidenceRef[] {
  return Object.freeze(refs.map(ref => Object.freeze({ ...ref })))
}

function cloneStrings(values: readonly string[]): readonly string[] {
  return Object.freeze([...values])
}

function baseState(parent: WorkingCognitiveStateV1): WorkingCognitiveStateV1 {
  return {
    schema_version: parent.schema_version,
    lineage_root: parent.lineage_root,
    objective: parent.objective,
    active_plan: Object.freeze([]),
    hypotheses: Object.freeze([]),
    falsified_hypotheses: Object.freeze([]),
    unresolved_obligations: Object.freeze([]),
    evidence_refs: cloneEvidenceRefs(parent.evidence_refs),
    artifact_refs: Object.freeze([...parent.artifact_refs]),
    next_actions: Object.freeze([]),
    budget_state: Object.freeze({ ...parent.budget_state }),
  }
}

function allCognitiveSurfaces(parent: WorkingCognitiveStateV1): Readonly<Record<SelectableCognitiveSurface, unknown>> {
  return Object.freeze({
    active_plan: parent.active_plan,
    hypotheses: parent.hypotheses,
    falsified_hypotheses: parent.falsified_hypotheses,
    unresolved_obligations: parent.unresolved_obligations,
    next_actions: parent.next_actions,
    provider_continuation: parent.provider_continuation ?? null,
  })
}

function applySurface(
  child: WorkingCognitiveStateV1,
  parent: WorkingCognitiveStateV1,
  surface: SelectableCognitiveSurface,
): WorkingCognitiveStateV1 {
  switch (surface) {
    case 'active_plan': return { ...child, active_plan: cloneStrings(parent.active_plan) }
    case 'hypotheses': return { ...child, hypotheses: cloneStrings(parent.hypotheses) }
    case 'falsified_hypotheses': return { ...child, falsified_hypotheses: cloneStrings(parent.falsified_hypotheses) }
    case 'unresolved_obligations': return { ...child, unresolved_obligations: cloneStrings(parent.unresolved_obligations) }
    case 'next_actions': return { ...child, next_actions: cloneStrings(parent.next_actions) }
    case 'provider_continuation': return parent.provider_continuation === undefined
      ? child
      : { ...child, provider_continuation: Object.freeze({ ...parent.provider_continuation }) }
  }
}

function inheritedSurfacesFor(
  policy: InheritancePolicy,
  whitelist: readonly SelectableCognitiveSurface[],
): readonly SelectableCognitiveSurface[] {
  switch (policy) {
    case 'PRESERVE':
      return Object.freeze<SelectableCognitiveSurface[]>([
        'active_plan',
        'hypotheses',
        'falsified_hypotheses',
        'unresolved_obligations',
        'next_actions',
        'provider_continuation',
      ])
    case 'RAW_EVIDENCE_ONLY':
      return Object.freeze<SelectableCognitiveSurface[]>([
        'falsified_hypotheses',
        'unresolved_obligations',
      ])
    case 'CLEAN_ROOM':
      return Object.freeze<SelectableCognitiveSurface[]>(['unresolved_obligations'])
    case 'SELECTIVE':
      return Object.freeze([...new Set(whitelist)])
  }
}

async function evidenceRootFor(refs: readonly CanonicalEvidenceRef[]): Promise<SHA256Hex> {
  const ordered = [...refs].sort((a, b) => a.receipt_hash.localeCompare(b.receipt_hash))
  return computeMerkleRootFromValues(ordered)
}

export class CognitiveLineageManager {
  public static async fork(
    parent: WorkingCognitiveStateV1,
    policy: InheritancePolicy,
    whitelisted_keys: readonly SelectableCognitiveSurface[] = [],
  ): Promise<{ child: WorkingCognitiveStateV1; receipt: CognitiveLineageReceiptV1 }> {
    if (policy !== 'SELECTIVE' && whitelisted_keys.length > 0) {
      throw new TypeError('Cognitive whitelist is valid only for SELECTIVE inheritance')
    }

    const inheritedKeys = inheritedSurfacesFor(policy, whitelisted_keys)
    const inheritedKeySet = new Set(inheritedKeys)
    let child = baseState(parent)
    for (const surface of inheritedKeys) child = applySurface(child, parent, surface)

    const surfaces = allCognitiveSurfaces(parent)
    const inheritedSurface: Record<string, unknown> = {}
    const excludedSurface: Record<string, unknown> = {}
    for (const surface of Object.keys(surfaces) as SelectableCognitiveSurface[]) {
      if (inheritedKeySet.has(surface)) inheritedSurface[surface] = surfaces[surface]
      else excludedSurface[surface] = surfaces[surface]
    }

    const inherited_surface_digest = await hashValue(inheritedSurface)
    const excluded_surface_digest = await hashValue(excludedSurface)
    const evidence_root = await evidenceRootFor(child.evidence_refs)
    const child_lineage_root = await hashValue({
      parent_lineage_root: parent.lineage_root,
      inheritance_policy: policy,
      inherited_surface_digest,
      evidence_root,
    })
    child = Object.freeze({ ...child, lineage_root: child_lineage_root })

    const receiptPayload = Object.freeze({
      receipt_kind: 'COGNITIVE_LINEAGE_RECEIPT_V1' as const,
      schema_version: '1.0.0' as const,
      parent_lineage_root: parent.lineage_root,
      child_lineage_root,
      inheritance_policy: policy,
      inherited_surface_digest,
      excluded_surface_digest,
      evidence_root,
      ...(child.provider_continuation !== undefined
        ? { provider_state_digest: child.provider_continuation.opaque_payload_digest }
        : {}),
      authority_class: 'NONE' as const,
    })

    return {
      child,
      receipt: Object.freeze({ ...receiptPayload, receipt_hash: await hashValue(receiptPayload) }),
    }
  }

  public static async join(
    parent_state: WorkingCognitiveStateV1,
    lineage_receipts: readonly CognitiveLineageReceiptV1[],
    verified_evidence: readonly CanonicalEvidenceRef[],
  ): Promise<WorkingCognitiveStateV1> {
    for (const receipt of lineage_receipts) {
      if (receipt.authority_class !== 'NONE') {
        throw new TypeError('Cognitive lineage receipts must remain authority NONE')
      }
    }

    const byReceipt = new Map<string, CanonicalEvidenceRef>()
    for (const ref of [...parent_state.evidence_refs, ...verified_evidence]) {
      byReceipt.set(ref.receipt_hash, Object.freeze({ ...ref }))
    }
    const evidence_refs = Object.freeze(
      [...byReceipt.values()].sort((a, b) => a.receipt_hash.localeCompare(b.receipt_hash)),
    )
    const receiptHashes = [...lineage_receipts].map(receipt => receipt.receipt_hash).sort()
    const evidence_root = await evidenceRootFor(evidence_refs)
    const lineage_root = await hashValue({
      parent_lineage_root: parent_state.lineage_root,
      operation: 'JOIN',
      lineage_receipt_hashes: receiptHashes,
      evidence_root,
    })

    // Branch prose, plans, hypotheses and provider state are never joined from
    // child branches. Only externally verified evidence references are added.
    return Object.freeze({ ...parent_state, lineage_root, evidence_refs })
  }
}

export async function buildCognitiveCompactionReceiptV1(
  input: BuildCognitiveCompactionReceiptV1Input,
): Promise<CognitiveCompactionReceiptV1> {
  const { from_seq, to_seq } = input.source_event_range
  if (!Number.isSafeInteger(from_seq) || !Number.isSafeInteger(to_seq) || from_seq < 0 || to_seq < from_seq) {
    throw new RangeError('Cognitive compaction event range must be ordered non-negative safe integers')
  }

  const payload = Object.freeze({
    receipt_kind: 'COGNITIVE_COMPACTION_RECEIPT_V1' as const,
    schema_version: '1.0.0' as const,
    source_lineage_root: input.source_lineage_root,
    source_event_range: Object.freeze({ from_seq, to_seq }),
    source_state_digest: input.source_state_digest,
    compaction_policy_digest: input.compaction_policy_digest,
    retained_surface_digest: input.retained_surface_digest,
    discarded_surface_classes: Object.freeze([...new Set(input.discarded_surface_classes)].sort()),
    ...(input.provider_compaction_digest !== undefined
      ? { provider_compaction_digest: input.provider_compaction_digest }
      : {}),
    result_state_digest: input.result_state_digest,
    authority_class: 'NONE' as const,
  })
  return Object.freeze({ ...payload, receipt_hash: await hashValue(payload) })
}
