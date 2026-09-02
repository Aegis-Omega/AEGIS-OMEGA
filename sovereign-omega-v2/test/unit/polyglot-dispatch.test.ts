import { describe, expect, it } from 'vitest'
import { routePolyglotTask, type PolyglotParadigm, type ToolchainCapabilityEvidence } from '../../src/polyglot/fabric'
import {
  ROLE_CONTEXT_POLICIES,
  buildDispatchPlan,
  classifyParadigmOracle,
  decomposePolyglotTask,
  type CognitiveRole,
  type ContextInheritancePolicy,
} from '../../src/polyglot/dispatch'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)
const SHA_C = 'c'.repeat(64)

function evidence(toolchain_id: string): ToolchainCapabilityEvidence {
  return {
    schema_version: 'AEGIS-POLYGLOT-CAPABILITY-EVIDENCE-V1',
    toolchain_id,
    status: 'VERIFIED_AVAILABLE',
    toolchain_version: 'test-1.0.0',
    executable_digest_sha256: SHA_A,
    source_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
  }
}

describe('ParadigmDecomposer and isolated execution dispatcher', () => {
  it('pins the three cognitive roles to non-interchangeable inheritance policies', () => {
    expect(ROLE_CONTEXT_POLICIES).toEqual({
      BUILDER: 'PRESERVE',
      FALSIFIER: 'RAW_EVIDENCE_ONLY',
      REVIEWER: 'CLEAN_ROOM',
    } satisfies Record<CognitiveRole, ContextInheritancePolicy>)
  })

  it('classifies paradigms into symbolic, formal, probabilistic and hardware oracle classes', () => {
    expect(classifyParadigmOracle('EQUALITY_SATURATION')).toBe('SYMBOLIC')
    expect(classifyParadigmOracle('SYMBOLIC_LOGIC')).toBe('SYMBOLIC')
    expect(classifyParadigmOracle('FORMAL_PROOF')).toBe('FORMAL')
    expect(classifyParadigmOracle('VERIFIED_SYSTEMS')).toBe('FORMAL')
    expect(classifyParadigmOracle('PROBABILISTIC')).toBe('PROBABILISTIC')
    expect(classifyParadigmOracle('SCIENTIFIC_DYNAMICS')).toBe('PROBABILISTIC')
    expect(classifyParadigmOracle('DIFFERENTIABLE')).toBe('PROBABILISTIC')
    expect(classifyParadigmOracle('ACCELERATOR')).toBe('HARDWARE')
    expect(classifyParadigmOracle('QUANTUM')).toBe('HARDWARE')
    expect(classifyParadigmOracle('NEUROMORPHIC')).toBe('HARDWARE')
  })

  it('decomposes each requested paradigm into Builder, Falsifier and Reviewer work units', async () => {
    const units = await decomposePolyglotTask({
      task_id: 'task-decompose',
      claim_id: 'claim-1',
      required_paradigms: ['EQUALITY_SATURATION', 'FORMAL_PROOF'],
      source_evidence_digest: SHA_C,
    })

    expect(units).toHaveLength(6)
    expect(units.map(x => [x.paradigm, x.role, x.context_policy])).toEqual([
      ['EQUALITY_SATURATION', 'BUILDER', 'PRESERVE'],
      ['EQUALITY_SATURATION', 'FALSIFIER', 'RAW_EVIDENCE_ONLY'],
      ['EQUALITY_SATURATION', 'REVIEWER', 'CLEAN_ROOM'],
      ['FORMAL_PROOF', 'BUILDER', 'PRESERVE'],
      ['FORMAL_PROOF', 'FALSIFIER', 'RAW_EVIDENCE_ONLY'],
      ['FORMAL_PROOF', 'REVIEWER', 'CLEAN_ROOM'],
    ])
    for (const unit of units) {
      expect(unit.work_unit_id).toMatch(/^[0-9a-f]{64}$/)
      expect(unit.source_evidence_digest).toBe(SHA_C)
      expect(unit.authority_class).toBe('NONE')
      expect(unit.authority_effect).toBe('NONE')
      expect(unit.is_replay_reconstructable).toBe(true)
      expect(Object.isFrozen(unit)).toBe(true)
    }
  })

  it('is deterministic across three independent decompositions', async () => {
    const request = {
      task_id: 'task-deterministic-decompose',
      claim_id: 'claim-2',
      required_paradigms: ['SYMBOLIC_LOGIC', 'PROBABILISTIC', 'QUANTUM'] as PolyglotParadigm[],
      source_evidence_digest: SHA_C,
    }
    const a = await decomposePolyglotTask(request)
    const b = await decomposePolyglotTask(request)
    const c = await decomposePolyglotTask(request)
    expect(a).toEqual(b)
    expect(b).toEqual(c)
  })

  it('dispatches only work units whose exact paradigms were selected by verified routing', async () => {
    const route = await routePolyglotTask({
      task_id: 'task-dispatch',
      required_paradigms: ['EQUALITY_SATURATION', 'SYMBOLIC_LOGIC', 'FORMAL_PROOF'],
      max_backends: 2,
      evidence: [evidence('egg'), evidence('cvc5'), evidence('lean4')],
    })
    const units = await decomposePolyglotTask({
      task_id: route.task_id,
      claim_id: 'claim-dispatch',
      required_paradigms: route.required_paradigms,
      source_evidence_digest: SHA_C,
    })
    const plan = await buildDispatchPlan(route, units)

    expect(route.decision).toBe('DEFER')
    expect(plan.decision).toBe('DEFER')
    expect(plan.dispatches).toHaveLength(6)
    expect(new Set(plan.dispatches.map(x => x.toolchain_id))).toEqual(new Set(['egg', 'cvc5']))
    expect(new Set(plan.dispatches.map(x => x.paradigm))).toEqual(
      new Set(['EQUALITY_SATURATION', 'SYMBOLIC_LOGIC']),
    )
    expect(plan.unresolved_paradigms).toEqual(['FORMAL_PROOF'])
    expect(plan.authority_effect).toBe('NONE')
    expect(plan.dispatch_digest).toMatch(/^[0-9a-f]{64}$/)
  })

  it('never changes Falsifier or Reviewer context isolation during dispatch', async () => {
    const route = await routePolyglotTask({
      task_id: 'task-isolation',
      required_paradigms: ['QUANTUM'],
      max_backends: 1,
      evidence: [evidence('cudaq')],
    })
    const units = await decomposePolyglotTask({
      task_id: route.task_id,
      claim_id: 'claim-q',
      required_paradigms: ['QUANTUM'],
      source_evidence_digest: SHA_C,
    })
    const plan = await buildDispatchPlan(route, units)
    const falsifier = plan.dispatches.find(x => x.role === 'FALSIFIER')
    const reviewer = plan.dispatches.find(x => x.role === 'REVIEWER')

    expect(falsifier?.context_policy).toBe('RAW_EVIDENCE_ONLY')
    expect(reviewer?.context_policy).toBe('CLEAN_ROOM')
    expect(falsifier?.toolchain_id).toBe('cudaq')
    expect(reviewer?.toolchain_id).toBe('cudaq')
  })

  it('rejects malformed source evidence digests and route/work-unit task splicing', async () => {
    await expect(decomposePolyglotTask({
      task_id: 'task-bad-digest',
      claim_id: 'claim-bad',
      required_paradigms: ['FORMAL_PROOF'],
      source_evidence_digest: 'abc',
    })).rejects.toThrow(/EVIDENCE_DIGEST/)

    const route = await routePolyglotTask({
      task_id: 'task-route-a',
      required_paradigms: ['FORMAL_PROOF'],
      max_backends: 1,
      evidence: [evidence('lean4')],
    })
    const units = await decomposePolyglotTask({
      task_id: 'task-route-b',
      claim_id: 'claim-splice',
      required_paradigms: ['FORMAL_PROOF'],
      source_evidence_digest: SHA_C,
    })
    await expect(buildDispatchPlan(route, units)).rejects.toThrow(/TASK_SPLICE/)
  })

  it('does not expose an external execution injection seam in the dispatcher planner API', () => {
    const source = buildDispatchPlan.toString() + decomposePolyglotTask.toString()
    expect(source).not.toContain('executor')
    expect(source).not.toContain('commandRunner')
    expect(source).not.toContain('child_process')
  })
})
