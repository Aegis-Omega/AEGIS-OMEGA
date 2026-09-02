import { describe, expect, it } from 'vitest'
import {
  POLYGLOT_FRONTIER_CATALOG,
  PolyglotCapabilityError,
  buildPolyglotMetacognitiveObservation,
  routePolyglotTask,
  type PolyglotParadigm,
  type ToolchainCapabilityEvidence,
} from '../../src/polyglot/fabric'

const SHA_A = 'a'.repeat(64)
const SHA_B = 'b'.repeat(64)

function evidence(
  toolchain_id: string,
  overrides: Partial<ToolchainCapabilityEvidence> = {},
): ToolchainCapabilityEvidence {
  return {
    schema_version: 'AEGIS-POLYGLOT-CAPABILITY-EVIDENCE-V1',
    toolchain_id,
    status: 'VERIFIED_AVAILABLE',
    toolchain_version: 'test-1.0.0',
    executable_digest_sha256: SHA_A,
    source_receipt_digest: SHA_B,
    authority_class: 'NONE',
    authority_effect: 'NONE',
    ...overrides,
  }
}

describe('Polyglot Metacognitive Capability Fabric', () => {
  it('catalogues genuinely different computational paradigms without granting authority', () => {
    const paradigms = new Set(POLYGLOT_FRONTIER_CATALOG.map(entry => entry.paradigm))
    const ids = POLYGLOT_FRONTIER_CATALOG.map(entry => entry.toolchain_id)

    expect(new Set(ids).size).toBe(ids.length)
    expect(paradigms).toEqual(expect.objectContaining(new Set<PolyglotParadigm>([
      'CONTENT_ADDRESSED',
      'EQUALITY_SATURATION',
      'SYMBOLIC_LOGIC',
      'PROBABILISTIC',
      'FORMAL_PROOF',
      'VERIFIED_SYSTEMS',
      'ACCELERATOR',
      'META_COMPILER',
      'QUANTUM',
      'NEUROMORPHIC',
      'SCIENTIFIC_DYNAMICS',
      'DIFFERENTIABLE',
    ])))

    for (const entry of POLYGLOT_FRONTIER_CATALOG) {
      expect(entry.authority_class).toBe('NONE')
      expect(entry.authority_effect).toBe('NONE')
      expect(entry.default_state).toBe('CATALOGUED_NOT_VERIFIED')
    }
  })

  it('fails closed when a requested paradigm has no verified capability evidence', async () => {
    const receipt = await routePolyglotTask({
      task_id: 'task-no-evidence',
      required_paradigms: ['EQUALITY_SATURATION'],
      max_backends: 2,
      evidence: [],
    })

    expect(receipt.decision).toBe('DEFER')
    expect(receipt.selected_toolchains).toEqual([])
    expect(receipt.unresolved_paradigms).toEqual(['EQUALITY_SATURATION'])
    expect(receipt.authority_effect).toBe('NONE')
  })

  it('rejects malformed or authority-bearing capability evidence', async () => {
    await expect(routePolyglotTask({
      task_id: 'task-bad-digest',
      required_paradigms: ['CONTENT_ADDRESSED'],
      max_backends: 1,
      evidence: [evidence('unison', { executable_digest_sha256: 'abc' })],
    })).rejects.toThrow(PolyglotCapabilityError)

    await expect(routePolyglotTask({
      task_id: 'task-authority-splice',
      required_paradigms: ['CONTENT_ADDRESSED'],
      max_backends: 1,
      evidence: [evidence('unison', { authority_effect: 'KNOWLEDGE_ADMISSION' as never })],
    })).rejects.toThrow(/AUTHORITY/)
  })

  it('routes only through verified evidence and is deterministic across three independent runs', async () => {
    const request = {
      task_id: 'task-symbolic-proof',
      required_paradigms: ['EQUALITY_SATURATION', 'SYMBOLIC_LOGIC', 'FORMAL_PROOF'] as PolyglotParadigm[],
      max_backends: 3,
      evidence: [
        evidence('egg'),
        evidence('cvc5'),
        evidence('lean4'),
        evidence('unison'),
      ],
    }

    const first = await routePolyglotTask(request)
    const second = await routePolyglotTask(request)
    const third = await routePolyglotTask(request)

    expect(first).toEqual(second)
    expect(second).toEqual(third)
    expect(first.decision).toBe('ROUTE')
    expect(first.selected_toolchains.map(x => x.toolchain_id)).toEqual(['egg', 'cvc5', 'lean4'])
    expect(first.unresolved_paradigms).toEqual([])
    expect(first.route_digest).toMatch(/^[0-9a-f]{64}$/)
  })

  it('never substitutes a verified toolchain from the wrong computational paradigm', async () => {
    const receipt = await routePolyglotTask({
      task_id: 'task-no-substitution',
      required_paradigms: ['PROBABILISTIC'],
      max_backends: 2,
      evidence: [evidence('lean4'), evidence('cvc5')],
    })

    expect(receipt.decision).toBe('DEFER')
    expect(receipt.selected_toolchains).toEqual([])
    expect(receipt.unresolved_paradigms).toEqual(['PROBABILISTIC'])
  })

  it('keeps partial cross-paradigm plans explicit instead of laundering them into success', async () => {
    const receipt = await routePolyglotTask({
      task_id: 'task-partial',
      required_paradigms: ['CONTENT_ADDRESSED', 'NEUROMORPHIC'],
      max_backends: 2,
      evidence: [evidence('unison')],
    })

    expect(receipt.decision).toBe('DEFER')
    expect(receipt.selected_toolchains.map(x => x.toolchain_id)).toEqual(['unison'])
    expect(receipt.unresolved_paradigms).toEqual(['NEUROMORPHIC'])
  })

  it('enforces the requested backend budget without changing paradigm order', async () => {
    const receipt = await routePolyglotTask({
      task_id: 'task-budget',
      required_paradigms: ['EQUALITY_SATURATION', 'SYMBOLIC_LOGIC', 'FORMAL_PROOF'],
      max_backends: 2,
      evidence: [evidence('egg'), evidence('cvc5'), evidence('lean4')],
    })

    expect(receipt.selected_toolchains.map(x => x.toolchain_id)).toEqual(['egg', 'cvc5'])
    expect(receipt.unresolved_paradigms).toEqual(['FORMAL_PROOF'])
    expect(receipt.decision).toBe('DEFER')
  })

  it('emits an authority-neutral T2 metacognitive observation for the self-model', async () => {
    const receipt = await routePolyglotTask({
      task_id: 'task-self-model',
      required_paradigms: ['CONTENT_ADDRESSED'],
      max_backends: 1,
      evidence: [evidence('unison')],
    })
    const observation = buildPolyglotMetacognitiveObservation(receipt)

    expect(observation.layer).toBe('METACOGNITIVE')
    expect(observation.tier).toBe('T2')
    expect(observation.signal).toContain(receipt.route_digest)
    expect(observation.signal).toContain('authority=NONE')
    expect(observation.signal).not.toContain('T0')
  })

  it('does not expose an executor or command runner injection seam in the planner API', async () => {
    const source = routePolyglotTask.toString()
    expect(source).not.toContain('executor')
    expect(source).not.toContain('commandRunner')
  })
})
