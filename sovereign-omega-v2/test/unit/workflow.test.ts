// ============================================================
// SOVEREIGN OMEGA — Cognitive Workflow Recorder Tests (E5)
// Verifies: replay-safety gate fires before any store write,
// all 8 E5 payload instances are replay-safe, non-E5 event
// types are rejected, and store.append receives correct args.
// ============================================================

import { describe, it, expect, vi } from 'vitest'
import {
  recordWorkflowEvent,
  E5_PRODUCER_ID, E5_PRODUCER_VERSION, E5_SCHEMA_VERSION,
  type AppendCapable,
} from '../../src/event/workflow-recorder'
import { isReplaySafe, ReplaySafetyViolation } from '../../src/core/semantics'
import { EventType, RetentionClass, CapabilityClass } from '../../src/core/types'
import type {
  AgentPatchProposedPayload, GateResultRecordedPayload,
  CorpusNodeAccessedPayload, SubagentDelegatedPayload,
  SubagentResultReceivedPayload, GuardianInvokedPayload,
  GuardianVerdictPayload, SemanticNodeQueriedPayload,
} from '../../src/event/workflow'

const FIXED_TS = 1_600_000_000_000
const ZERO_HASH = '0'.repeat(64) as any

function makeStore(): { store: AppendCapable; appendSpy: ReturnType<typeof vi.fn> } {
  const appendSpy = vi.fn().mockResolvedValue({
    event_id: 'test-event-id' as any,
    stream_id: 'test-stream' as any,
    event_type: EventType.GATE_RESULT_RECORDED,
    timestamp_ms: FIXED_TS,
    sequence: 0n as any,
    producer_id: E5_PRODUCER_ID,
    producer_version: E5_PRODUCER_VERSION,
    payload_schema_version: E5_SCHEMA_VERSION,
    payload: {},
    prev_hash: ZERO_HASH,
    self_hash: ZERO_HASH,
    retention_class: RetentionClass.STANDARD,
  })
  return { store: { append: appendSpy }, appendSpy }
}

// ─── Fixture payloads — one concrete instance per E5 type ──

const agentPatch: AgentPatchProposedPayload = {
  agent_id: 'claude:orchestration',
  agent_class: CapabilityClass.ORCHESTRATION,
  files_modified: ['src/core/fixedpoint.ts'],
  gate_required: 6,
  tier_ceiling_violated: false,
  diff_hash: ZERO_HASH,
}

const gateResult: GateResultRecordedPayload = {
  gate_number: 8,
  command: 'npm run test && npm run typecheck && npm run build',
  passed: true,
  pass_count: 133,
  failure_output: null,
  decision: 'PROCEED',
  halt_reason: null,
}

const corpusAccess: CorpusNodeAccessedPayload = {
  agent_id: 'claude:orchestration',
  drive_file_id: '1cfFY59zAczNPCL7mvr_TxFo1yR7xfDNh',
  document_name: 'SOVEREIGN_OMEGA_INTEGRATED_SPEC_v2.md',
  epistemic_tier: 1,
  purpose: 'spec compliance check before writing workflow-recorder.ts',
}

const subagentDelegated: SubagentDelegatedPayload = {
  delegating_agent_id: 'claude:orchestration',
  subagent_id: 'explore:bernstein-fuzz',
  subagent_type: 'Explore',
  semantic_scope: ['src/core/fixedpoint.ts', 'test/determinism/bernstein-q32-fuzz.test.ts'],
  authority_class: CapabilityClass.INFERENCE,
  task_hash: ZERO_HASH,
}

const subagentResult: SubagentResultReceivedPayload = {
  subagent_id: 'explore:bernstein-fuzz',
  parent_delegation_id: '01900000-0000-7000-8000-000000000001' as any,
  succeeded: true,
  result_hash: ZERO_HASH,
  files_affected: ['src/core/fixedpoint.ts'],
}

const guardianInvoked: GuardianInvokedPayload = {
  invoked_by: 'claude:orchestration',
  check_reason: 'FROZEN_FILE_CHECK',
  files_under_review: ['sovereign-omega-v2/python/gate.py'],
}

const guardianVerdict: GuardianVerdictPayload = {
  verdict: 'APPROVED',
  check_performed: 'FROZEN_FILE_CHECK',
  location: 'sovereign-omega-v2/python/gate.py',
  reason: 'Hash matches constitutional record — no modification detected',
  invocation_event_id: '01900000-0000-7000-8000-000000000002' as any,
}

const nodeQueried: SemanticNodeQueriedPayload = {
  query_type: 'lookupNode',
  query_parameter: 'src/core/canonicalize.ts',
  result_count: 1,
}

// ─── Tests ────────────────────────────────────────────────

describe('Workflow Event Recorder (E5) — Ω⁵.8', () => {

  it('all 8 E5 payload instances pass isReplaySafe', () => {
    expect(isReplaySafe(agentPatch), 'AgentPatchProposedPayload').toBe(true)
    expect(isReplaySafe(gateResult), 'GateResultRecordedPayload').toBe(true)
    expect(isReplaySafe(corpusAccess), 'CorpusNodeAccessedPayload').toBe(true)
    expect(isReplaySafe(subagentDelegated), 'SubagentDelegatedPayload').toBe(true)
    expect(isReplaySafe(subagentResult), 'SubagentResultReceivedPayload').toBe(true)
    expect(isReplaySafe(guardianInvoked), 'GuardianInvokedPayload').toBe(true)
    expect(isReplaySafe(guardianVerdict), 'GuardianVerdictPayload').toBe(true)
    expect(isReplaySafe(nodeQueried), 'SemanticNodeQueriedPayload').toBe(true)
  })

  it('rejects non-replay-safe payloads with ReplaySafetyViolation before calling store', async () => {
    const { store, appendSpy } = makeStore()
    const badPayload = { value: NaN }

    await expect(
      recordWorkflowEvent(store, EventType.GATE_RESULT_RECORDED, badPayload, FIXED_TS)
    ).rejects.toThrow(ReplaySafetyViolation)

    expect(appendSpy).not.toHaveBeenCalled()
  })

  it('rejects function payloads — ReplaySafetyViolation, store not called', async () => {
    const { store, appendSpy } = makeStore()
    await expect(
      recordWorkflowEvent(store, EventType.AGENT_PATCH_PROPOSED, () => {}, FIXED_TS)
    ).rejects.toThrow(ReplaySafetyViolation)
    expect(appendSpy).not.toHaveBeenCalled()
  })

  it('rejects non-E5 event types with RangeError', async () => {
    const { store } = makeStore()
    await expect(
      recordWorkflowEvent(store, EventType.SYSTEM_INIT, {}, FIXED_TS)
    ).rejects.toThrow(RangeError)
    await expect(
      recordWorkflowEvent(store, EventType.VCG_COMPUTED, {}, FIXED_TS)
    ).rejects.toThrow(RangeError)
  })

  it('calls store.append with correct producer metadata for a safe payload', async () => {
    const { store, appendSpy } = makeStore()

    await recordWorkflowEvent(store, EventType.GATE_RESULT_RECORDED, gateResult, FIXED_TS)

    expect(appendSpy).toHaveBeenCalledOnce()
    const [event_type, payload, producer_id, producer_version, schema_version, retention, ts] =
      appendSpy.mock.calls[0]!
    expect(event_type).toBe(EventType.GATE_RESULT_RECORDED)
    expect(payload).toBe(gateResult)
    expect(producer_id).toBe(E5_PRODUCER_ID)
    expect(producer_version).toBe(E5_PRODUCER_VERSION)
    expect(schema_version).toBe(E5_SCHEMA_VERSION)
    expect(retention).toBe(RetentionClass.STANDARD)
    expect(ts).toBe(FIXED_TS)
  })

  it('propagates store errors without swallowing them', async () => {
    const failStore: AppendCapable = {
      append: vi.fn().mockRejectedValue(new Error('IDB_WRITE_FAILED')),
    }
    await expect(
      recordWorkflowEvent(failStore, EventType.SEMANTIC_NODE_QUERIED, nodeQueried, FIXED_TS)
    ).rejects.toThrow('IDB_WRITE_FAILED')
  })

  it('all 8 E5 types are accepted — none throw RangeError', async () => {
    const { store } = makeStore()
    const cases: [EventType, unknown][] = [
      [EventType.AGENT_PATCH_PROPOSED, agentPatch],
      [EventType.GATE_RESULT_RECORDED, gateResult],
      [EventType.CORPUS_NODE_ACCESSED, corpusAccess],
      [EventType.SUBAGENT_DELEGATED, subagentDelegated],
      [EventType.SUBAGENT_RESULT_RECEIVED, subagentResult],
      [EventType.GUARDIAN_INVOKED, guardianInvoked],
      [EventType.GUARDIAN_VERDICT_ISSUED, guardianVerdict],
      [EventType.SEMANTIC_NODE_QUERIED, nodeQueried],
    ]
    for (const [et, payload] of cases) {
      await expect(
        recordWorkflowEvent(store, et, payload, FIXED_TS)
      ).resolves.toBeDefined()
    }
  })

  it('circular reference payload is rejected — ReplaySafetyViolation, store not called', async () => {
    const { store, appendSpy } = makeStore()
    const circular: Record<string, unknown> = { x: 1 }
    circular['self'] = circular
    await expect(
      recordWorkflowEvent(store, EventType.CORPUS_NODE_ACCESSED, circular, FIXED_TS)
    ).rejects.toThrow(ReplaySafetyViolation)
    expect(appendSpy).not.toHaveBeenCalled()
  })

})
