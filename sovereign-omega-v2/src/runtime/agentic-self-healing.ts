// ============================================================
// SOVEREIGN OMEGA — Agentic Self-Healing Runtime V1
// EPISTEMIC TIER: T2 · authority-neutral orchestration layer
//
// Existing constitutional boundaries preserved:
//   detect      → external watchdog/divergence/grace observations
//   contain     → quarantine before repair
//   recover     → ONLY exact pre-fault immutable-state reversion may auto-apply
//   propose     → durable repair is proposal-only
//   verify      → every supplied verifier must pass
//   authorize   → durable mutation remains outside this runtime
//   certify     → hash-chained deterministic healing receipts
//
// T0 boundary:
//   Parallel autonomous mutation authority is prohibited.
//   This runtime can never commit a new durable state.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'

export const AGENTIC_HEALING_SCHEMA_VERSION = '1.0.0' as const
export const HEALING_GENESIS_HASH = '0'.repeat(64) as SHA256Hex
export const MAX_HEALING_ATTEMPTS_PER_INCIDENT = 3 as const

export type HealingSeverity = 'INFO' | 'DEGRADED' | 'FAULT' | 'CRITICAL'
export type HealingPlanMode = 'GRACE_REVERSION' | 'PROPOSE_MUTATION'

export type HealingStatus =
  | 'MONITORING'
  | 'QUARANTINED'
  | 'RECOVERED'
  | 'AWAITING_AUTHORITY'
  | 'SUSPENDED'
  | 'ESCALATED'

export interface HealingObservation {
  readonly incident_id: string
  readonly component_id: string
  readonly fault_code: string
  readonly severity: HealingSeverity
  readonly sequence: SequenceNumber
  readonly state_hash: SHA256Hex
  readonly pre_fault_state_hash: SHA256Hex | null
  readonly evidence_hash: SHA256Hex
  readonly replay_diverged: boolean
  readonly is_replay_reconstructable: true
}

export interface HealingPlanInput {
  readonly mode: HealingPlanMode
  readonly candidate_state_hash: SHA256Hex
  readonly operator_id?: string
  readonly delta_k?: number
  readonly rationale_code: string
}

export interface HealingPlan extends HealingPlanInput {
  readonly planner_id: string
  readonly plan_hash: SHA256Hex
  readonly observation_hash: SHA256Hex
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
}

export interface HealingPlanner {
  readonly planner_id: string
  propose(observation: HealingObservation): Promise<HealingPlanInput | null>
}

export interface HealingVerifierEvidence {
  readonly passed: boolean
  readonly evidence_hash: SHA256Hex
  readonly reason_code?: string
}

export interface HealingVerifier {
  readonly verifier_id: string
  verify(input: {
    readonly observation: HealingObservation
    readonly plan: HealingPlan
    readonly effective_state_hash: SHA256Hex
  }): Promise<HealingVerifierEvidence>
}

export interface HealingVerifierReceipt {
  readonly verifier_id: string
  readonly passed: boolean
  readonly evidence_hash: SHA256Hex
  readonly reason_code?: string
  readonly result_hash: SHA256Hex
}

export interface VolatileRecoveryAdapter {
  /**
   * May only select/restore the exact pre-fault immutable snapshot.
   * It must not construct or commit a new durable state.
   */
  revertToPreFault(input: {
    readonly observation: HealingObservation
    readonly plan: HealingPlan
  }): Promise<{
    readonly applied: boolean
    readonly state_hash: SHA256Hex
  }>
}

export interface HealingAuthorityPreflight {
  /**
   * Eligibility check only. This is NOT mutation approval.
   * Production adapters delegate to the existing sealed operator/capacity/gate path.
   */
  mutationAuthorityActive(): Promise<boolean>
  preflight(input: {
    readonly observation: HealingObservation
    readonly plan: HealingPlan
    readonly operator_id: string
    readonly delta_k: number
  }): Promise<{
    readonly eligible: boolean
    readonly reason_code: string
    readonly evidence_hash: SHA256Hex
  }>
}

export interface HealingCycleAdapters {
  readonly planner: HealingPlanner
  readonly verifiers: readonly HealingVerifier[]
  readonly volatile_recovery?: VolatileRecoveryAdapter
  readonly authority_preflight?: HealingAuthorityPreflight
}

export interface HealingCycleReceipt {
  readonly schema_version: typeof AGENTIC_HEALING_SCHEMA_VERSION
  readonly incident_id: string
  readonly component_id: string
  readonly sequence: SequenceNumber
  readonly status: HealingStatus
  readonly reason_code: string
  readonly observation_hash: SHA256Hex
  readonly plan_hash: SHA256Hex | null
  readonly effective_state_hash: SHA256Hex
  readonly verifier_results: readonly HealingVerifierReceipt[]
  readonly verifier_root: SHA256Hex
  readonly authority_preflight_evidence_hash: SHA256Hex | null
  readonly quarantine_active: boolean
  readonly volatile_reversion_applied: boolean
  readonly durable_apply_performed: false
  readonly authority_effect: 'NONE'
  readonly previous_receipt_hash: SHA256Hex
  readonly receipt_hash: SHA256Hex
  readonly is_replay_reconstructable: true
}

export interface HealingChainCertificate {
  readonly is_valid: boolean
  readonly receipt_count: number
  readonly terminal_hash: SHA256Hex
  readonly certificate_hash: SHA256Hex
  readonly authority_effect: 'NONE'
  readonly is_replay_reconstructable: true
}

export class AgenticHealingError extends Error {
  override readonly name = 'AgenticHealingError'
}

function isHex64(value: string): value is SHA256Hex {
  return /^[0-9a-f]{64}$/.test(value)
}

function requireHex64(value: string, field: string): asserts value is SHA256Hex {
  if (!isHex64(value)) throw new AgenticHealingError(`${field} must be lowercase SHA-256 hex`)
}

function validateObservation(observation: HealingObservation): void {
  if (!observation.incident_id) throw new AgenticHealingError('incident_id required')
  if (!observation.component_id) throw new AgenticHealingError('component_id required')
  if (!observation.fault_code) throw new AgenticHealingError('fault_code required')
  requireHex64(observation.state_hash, 'state_hash')
  requireHex64(observation.evidence_hash, 'evidence_hash')
  if (observation.pre_fault_state_hash !== null) {
    requireHex64(observation.pre_fault_state_hash, 'pre_fault_state_hash')
  }
  if (observation.is_replay_reconstructable !== true) {
    throw new AgenticHealingError('observation must be replay reconstructable')
  }
}

async function observationHash(observation: HealingObservation): Promise<SHA256Hex> {
  return await hashValue({
    incident_id: observation.incident_id,
    component_id: observation.component_id,
    fault_code: observation.fault_code,
    severity: observation.severity,
    sequence: observation.sequence.toString(),
    state_hash: observation.state_hash,
    pre_fault_state_hash: observation.pre_fault_state_hash,
    evidence_hash: observation.evidence_hash,
    replay_diverged: observation.replay_diverged,
    is_replay_reconstructable: observation.is_replay_reconstructable,
  }) as SHA256Hex
}

async function buildPlan(
  observation: HealingObservation,
  observation_hash: SHA256Hex,
  planner: HealingPlanner,
): Promise<HealingPlan | null> {
  if (!planner.planner_id) throw new AgenticHealingError('planner_id required')
  const input = await planner.propose(observation)
  if (input === null) return null

  requireHex64(input.candidate_state_hash, 'candidate_state_hash')
  if (!input.rationale_code) throw new AgenticHealingError('rationale_code required')

  if (input.mode === 'PROPOSE_MUTATION') {
    if (!input.operator_id) throw new AgenticHealingError('operator_id required for durable repair')
    if (
      typeof input.delta_k !== 'number' ||
      !Number.isFinite(input.delta_k) ||
      input.delta_k < 0
    ) {
      throw new AgenticHealingError('delta_k must be finite non-negative for durable repair')
    }
    if (input.candidate_state_hash === observation.state_hash) {
      throw new AgenticHealingError('durable repair candidate must change state hash')
    }
  }

  const plan_hash = await hashValue({
    planner_id: planner.planner_id,
    observation_hash,
    mode: input.mode,
    candidate_state_hash: input.candidate_state_hash,
    operator_id: input.operator_id ?? null,
    delta_k: input.delta_k ?? null,
    rationale_code: input.rationale_code,
  }) as SHA256Hex

  return deepFreeze<HealingPlan>({
    ...input,
    planner_id: planner.planner_id,
    plan_hash,
    observation_hash,
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  })
}

async function runVerifiers(
  observation: HealingObservation,
  plan: HealingPlan,
  effective_state_hash: SHA256Hex,
  verifiers: readonly HealingVerifier[],
): Promise<readonly HealingVerifierReceipt[]> {
  if (verifiers.length === 0) return Object.freeze([])

  const ids = new Set<string>()
  const receipts: HealingVerifierReceipt[] = []

  for (let index = 0; index < verifiers.length; index++) {
    const verifier = verifiers[index]!
    const verifier_id = verifier.verifier_id

    if (!verifier_id || ids.has(verifier_id)) {
      const reason_code = !verifier_id
        ? 'VERIFIER_ID_MISSING'
        : `DUPLICATE_VERIFIER_ID:${verifier_id}`
      const normalized_id = verifier_id || `__invalid_verifier_${index}`
      const evidence_hash = await hashValue({
        reason_code,
        normalized_id,
        index,
        plan_hash: plan.plan_hash,
        effective_state_hash,
      }) as SHA256Hex
      const result_hash = await hashValue({
        verifier_id: normalized_id,
        passed: false,
        evidence_hash,
        reason_code,
        plan_hash: plan.plan_hash,
        effective_state_hash,
      }) as SHA256Hex
      receipts.push(deepFreeze<HealingVerifierReceipt>({
        verifier_id: normalized_id,
        passed: false,
        evidence_hash,
        reason_code,
        result_hash,
      }))
      continue
    }

    ids.add(verifier_id)

    let evidence: HealingVerifierEvidence
    try {
      evidence = await verifier.verify({ observation, plan, effective_state_hash })
      requireHex64(evidence.evidence_hash, `verifier ${verifier_id} evidence_hash`)
    } catch (error) {
      const error_name = error instanceof Error ? error.name : 'UnknownError'
      const evidence_hash = await hashValue({
        verifier_id: verifier_id,
        error_name,
        plan_hash: plan.plan_hash,
        effective_state_hash,
      }) as SHA256Hex
      evidence = {
        passed: false,
        evidence_hash,
        reason_code: `VERIFIER_EXCEPTION:${error_name}`,
      }
    }

    const result_hash = await hashValue({
      verifier_id: verifier_id,
      passed: evidence.passed,
      evidence_hash: evidence.evidence_hash,
      reason_code: evidence.reason_code ?? null,
      plan_hash: plan.plan_hash,
      effective_state_hash,
    }) as SHA256Hex

    receipts.push(deepFreeze<HealingVerifierReceipt>({
      verifier_id: verifier_id,
      passed: evidence.passed,
      evidence_hash: evidence.evidence_hash,
      ...(evidence.reason_code !== undefined ? { reason_code: evidence.reason_code } : {}),
      result_hash,
    }))
  }

  return Object.freeze(receipts)
}

async function verifierRoot(results: readonly HealingVerifierReceipt[]): Promise<SHA256Hex> {
  return await hashValue(results.map(result => result.result_hash)) as SHA256Hex
}

interface EmitReceiptInput {
  readonly observation: HealingObservation
  readonly observation_hash: SHA256Hex
  readonly status: HealingStatus
  readonly reason_code: string
  readonly plan: HealingPlan | null
  readonly effective_state_hash: SHA256Hex
  readonly verifier_results: readonly HealingVerifierReceipt[]
  readonly authority_preflight_evidence_hash?: SHA256Hex
  readonly quarantine_active: boolean
  readonly volatile_reversion_applied: boolean
}

export class AgenticSelfHealingRuntime {
  private constructor(private readonly receipts: readonly HealingCycleReceipt[]) {}

  static create(): AgenticSelfHealingRuntime {
    return new AgenticSelfHealingRuntime(Object.freeze([]))
  }

  get receiptCount(): number { return this.receipts.length }

  get terminalHash(): SHA256Hex {
    return this.receipts.length === 0
      ? HEALING_GENESIS_HASH
      : this.receipts[this.receipts.length - 1]!.receipt_hash
  }

  getReceipts(): readonly HealingCycleReceipt[] {
    return this.receipts
  }

  async runCycle(
    observation: HealingObservation,
    adapters: HealingCycleAdapters,
  ): Promise<{ runtime: AgenticSelfHealingRuntime; receipt: HealingCycleReceipt }> {
    validateObservation(observation)

    const previous = this.receipts.length === 0
      ? null
      : this.receipts[this.receipts.length - 1]!

    if (previous !== null && observation.sequence <= previous.sequence) {
      throw new AgenticHealingError(
        `non-monotonic healing sequence: ${observation.sequence} <= ${previous.sequence}`,
      )
    }

    const priorAttempts = this.receipts.filter(
      receipt =>
        receipt.incident_id === observation.incident_id &&
        receipt.status !== 'MONITORING',
    ).length

    const obsHash = await observationHash(observation)
    const requiresContainment =
      observation.replay_diverged ||
      observation.severity === 'FAULT' ||
      observation.severity === 'CRITICAL'

    if (!requiresContainment) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'MONITORING',
        reason_code: 'OBSERVATION_BELOW_HEALING_THRESHOLD',
        plan: null,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: false,
        volatile_reversion_applied: false,
      })
    }

    if (priorAttempts >= MAX_HEALING_ATTEMPTS_PER_INCIDENT) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: 'HEALING_ATTEMPT_BUDGET_EXHAUSTED',
        plan: null,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    let plan: HealingPlan | null
    try {
      plan = await buildPlan(observation, obsHash, adapters.planner)
    } catch (error) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: error instanceof Error ? `PLANNER_REJECTED:${error.name}` : 'PLANNER_REJECTED',
        plan: null,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    if (plan === null) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: 'NO_REPAIR_PLAN',
        plan: null,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    if (plan.mode === 'GRACE_REVERSION') {
      if (
        observation.pre_fault_state_hash === null ||
        plan.candidate_state_hash !== observation.pre_fault_state_hash
      ) {
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'QUARANTINED',
          reason_code: 'GRACE_REVERSION_TARGET_MISMATCH',
          plan,
          effective_state_hash: observation.state_hash,
          verifier_results: Object.freeze([]),
          quarantine_active: true,
          volatile_reversion_applied: false,
        })
      }

      if (adapters.volatile_recovery === undefined) {
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'ESCALATED',
          reason_code: 'VOLATILE_RECOVERY_ADAPTER_MISSING',
          plan,
          effective_state_hash: observation.state_hash,
          verifier_results: Object.freeze([]),
          quarantine_active: true,
          volatile_reversion_applied: false,
        })
      }

      let recovered: { readonly applied: boolean; readonly state_hash: SHA256Hex }
      try {
        recovered = await adapters.volatile_recovery.revertToPreFault({ observation, plan })
        requireHex64(recovered.state_hash, 'volatile recovery state_hash')
      } catch (error) {
        const error_name = error instanceof Error ? error.name : 'UnknownError'
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'QUARANTINED',
          reason_code: `VOLATILE_RECOVERY_EXCEPTION:${error_name}`,
          plan,
          effective_state_hash: observation.state_hash,
          verifier_results: Object.freeze([]),
          quarantine_active: true,
          volatile_reversion_applied: false,
        })
      }

      if (!recovered.applied || recovered.state_hash !== observation.pre_fault_state_hash) {
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'QUARANTINED',
          reason_code: 'VOLATILE_REVERSION_FAILED',
          plan,
          effective_state_hash: observation.state_hash,
          verifier_results: Object.freeze([]),
          quarantine_active: true,
          volatile_reversion_applied: false,
        })
      }

      const verifierResults = await runVerifiers(
        observation,
        plan,
        recovered.state_hash,
        adapters.verifiers,
      )

      if (verifierResults.length === 0) {
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'ESCALATED',
          reason_code: 'VERIFIER_SET_EMPTY',
          plan,
          effective_state_hash: recovered.state_hash,
          verifier_results: verifierResults,
          quarantine_active: true,
          volatile_reversion_applied: true,
        })
      }

      if (verifierResults.some(result => !result.passed)) {
        return await this.emit({
          observation,
          observation_hash: obsHash,
          status: 'QUARANTINED',
          reason_code: 'POST_REVERSION_VERIFICATION_FAILED',
          plan,
          effective_state_hash: recovered.state_hash,
          verifier_results: verifierResults,
          quarantine_active: true,
          volatile_reversion_applied: true,
        })
      }

      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'RECOVERED',
        reason_code: 'GRACE_REVERSION_VERIFIED',
        plan,
        effective_state_hash: recovered.state_hash,
        verifier_results: verifierResults,
        quarantine_active: false,
        volatile_reversion_applied: true,
      })
    }

    const authority = adapters.authority_preflight
    if (authority === undefined) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: 'AUTHORITY_PREFLIGHT_MISSING',
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    let authorityActive = false
    try {
      authorityActive = await authority.mutationAuthorityActive()
    } catch (error) {
      const error_name = error instanceof Error ? error.name : 'UnknownError'
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'SUSPENDED',
        reason_code: `AUTHORITY_STATUS_EXCEPTION:${error_name}`,
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    if (!authorityActive) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'SUSPENDED',
        reason_code: 'MUTATION_AUTHORITY_SUSPENDED',
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    const operatorId = plan.operator_id
    const deltaK = plan.delta_k
    if (operatorId === undefined || deltaK === undefined) {
      throw new AgenticHealingError('validated durable plan lost operator metadata')
    }

    let preflight: {
      readonly eligible: boolean
      readonly reason_code: string
      readonly evidence_hash: SHA256Hex
    }
    try {
      preflight = await authority.preflight({
        observation,
        plan,
        operator_id: operatorId,
        delta_k: deltaK,
      })
      requireHex64(preflight.evidence_hash, 'authority preflight evidence_hash')
    } catch (error) {
      const error_name = error instanceof Error ? error.name : 'UnknownError'
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: `MUTATION_PREFLIGHT_EXCEPTION:${error_name}`,
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    if (!preflight.eligible) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: `MUTATION_PREFLIGHT_REJECTED:${preflight.reason_code}`,
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: Object.freeze([]),
        authority_preflight_evidence_hash: preflight.evidence_hash,
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    const verifierResults = await runVerifiers(
      observation,
      plan,
      plan.candidate_state_hash,
      adapters.verifiers,
    )

    if (verifierResults.length === 0) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'ESCALATED',
        reason_code: 'VERIFIER_SET_EMPTY',
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: verifierResults,
        authority_preflight_evidence_hash: preflight.evidence_hash,
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    if (verifierResults.some(result => !result.passed)) {
      return await this.emit({
        observation,
        observation_hash: obsHash,
        status: 'QUARANTINED',
        reason_code: 'REPAIR_VERIFICATION_FAILED',
        plan,
        effective_state_hash: observation.state_hash,
        verifier_results: verifierResults,
        authority_preflight_evidence_hash: preflight.evidence_hash,
        quarantine_active: true,
        volatile_reversion_applied: false,
      })
    }

    // Critical authority boundary:
    // The candidate is verified but NOT applied. Existing governance must authorize it.
    return await this.emit({
      observation,
      observation_hash: obsHash,
      status: 'AWAITING_AUTHORITY',
      reason_code: 'DURABLE_REPAIR_VERIFIED_AWAITING_AUTHORITY',
      plan,
      effective_state_hash: observation.state_hash,
      verifier_results: verifierResults,
      authority_preflight_evidence_hash: preflight.evidence_hash,
      quarantine_active: true,
      volatile_reversion_applied: false,
    })
  }

  private async emit(input: EmitReceiptInput): Promise<{
    runtime: AgenticSelfHealingRuntime
    receipt: HealingCycleReceipt
  }> {
    const verifier_root = await verifierRoot(input.verifier_results)
    const previous_receipt_hash = this.terminalHash

    const body = {
      schema_version: AGENTIC_HEALING_SCHEMA_VERSION,
      incident_id: input.observation.incident_id,
      component_id: input.observation.component_id,
      sequence: input.observation.sequence.toString(),
      status: input.status,
      reason_code: input.reason_code,
      observation_hash: input.observation_hash,
      plan_hash: input.plan?.plan_hash ?? null,
      effective_state_hash: input.effective_state_hash,
      verifier_results: input.verifier_results,
      verifier_root,
      authority_preflight_evidence_hash: input.authority_preflight_evidence_hash ?? null,
      quarantine_active: input.quarantine_active,
      volatile_reversion_applied: input.volatile_reversion_applied,
      durable_apply_performed: false,
      authority_effect: 'NONE',
      previous_receipt_hash,
      is_replay_reconstructable: true,
    } as const

    const receipt_hash = await hashValue(body) as SHA256Hex
    const receipt = deepFreeze<HealingCycleReceipt>({
      ...body,
      sequence: input.observation.sequence,
      durable_apply_performed: false,
      authority_effect: 'NONE',
      receipt_hash,
    })

    return {
      runtime: new AgenticSelfHealingRuntime(Object.freeze([...this.receipts, receipt])),
      receipt,
    }
  }
}

export async function certifyHealingChain(
  receipts: readonly HealingCycleReceipt[],
): Promise<HealingChainCertificate> {
  let previous = HEALING_GENESIS_HASH
  let valid = true

  for (const receipt of receipts) {
    if (receipt.previous_receipt_hash !== previous) {
      valid = false
      break
    }

    const body = {
      schema_version: receipt.schema_version,
      incident_id: receipt.incident_id,
      component_id: receipt.component_id,
      sequence: receipt.sequence.toString(),
      status: receipt.status,
      reason_code: receipt.reason_code,
      observation_hash: receipt.observation_hash,
      plan_hash: receipt.plan_hash,
      effective_state_hash: receipt.effective_state_hash,
      verifier_results: receipt.verifier_results,
      verifier_root: receipt.verifier_root,
      authority_preflight_evidence_hash: receipt.authority_preflight_evidence_hash,
      quarantine_active: receipt.quarantine_active,
      volatile_reversion_applied: receipt.volatile_reversion_applied,
      durable_apply_performed: receipt.durable_apply_performed,
      authority_effect: receipt.authority_effect,
      previous_receipt_hash: receipt.previous_receipt_hash,
      is_replay_reconstructable: receipt.is_replay_reconstructable,
    }

    const recomputed = await hashValue(body) as SHA256Hex
    if (recomputed !== receipt.receipt_hash) {
      valid = false
      break
    }
    previous = receipt.receipt_hash
  }

  const terminal_hash = receipts.length === 0
    ? HEALING_GENESIS_HASH
    : receipts[receipts.length - 1]!.receipt_hash

  const certificate_hash = await hashValue({
    is_valid: valid,
    receipt_hashes: receipts.map(receipt => receipt.receipt_hash),
    terminal_hash,
  }) as SHA256Hex

  return deepFreeze<HealingChainCertificate>({
    is_valid: valid,
    receipt_count: receipts.length,
    terminal_hash,
    certificate_hash,
    authority_effect: 'NONE',
    is_replay_reconstructable: true,
  })
}
