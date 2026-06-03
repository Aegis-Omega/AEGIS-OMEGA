// ============================================================
// SOVEREIGN OMEGA — runDecisionPipeline tests
// EPISTEMIC TIER: T2
//
// Tests for src/pipeline/index.ts
//
// Strategy: mock all external I/O (verifiers, replay, VCG,
// budget manager, e1 ambiguity, store) so tests are pure unit
// tests with no IndexedDB or real API calls.
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import type { AmbiguityAssessment } from '../../src/pipeline/e1.js'
import type { ExecutionResult } from '../../src/verifier/execute.js'
import type { VCGMetric, Confidence, SHA256Hex } from '../../src/core/types.js'

// ── Hoisted mock refs ─────────────────────────────────────

const mocks = vi.hoisted(() => ({
  assessAmbiguity:  vi.fn<() => AmbiguityAssessment>(),
  executeVerifiers: vi.fn<() => Promise<ExecutionResult>>(),
  replayProjection: vi.fn(),
  vcgIsStale:        vi.fn<() => boolean>(),
  vcgShouldSuspend:  vi.fn<() => boolean>(),
  vcgCompute:        vi.fn<() => VCGMetric>(),
  vcgGetEpochId:     vi.fn<() => string>(),
  vcgAddResult:      vi.fn(),
  buildConfidence:   vi.fn<() => Confidence>(),
  budgetEvaluate:    vi.fn(),
}))

// ── Module mocks ──────────────────────────────────────────

vi.mock('../../src/pipeline/e1.js', () => ({
  assessAmbiguity: mocks.assessAmbiguity,
  createInitialDialogueState: (_sessionId: string) => ({
    referents:   [],
    constraints: [],
    turn_count:  0,
    session_id:  _sessionId,
  }),
}))

vi.mock('../../src/verifier/execute.js', () => ({
  executeVerifiers: mocks.executeVerifiers,
}))

vi.mock('../../src/event/replay.js', () => ({
  replayProjection: mocks.replayProjection,
}))

vi.mock('../../src/calibration/vcg.js', () => {
  class MockVCGTracker {
    addResult     = mocks.vcgAddResult
    isStale       = mocks.vcgIsStale
    shouldSuspend = mocks.vcgShouldSuspend
    compute       = mocks.vcgCompute
    getEpochId    = mocks.vcgGetEpochId
    constructor(_dummy?: unknown) {}
  }
  return {
    VCGTracker:     MockVCGTracker,
    buildConfidence: mocks.buildConfidence,
  }
})

vi.mock('../../src/gate/risk.js', () => {
  class MockRiskBudgetManager {
    evaluate = mocks.budgetEvaluate
    constructor(_dummy?: unknown) {}
  }
  return { RiskBudgetManager: MockRiskBudgetManager }
})

import { runDecisionPipeline } from '../../src/pipeline/index.js'
import type { PipelineInput, PipelineDependencies } from '../../src/pipeline/index.js'
import { VCGTracker } from '../../src/calibration/vcg.js'
import { RiskBudgetManager } from '../../src/gate/risk.js'
import { EventType, CalibrationDomain } from '../../src/core/types.js'
import type { EventStore } from '../../src/event/store.js'
import type { SequenceNumber, UUIDv7 } from '../../src/core/types.js'
import type { VerifierOutput } from '../../src/verifier/types.js'

afterEach(() => vi.clearAllMocks())

// ── Fixtures ──────────────────────────────────────────────

const FIXED_TS = 1_600_000_000_000
const ZERO_HASH = '0'.repeat(64) as SHA256Hex
const SESSION_ID = '01900000-0000-7000-8000-000000000001' as UUIDv7

const PINS = {
  schema_version:             '1.0.0',
  verifier_versions:          {},
  calibration_model_version:  '1.0.0',
  projection_compiler_version: '1.0.0',
  k_measurement_version:      '1.0.0',
}

const FAKE_VCG_METRIC: VCGMetric = {
  domain_id:            'test-domain',
  weighted_error:       0.05,
  bootstrap_ci_95:      [0.01, 0.09],
  effective_sample_size: 10,
  decay_factor:         1,
  sample_count:         10,
  epoch_start_ms:       FIXED_TS,
}

const FAKE_CONFIDENCE: Confidence = {
  type:       'heuristic',
  value:      0.5,
  disclaimer: true,
  source:     'LOW_SAMPLE',
}

const FAKE_PROJECTION_STATE = {
  score_accumulator:          [70],
  strengths:                  ['A', 'B', 'C'],
  risks:                      ['X', 'Y', 'Z'],
  positioning_candidates:     [['leader', 0.8]] as [string, number][],
  ground_truth_refs:          [],
  retrieval_context_hashes:   [],
  confidence_type:            'heuristic' as const,
  projection_version:         '1.0.0',
  last_updated_sequence:      1n as SequenceNumber,
}

const ACCEPTED_GATE = {
  proposal_id:      'prop-1',
  component_id:     'pipeline-main',
  lcb_value:        0.1,
  e_value:          0.1,
  delta_metric:     0.5,
  sample_size:      1,
  accepted:         true,
  risk_spent:       0.01,
  budget_remaining: 0.99,
  freeze_triggered: false,
  method:           'anytime_valid_bernstein' as const,
}

const NO_CLARIFICATION: AmbiguityAssessment = {
  requires_clarification:     false,
  divergence_score:           0.1,
  detected_types:             [],
  cost_of_proceeding:         0.1,
  cost_of_clarifying:         0.5,
  escalate_to_structured_form: false,
}

const EMPTY_EXECUTION: ExecutionResult = {
  outputs:            [],
  calibration_eligible: [],
  advisory_only:      [],
  correlation_matrix: {},
  correlation_alert:  false,
}

function makeStore() {
  const appendFn = vi.fn().mockResolvedValue({
    event_id:              'eid' as UUIDv7,
    stream_id:             SESSION_ID,
    event_type:            EventType.AMBIGUITY_ROUTED,
    timestamp_ms:          FIXED_TS,
    sequence:              1n as SequenceNumber,
    producer_id:           'pipeline',
    producer_version:      '1.0.0',
    payload_schema_version: '1.0.0',
    payload:               {},
    prev_hash:             ZERO_HASH,
    self_hash:             ZERO_HASH,
    retention_class:       'REGULATED' as const,
  })
  const getAllFn = vi.fn().mockResolvedValue([])
  return {
    store:    { append: appendFn, getAll: getAllFn } as unknown as EventStore,
    appendFn, getAllFn,
  }
}

function makeDeps(): {
  deps: PipelineDependencies
  appendFn: ReturnType<typeof vi.fn>
  getAllFn: ReturnType<typeof vi.fn>
} {
  const { store, appendFn, getAllFn } = makeStore()
  // Constructors are mocked; arguments satisfy the real type signatures
  const vcgTracker    = new VCGTracker('test-stream')
  const budgetManager = new RiskBudgetManager(FIXED_TS)
  return {
    deps: { store, vcgTracker, budgetManager, pins: PINS } as PipelineDependencies,
    appendFn,
    getAllFn,
  }
}

const FAKE_VERIFIER_OUTPUT: VerifierOutput = {
  verifier_id:       'v-test',
  claim_id:          'claim-test',
  passed:            true,
  raw_confidence:    0.8,
  evidence_refs:     [],
  latency_ms:        10,
  determinism_flag:  true,
  verifier_version:  '1.0.0',
  trust_class:       CalibrationDomain.GROUND_TRUTH,
  artifact_hash:     ZERO_HASH,
}

const VERIFIER_EXECUTION: ExecutionResult = {
  outputs:              [FAKE_VERIFIER_OUTPUT],
  calibration_eligible: [FAKE_VERIFIER_OUTPUT],
  advisory_only:        [],
  correlation_matrix:   {},
  correlation_alert:    false,
}

const BASE_INPUT: PipelineInput = {
  session_id:          SESSION_ID,
  content:             'Run the analysis',
  domain:              'governance',
  verifier_ids:        [],
  request_timestamp_ms: FIXED_TS,
}

// ── Tests ────────────────────────────────────────────────

describe('runDecisionPipeline — clarification path', () => {
  it('returns conservative schema when requires_clarification=true (no escalation)', async () => {
    mocks.assessAmbiguity.mockReturnValue({
      ...NO_CLARIFICATION,
      requires_clarification: true,
      escalate_to_structured_form: false,
    })
    const { deps, appendFn } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)

    // Should log AMBIGUITY_ROUTED event
    const call = appendFn.mock.calls[0]
    expect(call![0]).toBe(EventType.AMBIGUITY_ROUTED)
    // Returns a conservative schema
    expect(result.confidence.type).toBe('heuristic')
    expect(result.schema_version).toBeDefined()
  })

  it('returns conservative schema when requires_clarification=true with escalation', async () => {
    mocks.assessAmbiguity.mockReturnValue({
      ...NO_CLARIFICATION,
      requires_clarification: true,
      escalate_to_structured_form: true,
    })
    const { deps, appendFn } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)

    expect(appendFn.mock.calls[0]![0]).toBe(EventType.AMBIGUITY_ROUTED)
    expect(result.confidence.type).toBe('heuristic')
  })

  it('does not call executeVerifiers when clarification is required', async () => {
    mocks.assessAmbiguity.mockReturnValue({ ...NO_CLARIFICATION, requires_clarification: true })
    const { deps } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)
    expect(mocks.executeVerifiers).not.toHaveBeenCalled()
  })
})

describe('runDecisionPipeline — VCG suspension', () => {
  beforeEach(() => {
    mocks.assessAmbiguity.mockReturnValue(NO_CLARIFICATION)
    mocks.executeVerifiers.mockResolvedValue(EMPTY_EXECUTION)
    mocks.vcgIsStale.mockReturnValue(false)
    mocks.vcgShouldSuspend.mockReturnValue(true)
    mocks.vcgCompute.mockReturnValue(FAKE_VCG_METRIC)
    mocks.vcgGetEpochId.mockReturnValue('epoch-test')
    mocks.buildConfidence.mockReturnValue(FAKE_CONFIDENCE)
  })

  it('returns conservative schema (VCG_SUSPENSION) when shouldSuspend=true', async () => {
    const { deps, appendFn } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.CALIBRATION_ALERT)
    expect(result.confidence.type).toBe('heuristic')
  })

  it('does not call replayProjection when VCG suspended', async () => {
    const { deps } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)
    expect(mocks.replayProjection).not.toHaveBeenCalled()
  })
})

describe('runDecisionPipeline — isStale logging', () => {
  beforeEach(() => {
    mocks.assessAmbiguity.mockReturnValue(NO_CLARIFICATION)
    mocks.executeVerifiers.mockResolvedValue(EMPTY_EXECUTION)
    mocks.vcgIsStale.mockReturnValue(true)
    mocks.vcgShouldSuspend.mockReturnValue(false)
    mocks.vcgCompute.mockReturnValue(FAKE_VCG_METRIC)
    mocks.vcgGetEpochId.mockReturnValue('epoch-test')
    mocks.buildConfidence.mockReturnValue(FAKE_CONFIDENCE)
    mocks.budgetEvaluate.mockReturnValue(ACCEPTED_GATE)
    mocks.replayProjection.mockResolvedValue(FAKE_PROJECTION_STATE)
  })

  it('logs CALIBRATION_STALE when isStale=true but continues pipeline', async () => {
    const { deps, appendFn } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.CALIBRATION_STALE)
    expect(result.schema_version).toBeDefined()
  })
})

describe('runDecisionPipeline — gate rejection', () => {
  beforeEach(() => {
    mocks.assessAmbiguity.mockReturnValue(NO_CLARIFICATION)
    mocks.executeVerifiers.mockResolvedValue(EMPTY_EXECUTION)
    mocks.vcgIsStale.mockReturnValue(false)
    mocks.vcgShouldSuspend.mockReturnValue(false)
    mocks.vcgCompute.mockReturnValue(FAKE_VCG_METRIC)
    mocks.vcgGetEpochId.mockReturnValue('epoch-test')
    mocks.buildConfidence.mockReturnValue(FAKE_CONFIDENCE)
    mocks.budgetEvaluate.mockReturnValue({
      ...ACCEPTED_GATE,
      accepted:         false,
      rejection_reason: 'LCB_FAIL' as const,
    })
  })

  it('returns conservative schema when gate rejects', async () => {
    const { deps, appendFn } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.GATE_EVALUATED)
    expect(result.confidence.type).toBe('heuristic')
  })

  it('does not call replayProjection when gate rejected', async () => {
    const { deps } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)
    expect(mocks.replayProjection).not.toHaveBeenCalled()
  })

  it('uses GATE_REJECTED fallback when rejection_reason is absent', async () => {
    // rejection_reason is optional; omitting it exercises the ?? 'GATE_REJECTED' branch
    const noReason = { ...ACCEPTED_GATE, accepted: false, rejection_reason: undefined }
    mocks.budgetEvaluate.mockReturnValue(noReason)
    const { deps } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)
    expect(result.confidence.type).toBe('heuristic')
  })
})

describe('runDecisionPipeline — happy path', () => {
  beforeEach(() => {
    mocks.assessAmbiguity.mockReturnValue(NO_CLARIFICATION)
    mocks.executeVerifiers.mockResolvedValue(EMPTY_EXECUTION)
    mocks.vcgIsStale.mockReturnValue(false)
    mocks.vcgShouldSuspend.mockReturnValue(false)
    mocks.vcgCompute.mockReturnValue(FAKE_VCG_METRIC)
    mocks.vcgGetEpochId.mockReturnValue('epoch-test')
    mocks.buildConfidence.mockReturnValue(FAKE_CONFIDENCE)
    mocks.budgetEvaluate.mockReturnValue(ACCEPTED_GATE)
    mocks.replayProjection.mockResolvedValue(FAKE_PROJECTION_STATE)
  })

  it('returns a DecisionSchema with schema_version set', async () => {
    const { deps } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)
    expect(typeof result.schema_version).toBe('string')
    expect(result.schema_version.length).toBeGreaterThan(0)
  })

  it('logs VCG_COMPUTED and SYSTEM_OUTPUT events on happy path', async () => {
    const { deps, appendFn } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.VCG_COMPUTED)
    expect(eventTypes).toContain(EventType.SYSTEM_OUTPUT)
    expect(eventTypes).toContain(EventType.GATE_EVALUATED)
  })

  it('calls replayProjection with events from store.getAll()', async () => {
    const fakeEvents = [{ event_type: EventType.VCG_COMPUTED }]
    const { deps, getAllFn } = makeDeps()
    getAllFn.mockResolvedValue(fakeEvents)

    await runDecisionPipeline(BASE_INPUT, deps)
    expect(mocks.replayProjection).toHaveBeenCalledWith(fakeEvents, PINS)
  })

  it('passes vcg_at_emission in DecisionSchema from vcgTracker.compute()', async () => {
    const { deps } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)
    expect(result.vcg_at_emission).toBe(FAKE_VCG_METRIC.weighted_error)
  })

  it('logs VERIFIER_EVALUATED and calls vcgTracker.addResult for each calibration_eligible result', async () => {
    mocks.executeVerifiers.mockResolvedValue(VERIFIER_EXECUTION)
    const { deps, appendFn } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.VERIFIER_EVALUATED)
    expect(mocks.vcgAddResult).toHaveBeenCalledOnce()
  })

  it('uses raw_confidence=null fallback (0.5) when verifier has no confidence', async () => {
    const noConf: VerifierOutput = { ...FAKE_VERIFIER_OUTPUT, raw_confidence: null }
    mocks.executeVerifiers.mockResolvedValue({
      ...VERIFIER_EXECUTION, calibration_eligible: [noConf],
    })
    const { deps } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)
    // addResult called with 0.5 fallback
    expect(mocks.vcgAddResult.mock.calls[0]![1]).toBe(0.5)
  })

  it('covers improvement=0 branch when verifier passes=false', async () => {
    const failing: VerifierOutput = { ...FAKE_VERIFIER_OUTPUT, passed: false }
    mocks.executeVerifiers.mockResolvedValue({
      ...VERIFIER_EXECUTION, calibration_eligible: [failing],
    })
    const { deps } = makeDeps()
    const result = await runDecisionPipeline(BASE_INPUT, deps)
    expect(result.schema_version).toBeDefined()
  })
})

describe('runDecisionPipeline — correlation alert', () => {
  it('logs VERIFIER_CORRELATION_ALERT when correlation_alert=true', async () => {
    mocks.assessAmbiguity.mockReturnValue(NO_CLARIFICATION)
    mocks.executeVerifiers.mockResolvedValue({
      ...EMPTY_EXECUTION,
      correlation_alert: true,
    })
    mocks.vcgIsStale.mockReturnValue(false)
    mocks.vcgShouldSuspend.mockReturnValue(false)
    mocks.vcgCompute.mockReturnValue(FAKE_VCG_METRIC)
    mocks.vcgGetEpochId.mockReturnValue('epoch-test')
    mocks.buildConfidence.mockReturnValue(FAKE_CONFIDENCE)
    mocks.budgetEvaluate.mockReturnValue(ACCEPTED_GATE)
    mocks.replayProjection.mockResolvedValue(FAKE_PROJECTION_STATE)

    const { deps, appendFn } = makeDeps()
    await runDecisionPipeline(BASE_INPUT, deps)

    const eventTypes = appendFn.mock.calls.map(c => c[0])
    expect(eventTypes).toContain(EventType.VERIFIER_CORRELATION_ALERT)
  })
})
