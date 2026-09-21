// Gate — Agentic Self-Healing Runtime V1
// EPISTEMIC TIER: T2
//
// The runtime may autonomously contain and revert to an already-existing
// pre-fault immutable snapshot. It may NOT commit a new durable state.
// Durable repair ends at AWAITING_AUTHORITY.

import { describe, expect, it } from 'vitest'
import type { SHA256Hex, SequenceNumber } from '../../src/core/types.js'
import {
  AGENTIC_HEALING_SCHEMA_VERSION,
  MAX_HEALING_ATTEMPTS_PER_INCIDENT,
  AgenticHealingError,
  AgenticSelfHealingRuntime,
  HEALING_GENESIS_HASH,
  certifyHealingChain,
  type HealingAuthorityPreflight,
  type HealingObservation,
  type HealingPlanInput,
  type HealingPlanner,
  type HealingVerifier,
  type VolatileRecoveryAdapter,
} from '../../src/runtime/agentic-self-healing.js'

const h = (c: string): SHA256Hex => c.repeat(64) as SHA256Hex
const seq = (n: number): SequenceNumber => BigInt(n) as SequenceNumber

function observation(overrides: Partial<HealingObservation> = {}): HealingObservation {
  return {
    incident_id: 'inc-1',
    component_id: 'runtime-main',
    fault_code: 'REPLAY_DRIFT',
    severity: 'FAULT',
    sequence: seq(1),
    state_hash: h('a'),
    pre_fault_state_hash: h('b'),
    evidence_hash: h('c'),
    replay_diverged: false,
    is_replay_reconstructable: true,
    ...overrides,
  }
}

function planner(input: HealingPlanInput | null, id = 'planner-1'): HealingPlanner {
  return {
    planner_id: id,
    async propose() { return input },
  }
}

function throwingPlanner(name = 'PlannerBoom'): HealingPlanner {
  return {
    planner_id: 'planner-throw',
    async propose() {
      const err = new Error('boom')
      err.name = name
      throw err
    },
  }
}

function verifier(
  passed: boolean,
  id = 'verifier-1',
  reason_code?: string,
): HealingVerifier {
  return {
    verifier_id: id,
    async verify() {
      return {
        passed,
        evidence_hash: h(passed ? 'd' : 'e'),
        ...(reason_code !== undefined ? { reason_code } : {}),
      }
    },
  }
}

function throwingVerifier(name = 'VerifierBoom'): HealingVerifier {
  return {
    verifier_id: 'verifier-throw',
    async verify() {
      const err = new Error('boom')
      err.name = name
      throw err
    },
  }
}

function recovery(
  applied = true,
  state_hash: SHA256Hex = h('b'),
): VolatileRecoveryAdapter {
  return {
    async revertToPreFault() {
      return { applied, state_hash }
    },
  }
}

function throwingRecovery(name = 'RecoveryBoom'): VolatileRecoveryAdapter {
  return {
    async revertToPreFault() {
      const err = new Error('boom')
      err.name = name
      throw err
    },
  }
}

function authority(
  active = true,
  eligible = true,
  reason_code = 'SEALED_REGISTRY_AND_K_BOUND_OK',
): HealingAuthorityPreflight {
  return {
    async mutationAuthorityActive() { return active },
    async preflight() {
      return {
        eligible,
        reason_code,
        evidence_hash: h('f'),
      }
    },
  }
}

const reversionPlan: HealingPlanInput = {
  mode: 'GRACE_REVERSION',
  candidate_state_hash: h('b'),
  rationale_code: 'REVERT_TO_PREFAULT_IMMUTABLE_STATE',
}

const mutationPlan: HealingPlanInput = {
  mode: 'PROPOSE_MUTATION',
  candidate_state_hash: h('9'),
  operator_id: 'repair-operator-v1',
  delta_k: 1,
  rationale_code: 'BOUNDED_DURABLE_REPAIR',
}

describe('Agentic Self-Healing Runtime V1', () => {
  it('exports the frozen v1 schema and zero genesis', () => {
    expect(AGENTIC_HEALING_SCHEMA_VERSION).toBe('1.0.0')
    expect(HEALING_GENESIS_HASH).toBe('0'.repeat(64))
  })

  it('MONITORING path does not call planner below healing threshold', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation({ severity: 'DEGRADED', replay_diverged: false }),
      {
        planner: throwingPlanner(),
        verifiers: [],
      },
    )
    expect(result.receipt.status).toBe('MONITORING')
    expect(result.receipt.quarantine_active).toBe(false)
    expect(result.receipt.plan_hash).toBeNull()
    expect(result.receipt.durable_apply_performed).toBe(false)
    expect(result.receipt.authority_effect).toBe('NONE')
  })

  it('replay divergence forces containment even when severity is DEGRADED', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation({ severity: 'DEGRADED', replay_diverged: true }),
      {
        planner: planner(null),
        verifiers: [],
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('NO_REPAIR_PLAN')
    expect(result.receipt.quarantine_active).toBe(true)
  })

  it('planner exception becomes ESCALATED receipt instead of crashing runtime', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: throwingPlanner('PlannerCrash'),
        verifiers: [],
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('PLANNER_REJECTED:PlannerCrash')
    expect(result.receipt.quarantine_active).toBe(true)
  })

  it('GRACE_REVERSION rejects candidate not equal to exact pre-fault state', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner({
          ...reversionPlan,
          candidate_state_hash: h('8'),
        }),
        verifiers: [verifier(true)],
        volatile_recovery: recovery(),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('GRACE_REVERSION_TARGET_MISMATCH')
    expect(result.receipt.volatile_reversion_applied).toBe(false)
  })

  it('GRACE_REVERSION requires a recovery adapter', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [verifier(true)],
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('VOLATILE_RECOVERY_ADAPTER_MISSING')
  })

  it('recovery adapter exception is quarantined', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [verifier(true)],
        volatile_recovery: throwingRecovery('SnapshotFault'),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('VOLATILE_RECOVERY_EXCEPTION:SnapshotFault')
  })

  it('recovery must report the exact pre-fault state hash', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [verifier(true)],
        volatile_recovery: recovery(true, h('7')),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('VOLATILE_REVERSION_FAILED')
  })

  it('successful reversion still requires at least one verifier', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [],
        volatile_recovery: recovery(),
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('VERIFIER_SET_EMPTY')
    expect(result.receipt.volatile_reversion_applied).toBe(true)
    expect(result.receipt.quarantine_active).toBe(true)
  })

  it('post-reversion verifier rejection keeps system quarantined', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [verifier(false, 'v1', 'STATE_NOT_RESTORED')],
        volatile_recovery: recovery(),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('POST_REVERSION_VERIFICATION_FAILED')
    expect(result.receipt.verifier_results[0]?.passed).toBe(false)
  })

  it('verifier exception is converted into failing verifier evidence', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [throwingVerifier('VerifierCrash')],
        volatile_recovery: recovery(),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.verifier_results[0]?.passed).toBe(false)
    expect(result.receipt.verifier_results[0]?.reason_code).toBe(
      'VERIFIER_EXCEPTION:VerifierCrash',
    )
    expect(result.receipt.verifier_results[0]?.evidence_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('exact Grace reversion plus all verifiers PASS yields RECOVERED', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        verifiers: [verifier(true, 'v1'), verifier(true, 'v2')],
        volatile_recovery: recovery(),
      },
    )
    expect(result.receipt.status).toBe('RECOVERED')
    expect(result.receipt.reason_code).toBe('GRACE_REVERSION_VERIFIED')
    expect(result.receipt.effective_state_hash).toBe(h('b'))
    expect(result.receipt.quarantine_active).toBe(false)
    expect(result.receipt.volatile_reversion_applied).toBe(true)
    expect(result.receipt.durable_apply_performed).toBe(false)
    expect(result.receipt.authority_preflight_evidence_hash).toBeNull()
  })

  it('durable mutation without authority adapter is ESCALATED', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('AUTHORITY_PREFLIGHT_MISSING')
  })

  it('suspended mutation authority blocks durable repair before verifier execution', async () => {
    let verifierCalled = false
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [{
          verifier_id: 'must-not-run',
          async verify() {
            verifierCalled = true
            return { passed: true, evidence_hash: h('d') }
          },
        }],
        authority_preflight: authority(false),
      },
    )
    expect(result.receipt.status).toBe('SUSPENDED')
    expect(result.receipt.reason_code).toBe('MUTATION_AUTHORITY_SUSPENDED')
    expect(verifierCalled).toBe(false)
  })

  it('authority status exception fails closed to SUSPENDED', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
        authority_preflight: {
          async mutationAuthorityActive() {
            const err = new Error('boom')
            err.name = 'AuthorityProbeFault'
            throw err
          },
          async preflight() {
            throw new Error('must not run')
          },
        },
      },
    )
    expect(result.receipt.status).toBe('SUSPENDED')
    expect(result.receipt.reason_code).toBe(
      'AUTHORITY_STATUS_EXCEPTION:AuthorityProbeFault',
    )
  })

  it('authority preflight rejection is content-addressed in receipt', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
        authority_preflight: authority(true, false, 'K_BOUND_EXCEEDED'),
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe(
      'MUTATION_PREFLIGHT_REJECTED:K_BOUND_EXCEEDED',
    )
    expect(result.receipt.authority_preflight_evidence_hash).toBe(h('f'))
  })

  it('authority preflight exception becomes ESCALATED rather than applied', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
        authority_preflight: {
          async mutationAuthorityActive() { return true },
          async preflight() {
            const err = new Error('boom')
            err.name = 'RegistryUnavailable'
            throw err
          },
        },
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe(
      'MUTATION_PREFLIGHT_EXCEPTION:RegistryUnavailable',
    )
    expect(result.receipt.durable_apply_performed).toBe(false)
  })

  it('durable repair verifier failure keeps original state quarantined', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(false, 'v1', 'REGRESSION')],
        authority_preflight: authority(),
      },
    )
    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('REPAIR_VERIFICATION_FAILED')
    expect(result.receipt.effective_state_hash).toBe(h('a'))
    expect(result.receipt.authority_preflight_evidence_hash).toBe(h('f'))
    expect(result.receipt.durable_apply_performed).toBe(false)
  })

  it('verified durable repair stops at AWAITING_AUTHORITY and never applies', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true, 'v1'), verifier(true, 'v2')],
        authority_preflight: authority(),
      },
    )
    expect(result.receipt.status).toBe('AWAITING_AUTHORITY')
    expect(result.receipt.reason_code).toBe(
      'DURABLE_REPAIR_VERIFIED_AWAITING_AUTHORITY',
    )
    expect(result.receipt.effective_state_hash).toBe(h('a'))
    expect(result.receipt.plan_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(result.receipt.plan?.plan_hash).toBe(result.receipt.plan_hash)
    expect(result.receipt.plan?.candidate_state_hash).toBe(h('9'))
    expect(result.receipt.plan?.operator_id).toBe('repair-operator-v1')
    expect(result.receipt.authority_preflight?.eligible).toBe(true)
    expect(result.receipt.authority_preflight?.evidence_hash).toBe(h('f'))
    expect(result.receipt.authority_preflight_evidence_hash).toBe(h('f'))
    expect(result.receipt.attempt_number).toBe(1)
    expect(result.receipt.attempt_budget).toBe(MAX_HEALING_ATTEMPTS_PER_INCIDENT)
    expect(result.receipt.durable_apply_performed).toBe(false)
    expect(result.receipt.authority_effect).toBe('NONE')
    expect(result.receipt.quarantine_active).toBe(true)
  })

  it('durable no-op mutation plan is rejected before authority path', async () => {
    const runtime = AgenticSelfHealingRuntime.create()
    const result = await runtime.runCycle(
      observation(),
      {
        planner: planner({
          ...mutationPlan,
          candidate_state_hash: h('a'),
        }),
        verifiers: [verifier(true)],
        authority_preflight: authority(),
      },
    )
    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('PLANNER_REJECTED:AgenticHealingError')
  })

  it('non-monotonic healing sequence is a hard error', async () => {
    const first = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ sequence: seq(5), severity: 'INFO' }),
      { planner: planner(null), verifiers: [] },
    )

    await expect(
      first.runtime.runCycle(
        observation({ incident_id: 'inc-2', sequence: seq(5), severity: 'INFO' }),
        { planner: planner(null), verifiers: [] },
      ),
    ).rejects.toThrow(AgenticHealingError)
  })

  it('receipts are deterministic for identical inputs and deterministic adapters', async () => {
    async function runOnce() {
      return await AgenticSelfHealingRuntime.create().runCycle(
        observation(),
        {
          planner: planner(reversionPlan),
          verifiers: [verifier(true)],
          volatile_recovery: recovery(),
        },
      )
    }

    const [a, b, c] = await Promise.all([runOnce(), runOnce(), runOnce()])
    expect(a.receipt.receipt_hash).toBe(b.receipt.receipt_hash)
    expect(b.receipt.receipt_hash).toBe(c.receipt.receipt_hash)
    expect(a.receipt.verifier_root).toBe(b.receipt.verifier_root)
  })

  it('receipt chain links from zero genesis and certifies', async () => {
    const first = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ severity: 'INFO', sequence: seq(1) }),
      { planner: planner(null), verifiers: [] },
    )
    const second = await first.runtime.runCycle(
      observation({
        incident_id: 'inc-2',
        severity: 'INFO',
        sequence: seq(2),
        evidence_hash: h('4'),
      }),
      { planner: planner(null), verifiers: [] },
    )

    expect(first.receipt.previous_receipt_hash).toBe(HEALING_GENESIS_HASH)
    expect(second.receipt.previous_receipt_hash).toBe(first.receipt.receipt_hash)

    const cert = await certifyHealingChain(second.runtime.getReceipts())
    expect(cert.is_valid).toBe(true)
    expect(cert.receipt_count).toBe(2)
    expect(cert.terminal_hash).toBe(second.receipt.receipt_hash)
    expect(cert.authority_effect).toBe('NONE')
  })

  it('healing chain certification detects receipt tamper', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ severity: 'INFO' }),
      { planner: planner(null), verifiers: [] },
    )

    const tampered = {
      ...result.receipt,
      reason_code: 'TAMPERED',
    }

    const cert = await certifyHealingChain([tampered])
    expect(cert.is_valid).toBe(false)
  })

  it('healing attempt budget stops repeated repair storms before planner re-entry', async () => {
    let runtime = AgenticSelfHealingRuntime.create()

    for (let i = 1; i <= MAX_HEALING_ATTEMPTS_PER_INCIDENT; i++) {
      const result = await runtime.runCycle(
        observation({ sequence: seq(i) }),
        { planner: planner(null), verifiers: [] },
      )
      expect(result.receipt.status).toBe('ESCALATED')
      expect(result.receipt.reason_code).toBe('NO_REPAIR_PLAN')
      runtime = result.runtime
    }

    let plannerCalled = false
    const exhausted = await runtime.runCycle(
      observation({ sequence: seq(MAX_HEALING_ATTEMPTS_PER_INCIDENT + 1) }),
      {
        planner: {
          planner_id: 'must-not-run',
          async propose() {
            plannerCalled = true
            return reversionPlan
          },
        },
        verifiers: [],
      },
    )

    expect(plannerCalled).toBe(false)
    expect(exhausted.receipt.status).toBe('ESCALATED')
    expect(exhausted.receipt.reason_code).toBe('HEALING_ATTEMPT_BUDGET_EXHAUSTED')
    expect(exhausted.receipt.attempt_number).toBe(MAX_HEALING_ATTEMPTS_PER_INCIDENT + 1)
    expect(exhausted.receipt.attempt_budget).toBe(MAX_HEALING_ATTEMPTS_PER_INCIDENT)
    expect(exhausted.receipt.quarantine_active).toBe(true)
    expect(exhausted.receipt.durable_apply_performed).toBe(false)
  })

  it('duplicate verifier IDs become failing evidence instead of throwing', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation(),
      {
        planner: planner(reversionPlan),
        volatile_recovery: recovery(),
        verifiers: [
          verifier(true, 'dup'),
          verifier(true, 'dup'),
        ],
      },
    )

    expect(result.receipt.status).toBe('QUARANTINED')
    expect(result.receipt.reason_code).toBe('POST_REVERSION_VERIFICATION_FAILED')
    expect(result.receipt.verifier_results).toHaveLength(2)
    expect(result.receipt.verifier_results[1]?.passed).toBe(false)
    expect(result.receipt.verifier_results[1]?.reason_code).toBe('DUPLICATE_VERIFIER_ID:dup')
  })

  it('malformed runtime severity is rejected before planner execution', async () => {
    let plannerCalled = false
    const malformed = {
      ...observation(),
      severity: 'UNKNOWN' as HealingObservation['severity'],
    }

    await expect(
      AgenticSelfHealingRuntime.create().runCycle(
        malformed,
        {
          planner: {
            planner_id: 'p',
            async propose() {
              plannerCalled = true
              return reversionPlan
            },
          },
          verifiers: [],
        },
      ),
    ).rejects.toThrow('invalid healing severity')

    expect(plannerCalled).toBe(false)
  })

  it('malformed plan mode is converted into planner rejection receipt', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation(),
      {
        planner: planner({
          ...reversionPlan,
          mode: 'UNKNOWN' as HealingPlanInput['mode'],
        }),
        verifiers: [],
      },
    )

    expect(result.receipt.status).toBe('ESCALATED')
    expect(result.receipt.reason_code).toBe('PLANNER_REJECTED:AgenticHealingError')
  })

  it('certifier rejects forged authority effect and trusts no forged terminal', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ severity: 'INFO' }),
      { planner: planner(null), verifiers: [] },
    )

    const forged = {
      ...result.receipt,
      authority_effect: 'ADMIT' as never,
    }

    const cert = await certifyHealingChain([forged])
    expect(cert.is_valid).toBe(false)
    expect(cert.terminal_hash).toBe(HEALING_GENESIS_HASH)
  })

  it('certifier rejects forged durable apply state', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ severity: 'INFO' }),
      { planner: planner(null), verifiers: [] },
    )

    const forged = {
      ...result.receipt,
      durable_apply_performed: true as never,
    }

    const cert = await certifyHealingChain([forged])
    expect(cert.is_valid).toBe(false)
    expect(cert.terminal_hash).toBe(HEALING_GENESIS_HASH)
  })

  it('certifier stops terminal at last valid receipt on later chain corruption', async () => {
    const first = await AgenticSelfHealingRuntime.create().runCycle(
      observation({ severity: 'INFO', sequence: seq(1) }),
      { planner: planner(null), verifiers: [] },
    )
    const second = await first.runtime.runCycle(
      observation({
        incident_id: 'inc-2',
        severity: 'INFO',
        sequence: seq(2),
        evidence_hash: h('4'),
      }),
      { planner: planner(null), verifiers: [] },
    )

    const forgedSecond = {
      ...second.receipt,
      sequence: seq(1),
    }

    const cert = await certifyHealingChain([first.receipt, forgedSecond])
    expect(cert.is_valid).toBe(false)
    expect(cert.terminal_hash).toBe(first.receipt.receipt_hash)
  })

  it('certifier rejects forged self-contained plan body even when receipt object is otherwise intact', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
        authority_preflight: authority(),
      },
    )

    const forged = {
      ...result.receipt,
      plan: result.receipt.plan === null
        ? null
        : {
            ...result.receipt.plan,
            candidate_state_hash: h('8'),
          },
    }

    const cert = await certifyHealingChain([forged])
    expect(cert.is_valid).toBe(false)
    expect(cert.terminal_hash).toBe(HEALING_GENESIS_HASH)
  })

  it('certifier rejects authority preflight body/hash mismatch', async () => {
    const result = await AgenticSelfHealingRuntime.create().runCycle(
      observation(),
      {
        planner: planner(mutationPlan),
        verifiers: [verifier(true)],
        authority_preflight: authority(),
      },
    )

    const forged = {
      ...result.receipt,
      authority_preflight: result.receipt.authority_preflight === null
        ? null
        : {
            ...result.receipt.authority_preflight,
            evidence_hash: h('8'),
          },
    }

    const cert = await certifyHealingChain([forged])
    expect(cert.is_valid).toBe(false)
    expect(cert.terminal_hash).toBe(HEALING_GENESIS_HASH)
  })

  it('invalid observation hash fails before planner execution', async () => {
    let plannerCalled = false
    const bad = {
      ...observation(),
      state_hash: 'not-a-hash' as SHA256Hex,
    }
    await expect(
      AgenticSelfHealingRuntime.create().runCycle(
        bad,
        {
          planner: {
            planner_id: 'p',
            async propose() {
              plannerCalled = true
              return mutationPlan
            },
          },
          verifiers: [],
        },
      ),
    ).rejects.toThrow(AgenticHealingError)
    expect(plannerCalled).toBe(false)
  })
})
