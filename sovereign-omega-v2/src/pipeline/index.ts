// ============================================================
// SOVEREIGN OMEGA — Main Decision Pipeline
// EPISTEMIC TIER: T0 (pipeline orchestration)
// Execution order: E1 → E2 → E4 → Projection → Output
// All temporal semantics use event.timestamp_ms.
// Conservative fallback on any gate failure.
// ============================================================

import type {
  DecisionSchema, RuntimeVersionPin, UUIDv7,
} from '../core/types.js'
import { EventType as ET, RetentionClass as RC } from '../core/types.js'
import { EventStore } from '../event/store.js'
import { replayProjection } from '../event/replay.js'
import { VCGTracker, buildConfidence } from '../calibration/vcg.js'
import { RiskBudgetManager } from '../gate/risk.js'
import { executeVerifiers } from '../verifier/execute.js'
import { buildDecisionSchema, buildConservativeSchema } from './schema.js'
import { assessAmbiguity, createInitialDialogueState } from './e1.js'
import type { DialogueState } from '../core/types.js'
import { normalizeDelta } from '../core/types.js'
import { generateUUIDv7 } from '../event/uuid.js'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'

export interface PipelineInput {
  readonly session_id: UUIDv7
  readonly content: string
  readonly domain: string
  readonly verifier_ids: readonly string[]
  readonly request_timestamp_ms: number  // MUST be from event context, not Date.now()
}

export interface PipelineDependencies {
  readonly store: EventStore
  readonly vcgTracker: VCGTracker
  readonly budgetManager: RiskBudgetManager
  readonly pins: RuntimeVersionPin
  readonly dialogueState?: Readonly<DialogueState>
}

/**
 * Execute the full decision pipeline.
 * Returns a DecisionSchema derived from verifier-grounded projection state.
 *
 * Pipeline invariants:
 * - No Date.now() in core logic
 * - All state transitions logged to event substrate
 * - Conservative fallback on any gate failure
 * - Verifier results partitioned by trust class before calibration
 */
export async function runDecisionPipeline(
  input: PipelineInput,
  deps: PipelineDependencies
): Promise<DecisionSchema> {
  const { store, vcgTracker, budgetManager, pins } = deps
  const ts = input.request_timestamp_ms

  // ── E1: Ambiguity Routing ─────────────────────────────
  const dialogueState = deps.dialogueState ?? createInitialDialogueState(input.session_id)
  const divergence = assessAmbiguity(input.content, dialogueState, pins.embedding_model_version ?? 'none')

  if (divergence.requires_clarification) {
    await store.append(
      ET.AMBIGUITY_ROUTED,
      {
        session_id: input.session_id,
        divergence_score: divergence.divergence_score,
        detected_types: divergence.detected_types,
        escalate: divergence.escalate_to_structured_form,
      },
      'pipeline', pins.schema_version, pins.schema_version, RC.REGULATED, ts
    )
    return buildConservativeSchema(
      { type: 'heuristic', value: 0.3, disclaimer: true, source: 'CLARIFICATION_REQUIRED' },
      divergence.escalate_to_structured_form ? 'ESCALATED_TO_STRUCTURED_FORM' : 'CLARIFICATION_REQUIRED'
    )
  }

  // ── E2: Verifier Execution & Calibration ──────────────
  const executionResult = await executeVerifiers(
    { claim_id: generateUUIDv7(), domain: input.domain, content: input.content },
    [...input.verifier_ids]
  )

  // Log correlation alert if detected
  if (executionResult.correlation_alert) {
    await store.append(ET.VERIFIER_CORRELATION_ALERT, { domain: input.domain }, 'pipeline', pins.schema_version, pins.schema_version, RC.REGULATED, ts)
  }

  // Add calibration-eligible results to VCG tracker
  for (const result of executionResult.calibration_eligible) {
    const claimed = result.raw_confidence ?? 0.5
    vcgTracker.addResult(result, claimed, ts)

    await store.append(ET.VERIFIER_EVALUATED, result, 'verifier', pins.verifier_versions[result.verifier_id] ?? 'unknown', pins.schema_version, RC.REGULATED, ts)
  }

  // Check VCG alerts
  if (vcgTracker.isStale(ts)) {
    await store.append(ET.CALIBRATION_STALE, { domain: input.domain }, 'pipeline', pins.schema_version, pins.schema_version, RC.REGULATED, ts)
  }
  if (vcgTracker.shouldSuspend(ts)) {
    await store.append(ET.CALIBRATION_ALERT, { vcg_above_suspend_threshold: true }, 'pipeline', pins.schema_version, pins.schema_version, RC.REGULATED, ts)
    return buildConservativeSchema({ type: 'heuristic', value: 0.1, disclaimer: true, source: 'VCG_SUSPENSION' })
  }

  const confidence = buildConfidence(vcgTracker, ts, executionResult.calibration_eligible.map(r => r.verifier_id))
  const vcgMetric = vcgTracker.compute(ts)

  await store.append(ET.VCG_COMPUTED, { vcg_epoch_id: vcgTracker.getEpochId(), weighted_error: vcgMetric.weighted_error }, 'calibration', pins.calibration_model_version, pins.schema_version, RC.REGULATED, ts)

  // ── E4: Sequential Gate ───────────────────────────────
  const proposalId = generateUUIDv7()
  const deltaMetrics = executionResult.calibration_eligible.map(r => {
    const baseline = 0.5
    const improvement = (r.passed ? 1 : 0) - baseline
    return normalizeDelta(improvement)
  })

  const gateDecision = budgetManager.evaluate(
    proposalId,
    'pipeline-main',
    deltaMetrics,
    1,  // deltaK = 1 for standard inference
    ts
  )

  await store.append(ET.GATE_EVALUATED, gateDecision, 'gate', pins.schema_version, pins.schema_version, RC.LEGAL_HOLD, ts)

  if (!gateDecision.accepted) {
    return buildConservativeSchema(
      { type: 'heuristic', value: 0.3, disclaimer: true, source: gateDecision.rejection_reason ?? 'GATE_REJECTED' }
    )
  }

  // ── Projection: Version-Pinned Deterministic Replay ──
  const events = await store.getAll()
  const projectionState = await replayProjection(events, pins)

  // Log output with hash
  const canonical = canonicalizeJCS({
    score: projectionState.score_accumulator,
    confidence: confidence.type,
  })
  const outputHash = await sha256Hex(canonical)

  await store.append(
    ET.SYSTEM_OUTPUT,
    {
      output_hash: outputHash,
      confidence_type: confidence.type,
      vcg_at_emission: vcgMetric.weighted_error,
    },
    'pipeline', pins.schema_version, pins.schema_version, RC.REGULATED, ts
  )

  return buildDecisionSchema(projectionState, confidence, vcgMetric.weighted_error)
}
