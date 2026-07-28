// ============================================================
// AEGIS Holonñgram Visual Feedback Compiler V1
// EPISTEMIC STATUS: DERIVED_NON_AUTHORITATIVE
//
// A fresh, independently verified receipt chain is the only admissible source.
// The output is a read-only visual projection: it cannot grant authority,
// execute a mutation, promote evidence, or authorize a route adjustment.
// ============================================================

import { canonicalizeJCS, canonicalizeJCSString } from '../core/canonicalize.js'
import { sha256Hex } from '../core/hashing.js'
import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import {
  assertCrossRuntimeReceiptIdV1,
  normalizeCrossRuntimeReceiptEnvelopeV1,
} from '../provenance/cross-runtime-receipts.js'
import type {
  AuthorityLevelV1,
  CrossRuntimeReceiptEnvelopeV1,
  CrossRuntimeReceiptKindV1,
  CrossRuntimeReceiptOutcomeV1,
  DecimalStringV1,
} from '../provenance/cross-runtime-receipts.js'
import {
  resolveAndVerifyCrossRuntimeReceiptChainV1,
} from '../provenance/receipt-resolver.js'
import type {
  CrossRuntimeReceiptSourceV1,
  CrossRuntimeReceiptVerificationDecisionV1,
  TrustedReceiptResolutionContextV1,
} from '../provenance/receipt-resolver.js'

export const HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION = '1.0.0' as const
export const HOLONNGRAM_ARTIFACT_KIND =
  'AEGIS_HOLONNGRAM_VISUAL_FEEDBACK_V1' as const
export const HOLONNGRAM_COMPILER_VERSION = 'holonngram-compiler-v1' as const
export const HOLONNGRAM_TOPOLOGY_ID = 'HOLONNGRAM_19_V1' as const
export const HOLONNGRAM_FRAME_DOMAIN =
  'AEGIS_HOLONNGRAM_VISUAL_FEEDBACK_FRAME_V1' as const
export const HOLONNGRAM_FORMULA_INPUT_DOMAIN =
  'AEGIS_HOLONNGRAM_FORMULA_INPUT_V1' as const
export const HOLONNGRAM_FORMULA_OUTPUT_DOMAIN =
  'AEGIS_HOLONNGRAM_FORMULA_OUTPUT_V1' as const
export const HOLONNGRAM_FORMULA_TRACE_DOMAIN =
  'AEGIS_HOLONNGRAM_FORMULA_TRACE_V1' as const

export const HOLONNGRAM_NODE_DEFINITIONS_V1 = deepFreeze([
  { node_id: 'C0', ring: 'CENTER', role: 'CURRENT_ENVELOPE' },
  { node_id: 'I1', ring: 'INNER', role: 'INTERPRETER' },
  { node_id: 'I2', ring: 'INNER', role: 'ASSESSOR' },
  { node_id: 'I3', ring: 'INNER', role: 'LEASE_GUARD' },
  { node_id: 'I4', ring: 'INNER', role: 'EXECUTOR' },
  { node_id: 'I5', ring: 'INNER', role: 'VERIFIER' },
  { node_id: 'I6', ring: 'INNER', role: 'COMMITTER' },
  { node_id: 'O1', ring: 'OUTER', role: 'ACTOR_WITNESS' },
  { node_id: 'O2', ring: 'OUTER', role: 'SESSION_WITNESS' },
  { node_id: 'O3', ring: 'OUTER', role: 'WORKSPACE_WITNESS' },
  { node_id: 'O4', ring: 'OUTER', role: 'HOLON_WITNESS' },
  { node_id: 'O5', ring: 'OUTER', role: 'AUTHORITY_WITNESS' },
  { node_id: 'O6', ring: 'OUTER', role: 'LEASE_WITNESS' },
  { node_id: 'O7', ring: 'OUTER', role: 'FENCE_WITNESS' },
  { node_id: 'O8', ring: 'OUTER', role: 'EXPECTED_STATE_WITNESS' },
  { node_id: 'O9', ring: 'OUTER', role: 'OBSERVED_STATE_WITNESS' },
  { node_id: 'O10', ring: 'OUTER', role: 'ACTION_WITNESS' },
  { node_id: 'O11', ring: 'OUTER', role: 'RESULT_WITNESS' },
  { node_id: 'O12', ring: 'OUTER', role: 'TRUST_CHAIN_WITNESS' },
] as const)

export type HolonngramNodeIdV1 =
  typeof HOLONNGRAM_NODE_DEFINITIONS_V1[number]['node_id']
export type HolonngramNodeRingV1 =
  typeof HOLONNGRAM_NODE_DEFINITIONS_V1[number]['ring']
export type HolonngramNodeRoleV1 =
  typeof HOLONNGRAM_NODE_DEFINITIONS_V1[number]['role']
export type HolonngramNodeStateV1 =
  | 'IDLE'
  | 'ACTIVE'
  | 'VERIFIED'
  | 'DENIED'
  | 'EXPIRED'
  | 'REVOKED'
  | 'CANCELLED'
  | 'FAILED'
  | 'CHANGED'
  | 'UNCHANGED'
export type HolonngramMeasurementStatusV1 =
  | 'NOT_COMPUTED'
  | 'CALLER_SUPPLIED_UNVERIFIED'
export type HolonngramFormulaExecutionStatusV1 =
  | 'NOT_EXECUTED'
  | 'UNVERIFIED_CALLER_INPUT'
export type HolonngramDeltaTypeV1 =
  | 'MATCH'
  | 'STATE_CHANGED'
  | 'STALE_EXPECTATION'
  | 'DENIED'
  | 'CANCELLED'
  | 'FAILED'
  | 'EXPIRED'
  | 'REVOKED'
export type HolonngramFeedbackSignalV1 =
  | 'REINFORCE'
  | 'NEEDS_REVIEW'
  | 'REQUEST_GRANT'
  | 'REPAIR_SCHEMA'
  | 'ROLLBACK'
  | 'FAIL_CLOSED'
export type HolonngramSeverityV1 =
  | 'INFO'
  | 'REVIEW'
  | 'WARNING'
  | 'CRITICAL'
  | 'FATAL'
export type HolonngramBoundaryV1 =
  | 'NONE'
  | 'AUTHORITY'
  | 'LEASE'
  | 'FENCING'
  | 'STATE'
  | 'SCHEMA'
  | 'TRUST'
  | 'REPLAY'
  | 'CANCELLATION'
  | 'EXECUTION'
export type HolonngramEdgeKindV1 =
  | 'FLOW'
  | 'AUTHORITY'
  | 'TRUST'
  | 'STATE'
  | 'PROVENANCE'
  | 'FEEDBACK'

export interface HolonngramCompilerInputV1 {
  readonly schema_version: typeof HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION
  readonly compiler_version: typeof HOLONNGRAM_COMPILER_VERSION
  readonly formula_id: string
  readonly formula_version: string
  readonly formula_definition_digest: SHA256Hex
  readonly transition_id: string
  readonly measurement: {
    readonly status: HolonngramMeasurementStatusV1
    readonly resonance_ppm: DecimalStringV1 | null
    readonly value_delta_ppm: DecimalStringV1 | null
  }
  readonly edge_updates: readonly HolonngramEdgeUpdateV1[]
  readonly next_route: string
}

export interface HolonngramEdgeUpdateV1 {
  readonly from_node: HolonngramNodeIdV1
  readonly to_node: HolonngramNodeIdV1
  readonly edge_kind: HolonngramEdgeKindV1
  readonly measurement_status: HolonngramMeasurementStatusV1
  readonly trust_delta_ppm: DecimalStringV1 | null
  readonly risk_delta_ppm: DecimalStringV1 | null
  readonly schema_delta_ppm: DecimalStringV1 | null
  readonly authority_delta_ppm: DecimalStringV1 | null
  readonly basis_codes: readonly string[]
}

export interface HolonngramSourceV1 {
  readonly provenance_status: 'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED'
  readonly decision_digest: SHA256Hex
  readonly terminal_receipt_id: SHA256Hex
  readonly terminal_receipt_kind: CrossRuntimeReceiptKindV1
  readonly terminal_outcome: CrossRuntimeReceiptOutcomeV1
  readonly chain_digest: SHA256Hex
  readonly receipt_count: DecimalStringV1
  readonly registry_roots: readonly SHA256Hex[]
  readonly actor_identity_root: SHA256Hex
  readonly session_identity_root: SHA256Hex
  readonly workspace_identity_root: SHA256Hex
  readonly holon_identity_root: SHA256Hex
  readonly authority_domain: string
  readonly authority_level: AuthorityLevelV1
  readonly authority_receipt_hash: SHA256Hex
  readonly lease_id: SHA256Hex
  readonly lease_generation: DecimalStringV1
  readonly fencing_token: SHA256Hex
  readonly lease_authorization_receipt_hash: SHA256Hex
  readonly parent_receipt_hash: SHA256Hex
  readonly observed_state_root: SHA256Hex
  readonly expected_state_root: SHA256Hex
  readonly action_digest: SHA256Hex
  readonly before_state_root: SHA256Hex
  readonly after_state_root: SHA256Hex
  readonly result_digest: SHA256Hex
  readonly terminal_timestamp_ms: DecimalStringV1
  readonly terminal_nonce: string
  readonly denial_codes: readonly string[]
  readonly verifier_identity_root: SHA256Hex
  readonly observed_at_ms: DecimalStringV1
  readonly max_clock_skew_ms: DecimalStringV1
}

export interface HolonngramFormulaTraceV1 {
  readonly formula_id: string
  readonly formula_version: string
  readonly formula_definition_digest: SHA256Hex
  readonly transition_id: string
  readonly trace_id: SHA256Hex
  readonly input_digest: SHA256Hex
  readonly output_digest: SHA256Hex
  readonly execution_status: HolonngramFormulaExecutionStatusV1
  readonly measurement_status: HolonngramMeasurementStatusV1
}

export interface HolonngramStateComparisonV1 {
  readonly observed_state_root: SHA256Hex
  readonly expected_state_root: SHA256Hex
  readonly before_state_root: SHA256Hex
  readonly after_state_root: SHA256Hex
  readonly field_diff_status: 'ROOTS_ONLY'
  readonly delta_type: HolonngramDeltaTypeV1
}

export interface HolonngramFeedbackV1 {
  readonly signal: HolonngramFeedbackSignalV1
  readonly severity: HolonngramSeverityV1
  readonly boundary: HolonngramBoundaryV1
  readonly rationale_codes: readonly string[]
  readonly resonance: {
    readonly measurement_status: HolonngramMeasurementStatusV1
    readonly ppm: DecimalStringV1 | null
  }
  readonly value: {
    readonly measurement_status: HolonngramMeasurementStatusV1
    readonly delta_ppm: DecimalStringV1 | null
  }
}

export interface HolonngramVisualNodeV1 {
  readonly node_id: HolonngramNodeIdV1
  readonly ring: HolonngramNodeRingV1
  readonly role: HolonngramNodeRoleV1
  readonly state: HolonngramNodeStateV1
  readonly source_refs: readonly SHA256Hex[]
}

export interface HolonngramVisualV1 {
  readonly nodes: readonly HolonngramVisualNodeV1[]
  readonly edge_updates: readonly HolonngramEdgeUpdateV1[]
  readonly event: {
    readonly transition_id: string
    readonly terminal_receipt_id: SHA256Hex
    readonly terminal_receipt_kind: CrossRuntimeReceiptKindV1
    readonly terminal_outcome: CrossRuntimeReceiptOutcomeV1
    readonly severity: HolonngramSeverityV1
    readonly signal: HolonngramFeedbackSignalV1
  }
  readonly receipt_timeline: {
    readonly terminal_receipt_id: SHA256Hex
    readonly chain_digest: SHA256Hex
    readonly receipt_count: DecimalStringV1
  }
  readonly next_route: string
}

export interface HolonngramVisualFeedbackFrameV1 {
  readonly schema_version: typeof HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION
  readonly artifact_kind: typeof HOLONNGRAM_ARTIFACT_KIND
  readonly compiler_version: typeof HOLONNGRAM_COMPILER_VERSION
  readonly topology_id: typeof HOLONNGRAM_TOPOLOGY_ID
  readonly epistemic_status: 'DERIVED_NON_AUTHORITATIVE'
  readonly source: HolonngramSourceV1
  readonly formula_trace: HolonngramFormulaTraceV1
  readonly state_comparison: HolonngramStateComparisonV1
  readonly feedback: HolonngramFeedbackV1
  readonly visual: HolonngramVisualV1
  readonly safety: {
    readonly grants_authority: false
    readonly executes_mutation: false
    readonly promotes_evidence: false
    readonly claims_authoritative_provenance: false
    readonly route_adjustment_authorized: false
  }
  readonly frame_digest: SHA256Hex
}

export class HolonngramCompilerError extends Error {
  override readonly name = 'HolonngramCompilerError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

const HASH_PATTERN = /^[0-9a-f]{64}$/
const ZERO_HASH = '0'.repeat(64)
const SAFE_ID_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/
const DECIMAL_PATTERN = /^(0|[1-9][0-9]*)$/
const SIGNED_DECIMAL_PATTERN = /^-?(0|[1-9][0-9]*)$/
const MAX_DECIMAL_DIGITS = 20
const PPM_LIMIT = 1_000_000n
const MEASUREMENT_STATUSES = new Set<HolonngramMeasurementStatusV1>([
  'NOT_COMPUTED', 'CALLER_SUPPLIED_UNVERIFIED',
])
const EDGE_KINDS = new Set<HolonngramEdgeKindV1>([
  'FLOW', 'AUTHORITY', 'TRUST', 'STATE', 'PROVENANCE', 'FEEDBACK',
])
const NODE_STATES = new Set<HolonngramNodeStateV1>([
  'IDLE', 'ACTIVE', 'VERIFIED', 'DENIED', 'EXPIRED', 'REVOKED',
  'CANCELLED', 'FAILED', 'CHANGED', 'UNCHANGED',
])
const NODE_IDS = new Set<string>(
  HOLONNGRAM_NODE_DEFINITIONS_V1.map(definition => definition.node_id),
)

/**
 * Resolve the full signed chain, bind its terminal receipt, and compile a
 * deterministic visual projection. Verification failure produces no frame.
 */
export async function resolveAndCompileHolonngramVisualFeedbackV1(
  source: CrossRuntimeReceiptSourceV1,
  terminalReceiptId: SHA256Hex,
  context: TrustedReceiptResolutionContextV1,
  inputValue: unknown,
): Promise<HolonngramVisualFeedbackFrameV1> {
  const input = normalizeHolonngramCompilerInputV1(inputValue)
  const decision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
    source,
    terminalReceiptId,
    context,
  )
  const terminalValue = await source.resolveReceipt(terminalReceiptId)
  if (terminalValue === null) fail('verified terminal receipt disappeared before compilation')
  const terminal = normalizeCrossRuntimeReceiptEnvelopeV1(terminalValue)
  await assertCrossRuntimeReceiptIdV1(terminal)
  assertTerminalBinding(decision, terminal)

  const receiptSource = sourceFrom(decision, terminal)
  const stateComparison = deriveStateComparison(terminal)
  const feedback = deriveFeedback(terminal, input.measurement)
  const edgeUpdates = input.edge_updates
  const inputDigest = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_INPUT_DOMAIN,
    source: receiptSource,
  }))
  const outputDigest = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_OUTPUT_DOMAIN,
    state_comparison: stateComparison,
    feedback,
    edge_updates: edgeUpdates,
    next_route: input.next_route,
  }))
  const traceId = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_TRACE_DOMAIN,
    formula_id: input.formula_id,
    formula_version: input.formula_version,
    formula_definition_digest: input.formula_definition_digest,
    input_digest: inputDigest,
    output_digest: outputDigest,
  }))
  const formulaTrace = deepFreeze({
    formula_id: input.formula_id,
    formula_version: input.formula_version,
    formula_definition_digest: input.formula_definition_digest,
    transition_id: input.transition_id,
    trace_id: traceId,
    input_digest: inputDigest,
    output_digest: outputDigest,
    execution_status: input.measurement.status === 'NOT_COMPUTED'
      ? 'NOT_EXECUTED' as const
      : 'UNVERIFIED_CALLER_INPUT' as const,
    measurement_status: input.measurement.status,
  })
  const visual = deepFreeze({
    nodes: deriveNodes(receiptSource, stateComparison),
    edge_updates: edgeUpdates,
    event: {
      transition_id: input.transition_id,
      terminal_receipt_id: receiptSource.terminal_receipt_id,
      terminal_receipt_kind: receiptSource.terminal_receipt_kind,
      terminal_outcome: receiptSource.terminal_outcome,
      severity: feedback.severity,
      signal: feedback.signal,
    },
    receipt_timeline: {
      terminal_receipt_id: receiptSource.terminal_receipt_id,
      chain_digest: receiptSource.chain_digest,
      receipt_count: receiptSource.receipt_count,
    },
    next_route: input.next_route,
  })
  const unsigned = deepFreeze({
    schema_version: HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION,
    artifact_kind: HOLONNGRAM_ARTIFACT_KIND,
    compiler_version: HOLONNGRAM_COMPILER_VERSION,
    topology_id: HOLONNGRAM_TOPOLOGY_ID,
    epistemic_status: 'DERIVED_NON_AUTHORITATIVE' as const,
    source: receiptSource,
    formula_trace: formulaTrace,
    state_comparison: stateComparison,
    feedback,
    visual,
    safety: {
      grants_authority: false as const,
      executes_mutation: false as const,
      promotes_evidence: false as const,
      claims_authoritative_provenance: false as const,
      route_adjustment_authorized: false as const,
    },
  })
  const frameDigest = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FRAME_DOMAIN,
    frame: unsigned,
  }))
  return normalizeHolonngramVisualFeedbackFrameV1({
    ...unsigned,
    frame_digest: frameDigest,
  })
}

export function normalizeHolonngramCompilerInputV1(
  value: unknown,
): HolonngramCompilerInputV1 {
  const input = asObject('Holonñgram compiler input', snapshotIJson(
    value, 'Holonñgram compiler input',
  ))
  assertExactKeys('Holonñgram compiler input', input, [
    'compiler_version',
    'edge_updates',
    'formula_definition_digest',
    'formula_id',
    'formula_version',
    'measurement',
    'next_route',
    'schema_version',
    'transition_id',
  ])
  if (input.schema_version !== HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION ||
      input.compiler_version !== HOLONNGRAM_COMPILER_VERSION) {
    fail('Holonñgram compiler input version is unsupported')
  }
  const measurement = normalizeMeasurement(input.measurement, 'input.measurement')
  const edgeUpdates = asArray('input.edge_updates', input.edge_updates)
    .map((edge, index) => normalizeEdgeUpdate(edge, `input.edge_updates[${index}]`))
  assertEdgesSortedUnique(edgeUpdates)
  if (measurement.status === 'NOT_COMPUTED' && edgeUpdates.length !== 0) {
    fail('NOT_COMPUTED input cannot claim edge measurements')
  }
  if (edgeUpdates.some(edge => edge.measurement_status !== measurement.status)) {
    fail('edge measurement status must match the formula measurement status')
  }
  return deepFreeze({
    schema_version: HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION,
    compiler_version: HOLONNGRAM_COMPILER_VERSION,
    formula_id: assertSafeId('input.formula_id', input.formula_id),
    formula_version: assertSafeId('input.formula_version', input.formula_version),
    formula_definition_digest: assertNonZeroHash(
      'input.formula_definition_digest', input.formula_definition_digest,
    ),
    transition_id: assertSafeId('input.transition_id', input.transition_id),
    measurement,
    edge_updates: edgeUpdates,
    next_route: assertSafeId('input.next_route', input.next_route),
  })
}

export function normalizeHolonngramVisualFeedbackFrameV1(
  value: unknown,
): HolonngramVisualFeedbackFrameV1 {
  const frame = asObject('Holonñgram frame', snapshotIJson(value, 'Holonñgram frame'))
  assertExactKeys('Holonñgram frame', frame, [
    'artifact_kind',
    'compiler_version',
    'epistemic_status',
    'feedback',
    'formula_trace',
    'frame_digest',
    'safety',
    'schema_version',
    'source',
    'state_comparison',
    'topology_id',
    'visual',
  ])
  if (frame.schema_version !== HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION ||
      frame.artifact_kind !== HOLONNGRAM_ARTIFACT_KIND ||
      frame.compiler_version !== HOLONNGRAM_COMPILER_VERSION ||
      frame.topology_id !== HOLONNGRAM_TOPOLOGY_ID ||
      frame.epistemic_status !== 'DERIVED_NON_AUTHORITATIVE') {
    fail('Holonñgram frame header is unsupported')
  }
  const source = normalizeSource(frame.source)
  const stateComparison = normalizeStateComparison(frame.state_comparison)
  assertStateSemantics(source, stateComparison)
  const feedback = normalizeFeedback(frame.feedback)
  const formulaTrace = normalizeFormulaTrace(frame.formula_trace)
  if (formulaTrace.measurement_status !== feedback.resonance.measurement_status ||
      formulaTrace.measurement_status !== feedback.value.measurement_status) {
    fail('formula and feedback measurement statuses disagree')
  }
  const visual = normalizeVisual(frame.visual, source, feedback)
  if (formulaTrace.transition_id !== visual.event.transition_id) {
    fail('formula trace transition id does not match the visual event')
  }
  if (visual.edge_updates.some(
    edge => edge.measurement_status !== formulaTrace.measurement_status,
  )) {
    fail('visual edge measurements are not bound to the formula trace status')
  }
  if (formulaTrace.measurement_status === 'NOT_COMPUTED' &&
      visual.edge_updates.length !== 0) {
    fail('NOT_COMPUTED frames cannot contain edge updates')
  }
  const safety = asObject('frame.safety', frame.safety)
  assertExactKeys('frame.safety', safety, [
    'claims_authoritative_provenance',
    'executes_mutation',
    'grants_authority',
    'promotes_evidence',
    'route_adjustment_authorized',
  ])
  if (safety.grants_authority !== false ||
      safety.executes_mutation !== false ||
      safety.promotes_evidence !== false ||
      safety.claims_authoritative_provenance !== false ||
      safety.route_adjustment_authorized !== false) {
    fail('Holonñgram safety boundary must remain entirely non-authoritative')
  }
  return deepFreeze({
    schema_version: HOLONNGRAM_VISUAL_FEEDBACK_SCHEMA_VERSION,
    artifact_kind: HOLONNGRAM_ARTIFACT_KIND,
    compiler_version: HOLONNGRAM_COMPILER_VERSION,
    topology_id: HOLONNGRAM_TOPOLOGY_ID,
    epistemic_status: 'DERIVED_NON_AUTHORITATIVE',
    source,
    formula_trace: formulaTrace,
    state_comparison: stateComparison,
    feedback,
    visual,
    safety: {
      grants_authority: false,
      executes_mutation: false,
      promotes_evidence: false,
      claims_authoritative_provenance: false,
      route_adjustment_authorized: false,
    },
    frame_digest: assertNonZeroHash('frame.frame_digest', frame.frame_digest),
  })
}

/**
 * Verify strict shape and deterministic digest integrity of a stored frame.
 *
 * This function does not authenticate the embedded receipt provenance. Live
 * admission must call resolveAndCompileHolonngramVisualFeedbackV1 so the signed
 * receipt chain and current trust context are resolved again.
 */
export async function verifyHolonngramVisualFeedbackFrameIntegrityV1(
  value: unknown,
): Promise<HolonngramVisualFeedbackFrameV1> {
  const frame = normalizeHolonngramVisualFeedbackFrameV1(value)
  const expectedInputDigest = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_INPUT_DOMAIN,
    source: frame.source,
  }))
  const expectedOutputDigest = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_OUTPUT_DOMAIN,
    state_comparison: frame.state_comparison,
    feedback: frame.feedback,
    edge_updates: frame.visual.edge_updates,
    next_route: frame.visual.next_route,
  }))
  const expectedTraceId = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FORMULA_TRACE_DOMAIN,
    formula_id: frame.formula_trace.formula_id,
    formula_version: frame.formula_trace.formula_version,
    formula_definition_digest: frame.formula_trace.formula_definition_digest,
    input_digest: expectedInputDigest,
    output_digest: expectedOutputDigest,
  }))
  if (frame.formula_trace.input_digest !== expectedInputDigest ||
      frame.formula_trace.output_digest !== expectedOutputDigest ||
      frame.formula_trace.trace_id !== expectedTraceId) {
    fail('Holonñgram formula trace is not bound to its source and visual output')
  }
  const expectedFeedback = feedbackFromSource(frame.source, {
    status: frame.formula_trace.measurement_status,
    resonance_ppm: frame.feedback.resonance.ppm,
    value_delta_ppm: frame.feedback.value.delta_ppm,
  })
  if (canonicalizeJCSString(frame.feedback) !== canonicalizeJCSString(expectedFeedback)) {
    fail('Holonñgram feedback does not follow the deterministic terminal map')
  }
  const expectedNodes = deriveNodes(frame.source, frame.state_comparison)
  if (canonicalizeJCSString(frame.visual.nodes) !== canonicalizeJCSString(expectedNodes)) {
    fail('Holonñgram nodes do not match their verified source bindings')
  }
  const { frame_digest: _frameDigest, ...unsigned } = frame
  const expected = await sha256Hex(canonicalizeJCS({
    domain: HOLONNGRAM_FRAME_DOMAIN,
    frame: unsigned,
  }))
  if (frame.frame_digest !== expected) fail('Holonñgram frame digest is invalid')
  return frame
}

function sourceFrom(
  decision: CrossRuntimeReceiptVerificationDecisionV1,
  terminal: CrossRuntimeReceiptEnvelopeV1,
): HolonngramSourceV1 {
  const body = terminal.receipt_body
  return deepFreeze({
    provenance_status: 'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED',
    decision_digest: decision.decision_digest,
    terminal_receipt_id: decision.terminal_receipt_id,
    terminal_receipt_kind: decision.terminal_receipt_kind,
    terminal_outcome: decision.terminal_outcome,
    chain_digest: decision.chain_digest,
    receipt_count: decision.receipt_count,
    registry_roots: decision.registry_roots,
    actor_identity_root: decision.actor_identity_root,
    session_identity_root: decision.session_identity_root,
    workspace_identity_root: decision.workspace_identity_root,
    holon_identity_root: decision.holon_identity_root,
    authority_domain: decision.authority_domain,
    authority_level: decision.authority_level,
    authority_receipt_hash: decision.authority_receipt_hash,
    lease_id: decision.lease_id,
    lease_generation: decision.lease_generation,
    fencing_token: decision.fencing_token,
    lease_authorization_receipt_hash: decision.lease_authorization_receipt_hash,
    parent_receipt_hash: body.parent_receipt_hash,
    observed_state_root: body.observed_state_root,
    expected_state_root: body.expected_state_root,
    action_digest: decision.action_digest,
    before_state_root: decision.before_state_root,
    after_state_root: decision.after_state_root,
    result_digest: decision.result_digest,
    terminal_timestamp_ms: body.timestamp_ms,
    terminal_nonce: body.nonce,
    denial_codes: body.denial_codes,
    verifier_identity_root: terminal.proof.verifier_identity_root,
    observed_at_ms: decision.observed_at_ms,
    max_clock_skew_ms: decision.max_clock_skew_ms,
  })
}

function assertTerminalBinding(
  decision: CrossRuntimeReceiptVerificationDecisionV1,
  terminal: CrossRuntimeReceiptEnvelopeV1,
): void {
  const body = terminal.receipt_body
  const pairs: readonly (readonly [unknown, unknown, string])[] = [
    [terminal.receipt_id, decision.terminal_receipt_id, 'receipt id'],
    [terminal.receipt_kind, decision.terminal_receipt_kind, 'receipt kind'],
    [body.outcome, decision.terminal_outcome, 'outcome'],
    [body.actor_identity_root, decision.actor_identity_root, 'actor identity'],
    [body.session_identity_root, decision.session_identity_root, 'session identity'],
    [body.workspace_identity_root, decision.workspace_identity_root, 'workspace identity'],
    [body.holon_identity_root, decision.holon_identity_root, 'holon identity'],
    [body.authority_domain, decision.authority_domain, 'authority domain'],
    [body.authority_level, decision.authority_level, 'authority level'],
    [body.authority_receipt_hash, decision.authority_receipt_hash, 'authority receipt'],
    [body.lease_id, decision.lease_id, 'lease id'],
    [body.lease_generation, decision.lease_generation, 'lease generation'],
    [body.fencing_token, decision.fencing_token, 'fencing token'],
    [
      body.lease_authorization_receipt_hash,
      decision.lease_authorization_receipt_hash,
      'lease authorization',
    ],
    [body.action_digest, decision.action_digest, 'action digest'],
    [body.before_state_root, decision.before_state_root, 'before state'],
    [body.after_state_root, decision.after_state_root, 'after state'],
    [body.result_digest, decision.result_digest, 'result digest'],
  ]
  for (const [actual, expected, label] of pairs) {
    if (actual !== expected) fail(`terminal receipt ${label} does not match verified decision`)
  }
  if (!decision.registry_roots.includes(terminal.proof.trust_registry_root)) {
    fail('terminal receipt trust registry root is absent from the verified decision')
  }
}

function deriveStateComparison(
  terminal: CrossRuntimeReceiptEnvelopeV1,
): HolonngramStateComparisonV1 {
  const body = terminal.receipt_body
  return deepFreeze({
    observed_state_root: body.observed_state_root,
    expected_state_root: body.expected_state_root,
    before_state_root: body.before_state_root,
    after_state_root: body.after_state_root,
    field_diff_status: 'ROOTS_ONLY' as const,
    delta_type: deltaTypeFor(terminal),
  })
}

function deltaTypeFor(terminal: CrossRuntimeReceiptEnvelopeV1): HolonngramDeltaTypeV1 {
  switch (terminal.receipt_kind) {
    case 'MUTATION_COMPLETED':
      if (terminal.receipt_body.expected_state_root !==
          terminal.receipt_body.observed_state_root) return 'STALE_EXPECTATION'
      return terminal.receipt_body.before_state_root === terminal.receipt_body.after_state_root
        ? 'MATCH'
        : 'STATE_CHANGED'
    case 'MUTATION_CANCELLED': return 'CANCELLED'
    case 'MUTATION_FAILED': return 'FAILED'
    case 'LEASE_EXPIRED': return 'EXPIRED'
    case 'LEASE_REVOKED': return 'REVOKED'
    case 'LEASE_ISSUANCE_DENIED':
    case 'LEASE_RENEWAL_DENIED':
    case 'MUTATION_DENIED':
      return 'DENIED'
    case 'LEASE_ISSUED':
    case 'LEASE_RENEWED':
    case 'MUTATION_ADMITTED':
      fail('non-terminal receipt cannot produce a Holonñgram frame')
  }
}

function deriveFeedback(
  terminal: CrossRuntimeReceiptEnvelopeV1,
  measurement: HolonngramCompilerInputV1['measurement'],
): HolonngramFeedbackV1 {
  return feedbackFromSource({
    terminal_receipt_kind: terminal.receipt_kind,
    denial_codes: terminal.receipt_body.denial_codes,
  }, measurement)
}

function feedbackFromSource(
  source: Pick<HolonngramSourceV1, 'terminal_receipt_kind' | 'denial_codes'>,
  measurement: HolonngramCompilerInputV1['measurement'],
): HolonngramFeedbackV1 {
  const kind = source.terminal_receipt_kind
  let signal: HolonngramFeedbackSignalV1
  let severity: HolonngramSeverityV1
  let boundary: HolonngramBoundaryV1
  if (kind === 'MUTATION_COMPLETED') {
    signal = 'REINFORCE'
    severity = 'INFO'
    boundary = 'NONE'
  } else if (kind === 'MUTATION_CANCELLED') {
    signal = 'ROLLBACK'
    severity = 'WARNING'
    boundary = 'CANCELLATION'
  } else if (kind === 'MUTATION_FAILED') {
    signal = 'ROLLBACK'
    severity = 'CRITICAL'
    boundary = 'EXECUTION'
  } else if (kind === 'LEASE_EXPIRED' || kind === 'LEASE_REVOKED') {
    signal = 'FAIL_CLOSED'
    severity = 'CRITICAL'
    boundary = 'LEASE'
  } else {
    const denial = classifyHolonngramDenialCodesV1(source.denial_codes)
    signal = denial.signal
    severity = denial.severity
    boundary = denial.boundary
  }
  return deepFreeze({
    signal,
    severity,
    boundary,
    rationale_codes: source.denial_codes,
    resonance: {
      measurement_status: measurement.status,
      ppm: measurement.resonance_ppm,
    },
    value: {
      measurement_status: measurement.status,
      delta_ppm: measurement.value_delta_ppm,
    },
  })
}

export function classifyHolonngramDenialCodesV1(
  codes: readonly string[],
): Pick<HolonngramFeedbackV1, 'signal' | 'severity' | 'boundary'> {
  const joined = codes.join('\u0000')
  // Fail-closed categories always outrank repair/review categories. The order
  // below is also the deterministic boundary tie-break for mixed critical codes.
  if (/TRUST|SIGNATURE|UNSIGNED|REGISTRY|KEY/.test(joined)) {
    return { signal: 'FAIL_CLOSED', severity: 'CRITICAL', boundary: 'TRUST' }
  }
  if (/FENC/.test(joined)) {
    return { signal: 'FAIL_CLOSED', severity: 'CRITICAL', boundary: 'FENCING' }
  }
  if (/LEASE|EXPIR/.test(joined)) {
    return { signal: 'FAIL_CLOSED', severity: 'CRITICAL', boundary: 'LEASE' }
  }
  if (/REPLAY|DUPLICATE/.test(joined)) {
    return { signal: 'FAIL_CLOSED', severity: 'CRITICAL', boundary: 'REPLAY' }
  }
  if (/SCHEMA/.test(joined)) {
    return { signal: 'REPAIR_SCHEMA', severity: 'WARNING', boundary: 'SCHEMA' }
  }
  if (/AUTHORITY|GRANT|SCOPE|POLICY/.test(joined)) {
    return { signal: 'REQUEST_GRANT', severity: 'WARNING', boundary: 'AUTHORITY' }
  }
  if (/STATE|STALE/.test(joined)) {
    return { signal: 'NEEDS_REVIEW', severity: 'WARNING', boundary: 'STATE' }
  }
  return { signal: 'NEEDS_REVIEW', severity: 'WARNING', boundary: 'NONE' }
}

function deriveNodes(
  source: HolonngramSourceV1,
  comparison: HolonngramStateComparisonV1,
): readonly HolonngramVisualNodeV1[] {
  const terminalState = nodeStateForOutcome(source.terminal_outcome)
  const stateState: HolonngramNodeStateV1 =
    comparison.before_state_root === comparison.after_state_root ? 'UNCHANGED' : 'CHANGED'
  const refs = (...values: readonly SHA256Hex[]): readonly SHA256Hex[] =>
    deepFreeze([...new Set(values.map(
      value => value === ZERO_HASH ? source.terminal_receipt_id : value,
    ))].sort(compareUtf8))
  const refsByNode: Readonly<Record<HolonngramNodeIdV1, readonly SHA256Hex[]>> = {
    C0: refs(source.terminal_receipt_id),
    I1: refs(source.action_digest),
    I2: refs(source.decision_digest),
    I3: refs(source.lease_id, source.lease_authorization_receipt_hash),
    I4: refs(source.result_digest),
    I5: refs(source.chain_digest),
    I6: refs(source.after_state_root),
    O1: refs(source.actor_identity_root),
    O2: refs(source.session_identity_root),
    O3: refs(source.workspace_identity_root),
    O4: refs(source.holon_identity_root),
    O5: refs(source.authority_receipt_hash),
    O6: refs(source.lease_id),
    O7: refs(source.fencing_token),
    O8: refs(source.expected_state_root),
    O9: refs(source.observed_state_root),
    O10: refs(source.action_digest),
    O11: refs(source.result_digest),
    O12: refs(source.chain_digest, ...source.registry_roots),
  }
  return deepFreeze(HOLONNGRAM_NODE_DEFINITIONS_V1.map(definition => {
    let state: HolonngramNodeStateV1 = 'VERIFIED'
    if (definition.node_id === 'C0') state = terminalState
    if (definition.node_id === 'I4' || definition.node_id === 'I6' ||
        definition.node_id === 'O8' || definition.node_id === 'O9') {
      state = stateState
    }
    if (definition.node_id === 'I3' &&
        (terminalState === 'EXPIRED' || terminalState === 'REVOKED')) {
      state = terminalState
    }
    return {
      ...definition,
      state,
      source_refs: sortUnique(refsByNode[definition.node_id]),
    }
  }))
}

function nodeStateForOutcome(outcome: CrossRuntimeReceiptOutcomeV1): HolonngramNodeStateV1 {
  switch (outcome) {
    case 'COMPLETED': return 'ACTIVE'
    case 'DENIED': return 'DENIED'
    case 'CANCELLED': return 'CANCELLED'
    case 'FAILED': return 'FAILED'
    case 'EXPIRED': return 'EXPIRED'
    case 'REVOKED': return 'REVOKED'
    case 'ADMITTED': fail('non-terminal admitted outcome cannot produce a Holonñgram frame')
  }
}

function normalizeSource(value: unknown): HolonngramSourceV1 {
  const source = asObject('frame.source', value)
  assertExactKeys('frame.source', source, [
    'action_digest',
    'actor_identity_root',
    'after_state_root',
    'authority_domain',
    'authority_level',
    'authority_receipt_hash',
    'before_state_root',
    'chain_digest',
    'decision_digest',
    'denial_codes',
    'expected_state_root',
    'fencing_token',
    'holon_identity_root',
    'lease_authorization_receipt_hash',
    'lease_generation',
    'lease_id',
    'max_clock_skew_ms',
    'observed_at_ms',
    'observed_state_root',
    'parent_receipt_hash',
    'provenance_status',
    'receipt_count',
    'registry_roots',
    'result_digest',
    'session_identity_root',
    'terminal_nonce',
    'terminal_outcome',
    'terminal_receipt_id',
    'terminal_receipt_kind',
    'terminal_timestamp_ms',
    'verifier_identity_root',
    'workspace_identity_root',
  ])
  if (source.provenance_status !== 'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED') {
    fail('frame source provenance status is invalid')
  }
  const registryRoots = asArray('frame.source.registry_roots', source.registry_roots)
    .map((root, index) => assertNonZeroHash(`frame.source.registry_roots[${index}]`, root))
  assertSortedUnique('frame.source.registry_roots', registryRoots)
  const denialCodes = asArray('frame.source.denial_codes', source.denial_codes)
    .map((code, index) => assertSafeId(`frame.source.denial_codes[${index}]`, code))
  assertSortedUnique('frame.source.denial_codes', denialCodes)
  const terminalReceiptKind = assertReceiptKind(source.terminal_receipt_kind)
  const terminalOutcome = assertReceiptOutcome(source.terminal_outcome)
  assertTerminalKindOutcome(terminalReceiptKind, terminalOutcome)
  return deepFreeze({
    provenance_status: 'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED',
    decision_digest: assertNonZeroHash('frame.source.decision_digest', source.decision_digest),
    terminal_receipt_id: assertNonZeroHash(
      'frame.source.terminal_receipt_id', source.terminal_receipt_id,
    ),
    terminal_receipt_kind: terminalReceiptKind,
    terminal_outcome: terminalOutcome,
    chain_digest: assertNonZeroHash('frame.source.chain_digest', source.chain_digest),
    receipt_count: assertPositiveDecimal('frame.source.receipt_count', source.receipt_count),
    registry_roots: registryRoots,
    actor_identity_root: assertNonZeroHash(
      'frame.source.actor_identity_root', source.actor_identity_root,
    ),
    session_identity_root: assertNonZeroHash(
      'frame.source.session_identity_root', source.session_identity_root,
    ),
    workspace_identity_root: assertNonZeroHash(
      'frame.source.workspace_identity_root', source.workspace_identity_root,
    ),
    holon_identity_root: assertNonZeroHash(
      'frame.source.holon_identity_root', source.holon_identity_root,
    ),
    authority_domain: assertSafeId('frame.source.authority_domain', source.authority_domain),
    authority_level: assertAuthorityLevel(source.authority_level),
    authority_receipt_hash: assertHash(
      'frame.source.authority_receipt_hash', source.authority_receipt_hash,
    ),
    lease_id: assertNonZeroHash('frame.source.lease_id', source.lease_id),
    lease_generation: assertDecimal('frame.source.lease_generation', source.lease_generation),
    fencing_token: assertHash('frame.source.fencing_token', source.fencing_token),
    lease_authorization_receipt_hash: assertHash(
      'frame.source.lease_authorization_receipt_hash',
      source.lease_authorization_receipt_hash,
    ),
    parent_receipt_hash: assertHash(
      'frame.source.parent_receipt_hash', source.parent_receipt_hash,
    ),
    observed_state_root: assertNonZeroHash(
      'frame.source.observed_state_root', source.observed_state_root,
    ),
    expected_state_root: assertNonZeroHash(
      'frame.source.expected_state_root', source.expected_state_root,
    ),
    action_digest: assertNonZeroHash('frame.source.action_digest', source.action_digest),
    before_state_root: assertNonZeroHash(
      'frame.source.before_state_root', source.before_state_root,
    ),
    after_state_root: assertNonZeroHash(
      'frame.source.after_state_root', source.after_state_root,
    ),
    result_digest: assertNonZeroHash('frame.source.result_digest', source.result_digest),
    terminal_timestamp_ms: assertDecimal(
      'frame.source.terminal_timestamp_ms', source.terminal_timestamp_ms,
    ),
    terminal_nonce: assertSafeId('frame.source.terminal_nonce', source.terminal_nonce),
    denial_codes: denialCodes,
    verifier_identity_root: assertNonZeroHash(
      'frame.source.verifier_identity_root', source.verifier_identity_root,
    ),
    observed_at_ms: assertDecimal('frame.source.observed_at_ms', source.observed_at_ms),
    max_clock_skew_ms: assertDecimal(
      'frame.source.max_clock_skew_ms', source.max_clock_skew_ms,
    ),
  })
}

function normalizeFormulaTrace(value: unknown): HolonngramFormulaTraceV1 {
  const trace = asObject('frame.formula_trace', value)
  assertExactKeys('frame.formula_trace', trace, [
    'execution_status',
    'formula_definition_digest',
    'formula_id',
    'formula_version',
    'input_digest',
    'measurement_status',
    'output_digest',
    'trace_id',
    'transition_id',
  ])
  const executionStatus = assertEnum(
    'frame.formula_trace.execution_status',
    trace.execution_status,
    new Set<HolonngramFormulaExecutionStatusV1>([
      'NOT_EXECUTED', 'UNVERIFIED_CALLER_INPUT',
    ]),
  )
  const measurementStatus = assertMeasurementStatus(
    'frame.formula_trace.measurement_status', trace.measurement_status,
  )
  const expectedExecutionStatus: HolonngramFormulaExecutionStatusV1 =
    measurementStatus === 'NOT_COMPUTED'
      ? 'NOT_EXECUTED'
      : 'UNVERIFIED_CALLER_INPUT'
  if (executionStatus !== expectedExecutionStatus) {
    fail('formula projection status overstates execution or measurement provenance')
  }
  return deepFreeze({
    formula_id: assertSafeId('frame.formula_trace.formula_id', trace.formula_id),
    formula_version: assertSafeId('frame.formula_trace.formula_version', trace.formula_version),
    formula_definition_digest: assertNonZeroHash(
      'frame.formula_trace.formula_definition_digest',
      trace.formula_definition_digest,
    ),
    transition_id: assertSafeId(
      'frame.formula_trace.transition_id', trace.transition_id,
    ),
    trace_id: assertNonZeroHash('frame.formula_trace.trace_id', trace.trace_id),
    input_digest: assertNonZeroHash('frame.formula_trace.input_digest', trace.input_digest),
    output_digest: assertNonZeroHash('frame.formula_trace.output_digest', trace.output_digest),
    execution_status: executionStatus,
    measurement_status: measurementStatus,
  })
}

function normalizeStateComparison(value: unknown): HolonngramStateComparisonV1 {
  const comparison = asObject('frame.state_comparison', value)
  assertExactKeys('frame.state_comparison', comparison, [
    'after_state_root',
    'before_state_root',
    'delta_type',
    'expected_state_root',
    'field_diff_status',
    'observed_state_root',
  ])
  if (comparison.field_diff_status !== 'ROOTS_ONLY') {
    fail('field-level differences are not proven by state roots')
  }
  const deltaTypes = new Set<HolonngramDeltaTypeV1>([
    'MATCH', 'STATE_CHANGED', 'STALE_EXPECTATION', 'DENIED',
    'CANCELLED', 'FAILED', 'EXPIRED', 'REVOKED',
  ])
  return deepFreeze({
    observed_state_root: assertNonZeroHash(
      'frame.state_comparison.observed_state_root', comparison.observed_state_root,
    ),
    expected_state_root: assertNonZeroHash(
      'frame.state_comparison.expected_state_root', comparison.expected_state_root,
    ),
    before_state_root: assertNonZeroHash(
      'frame.state_comparison.before_state_root', comparison.before_state_root,
    ),
    after_state_root: assertNonZeroHash(
      'frame.state_comparison.after_state_root', comparison.after_state_root,
    ),
    field_diff_status: 'ROOTS_ONLY',
    delta_type: assertEnum(
      'frame.state_comparison.delta_type', comparison.delta_type, deltaTypes,
    ),
  })
}

function normalizeFeedback(value: unknown): HolonngramFeedbackV1 {
  const feedback = asObject('frame.feedback', value)
  assertExactKeys('frame.feedback', feedback, [
    'boundary', 'rationale_codes', 'resonance', 'severity', 'signal', 'value',
  ])
  const rationaleCodes = asArray('frame.feedback.rationale_codes', feedback.rationale_codes)
    .map((code, index) => assertSafeId(`frame.feedback.rationale_codes[${index}]`, code))
  assertSortedUnique('frame.feedback.rationale_codes', rationaleCodes)
  const resonance = normalizeMeasuredValue(
    feedback.resonance, 'frame.feedback.resonance', 'ppm',
  )
  const measuredValue = normalizeMeasuredValue(
    feedback.value, 'frame.feedback.value', 'delta_ppm',
  )
  const signals = new Set<HolonngramFeedbackSignalV1>([
    'REINFORCE', 'NEEDS_REVIEW', 'REQUEST_GRANT',
    'REPAIR_SCHEMA', 'ROLLBACK', 'FAIL_CLOSED',
  ])
  const severities = new Set<HolonngramSeverityV1>([
    'INFO', 'REVIEW', 'WARNING', 'CRITICAL', 'FATAL',
  ])
  const boundaries = new Set<HolonngramBoundaryV1>([
    'NONE', 'AUTHORITY', 'LEASE', 'FENCING', 'STATE',
    'SCHEMA', 'TRUST', 'REPLAY', 'CANCELLATION', 'EXECUTION',
  ])
  return deepFreeze({
    signal: assertEnum('frame.feedback.signal', feedback.signal, signals),
    severity: assertEnum('frame.feedback.severity', feedback.severity, severities),
    boundary: assertEnum('frame.feedback.boundary', feedback.boundary, boundaries),
    rationale_codes: rationaleCodes,
    resonance: {
      measurement_status: resonance.status,
      ppm: resonance.value,
    },
    value: {
      measurement_status: measuredValue.status,
      delta_ppm: measuredValue.value,
    },
  })
}

function normalizeVisual(
  value: unknown,
  source: HolonngramSourceV1,
  feedback: HolonngramFeedbackV1,
): HolonngramVisualV1 {
  const visual = asObject('frame.visual', value)
  assertExactKeys('frame.visual', visual, [
    'edge_updates', 'event', 'next_route', 'nodes', 'receipt_timeline',
  ])
  const nodes = asArray('frame.visual.nodes', visual.nodes)
    .map((node, index) => normalizeNode(node, index))
  assertExactTopology(nodes)
  const edges = asArray('frame.visual.edge_updates', visual.edge_updates)
    .map((edge, index) => normalizeEdgeUpdate(edge, `frame.visual.edge_updates[${index}]`))
  assertEdgesSortedUnique(edges)
  const event = asObject('frame.visual.event', visual.event)
  assertExactKeys('frame.visual.event', event, [
    'severity', 'signal', 'terminal_outcome',
    'terminal_receipt_id', 'terminal_receipt_kind', 'transition_id',
  ])
  const timeline = asObject('frame.visual.receipt_timeline', visual.receipt_timeline)
  assertExactKeys('frame.visual.receipt_timeline', timeline, [
    'chain_digest', 'receipt_count', 'terminal_receipt_id',
  ])
  const eventTransition = assertSafeId(
    'frame.visual.event.transition_id', event.transition_id,
  )
  if (event.terminal_receipt_id !== source.terminal_receipt_id ||
      event.terminal_receipt_kind !== source.terminal_receipt_kind ||
      event.terminal_outcome !== source.terminal_outcome ||
      event.severity !== feedback.severity ||
      event.signal !== feedback.signal ||
      timeline.terminal_receipt_id !== source.terminal_receipt_id ||
      timeline.chain_digest !== source.chain_digest ||
      timeline.receipt_count !== source.receipt_count) {
    fail('visual event or timeline is not bound to verified source evidence')
  }
  return deepFreeze({
    nodes,
    edge_updates: edges,
    event: {
      transition_id: eventTransition,
      terminal_receipt_id: source.terminal_receipt_id,
      terminal_receipt_kind: source.terminal_receipt_kind,
      terminal_outcome: source.terminal_outcome,
      severity: feedback.severity,
      signal: feedback.signal,
    },
    receipt_timeline: {
      terminal_receipt_id: source.terminal_receipt_id,
      chain_digest: source.chain_digest,
      receipt_count: source.receipt_count,
    },
    next_route: assertSafeId('frame.visual.next_route', visual.next_route),
  })
}

function normalizeNode(value: unknown, index: number): HolonngramVisualNodeV1 {
  const node = asObject(`frame.visual.nodes[${index}]`, value)
  assertExactKeys(`frame.visual.nodes[${index}]`, node, [
    'node_id', 'ring', 'role', 'source_refs', 'state',
  ])
  const sourceRefs = asArray(
    `frame.visual.nodes[${index}].source_refs`, node.source_refs,
  ).map((root, rootIndex) => assertNonZeroHash(
    `frame.visual.nodes[${index}].source_refs[${rootIndex}]`, root,
  ))
  assertSortedUnique(`frame.visual.nodes[${index}].source_refs`, sourceRefs)
  const nodeId = assertNodeId(`frame.visual.nodes[${index}].node_id`, node.node_id)
  const definition = HOLONNGRAM_NODE_DEFINITIONS_V1[index]
  if (definition === undefined ||
      nodeId !== definition.node_id ||
      node.ring !== definition.ring ||
      node.role !== definition.role) {
    fail('Holonñgram nodes must preserve the fixed 19-node order, rings, and roles')
  }
  return deepFreeze({
    node_id: nodeId,
    ring: definition.ring,
    role: definition.role,
    state: assertEnum(`frame.visual.nodes[${index}].state`, node.state, NODE_STATES),
    source_refs: sourceRefs,
  })
}

function normalizeEdgeUpdate(value: unknown, field: string): HolonngramEdgeUpdateV1 {
  const edge = asObject(field, value)
  assertExactKeys(field, edge, [
    'authority_delta_ppm',
    'basis_codes',
    'edge_kind',
    'from_node',
    'measurement_status',
    'risk_delta_ppm',
    'schema_delta_ppm',
    'to_node',
    'trust_delta_ppm',
  ])
  const status = assertMeasurementStatus(`${field}.measurement_status`, edge.measurement_status)
  const basisCodes = asArray(`${field}.basis_codes`, edge.basis_codes)
    .map((code, index) => assertSafeId(`${field}.basis_codes[${index}]`, code))
  assertSortedUnique(`${field}.basis_codes`, basisCodes)
  const normalizeDelta = (name: string, delta: unknown): DecimalStringV1 | null =>
    status === 'NOT_COMPUTED'
      ? assertNull(`${field}.${name}`, delta)
      : assertSignedPpm(`${field}.${name}`, delta)
  if (status === 'NOT_COMPUTED' && basisCodes.length !== 0) {
    fail(`${field} cannot claim basis codes when measurements were not computed`)
  }
  return deepFreeze({
    from_node: assertNodeId(`${field}.from_node`, edge.from_node),
    to_node: assertNodeId(`${field}.to_node`, edge.to_node),
    edge_kind: assertEnum(`${field}.edge_kind`, edge.edge_kind, EDGE_KINDS),
    measurement_status: status,
    trust_delta_ppm: normalizeDelta('trust_delta_ppm', edge.trust_delta_ppm),
    risk_delta_ppm: normalizeDelta('risk_delta_ppm', edge.risk_delta_ppm),
    schema_delta_ppm: normalizeDelta('schema_delta_ppm', edge.schema_delta_ppm),
    authority_delta_ppm: normalizeDelta(
      'authority_delta_ppm', edge.authority_delta_ppm,
    ),
    basis_codes: basisCodes,
  })
}

function normalizeMeasurement(
  value: unknown,
  field: string,
): HolonngramCompilerInputV1['measurement'] {
  const measurement = asObject(field, value)
  assertExactKeys(field, measurement, ['resonance_ppm', 'status', 'value_delta_ppm'])
  const status = assertMeasurementStatus(`${field}.status`, measurement.status)
  if (status === 'NOT_COMPUTED') {
    return deepFreeze({
      status,
      resonance_ppm: assertNull(`${field}.resonance_ppm`, measurement.resonance_ppm),
      value_delta_ppm: assertNull(
        `${field}.value_delta_ppm`, measurement.value_delta_ppm,
      ),
    })
  }
  return deepFreeze({
    status,
    resonance_ppm: assertUnsignedPpm(
      `${field}.resonance_ppm`, measurement.resonance_ppm,
    ),
    value_delta_ppm: assertSignedPpm(
      `${field}.value_delta_ppm`, measurement.value_delta_ppm,
    ),
  })
}

function normalizeMeasuredValue(
  value: unknown,
  field: string,
  valueKey: 'ppm' | 'delta_ppm',
): { readonly status: HolonngramMeasurementStatusV1; readonly value: string | null } {
  const measured = asObject(field, value)
  assertExactKeys(field, measured, ['measurement_status', valueKey])
  const status = assertMeasurementStatus(`${field}.measurement_status`, measured.measurement_status)
  const raw = measured[valueKey]
  return deepFreeze({
    status,
    value: status === 'NOT_COMPUTED'
      ? assertNull(`${field}.${valueKey}`, raw)
      : valueKey === 'ppm'
        ? assertUnsignedPpm(`${field}.${valueKey}`, raw)
        : assertSignedPpm(`${field}.${valueKey}`, raw),
  })
}

function assertStateSemantics(
  source: HolonngramSourceV1,
  comparison: HolonngramStateComparisonV1,
): void {
  if (comparison.observed_state_root !== source.observed_state_root ||
      comparison.expected_state_root !== source.expected_state_root ||
      comparison.before_state_root !== source.before_state_root ||
      comparison.after_state_root !== source.after_state_root) {
    fail('state comparison does not mirror verified source roots')
  }
  const stateChanged = source.before_state_root !== source.after_state_root
  if (source.terminal_receipt_kind !== 'MUTATION_COMPLETED' && stateChanged) {
    fail('non-completed terminal evidence must leave canonical state unchanged')
  }
  if (comparison.delta_type === 'STATE_CHANGED' &&
      (source.terminal_receipt_kind !== 'MUTATION_COMPLETED' || !stateChanged)) {
    fail('STATE_CHANGED is only valid for a state-changing mutation completion')
  }
  const expectedDelta = deltaTypeForSource(source)
  if (comparison.delta_type !== expectedDelta) {
    fail('state comparison delta type does not follow the verified terminal receipt')
  }
}

function deltaTypeForSource(
  source: Pick<
    HolonngramSourceV1,
    | 'terminal_receipt_kind'
    | 'expected_state_root'
    | 'observed_state_root'
    | 'before_state_root'
    | 'after_state_root'
  >,
): HolonngramDeltaTypeV1 {
  switch (source.terminal_receipt_kind) {
    case 'MUTATION_COMPLETED':
      if (source.expected_state_root !== source.observed_state_root) return 'STALE_EXPECTATION'
      return source.before_state_root === source.after_state_root ? 'MATCH' : 'STATE_CHANGED'
    case 'MUTATION_CANCELLED': return 'CANCELLED'
    case 'MUTATION_FAILED': return 'FAILED'
    case 'LEASE_EXPIRED': return 'EXPIRED'
    case 'LEASE_REVOKED': return 'REVOKED'
    case 'LEASE_ISSUANCE_DENIED':
    case 'LEASE_RENEWAL_DENIED':
    case 'MUTATION_DENIED':
      return 'DENIED'
    case 'LEASE_ISSUED':
    case 'LEASE_RENEWED':
    case 'MUTATION_ADMITTED':
      fail('non-terminal source cannot produce a Holonñgram state comparison')
  }
}

function assertExactTopology(nodes: readonly HolonngramVisualNodeV1[]): void {
  if (nodes.length !== HOLONNGRAM_NODE_DEFINITIONS_V1.length) {
    fail('Holonñgram topology must contain exactly 19 nodes')
  }
  for (let index = 0; index < HOLONNGRAM_NODE_DEFINITIONS_V1.length; index += 1) {
    const node = nodes[index]
    const definition = HOLONNGRAM_NODE_DEFINITIONS_V1[index]
    if (node === undefined || definition === undefined ||
        node.node_id !== definition.node_id ||
        node.ring !== definition.ring ||
        node.role !== definition.role) {
      fail('Holonñgram topology does not match HOLONNGRAM_19_V1')
    }
  }
}

function assertEdgesSortedUnique(edges: readonly HolonngramEdgeUpdateV1[]): void {
  const keys = edges.map(edge => `${edge.from_node}\u0000${edge.to_node}\u0000${edge.edge_kind}`)
  assertSortedUnique('edge update tuples', keys)
}

function snapshotIJson(value: unknown, label: string): unknown {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as unknown
    assertIJsonValue(snapshot, label)
    return snapshot
  } catch (error) {
    if (error instanceof HolonngramCompilerError) throw error
    fail(`${label} is not a closed I-JSON value: ${
      error instanceof Error ? error.message : String(error)
    }`)
  }
}

function asObject(field: string, value: unknown): Record<string, unknown> {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    fail(`${field} must be an object`)
  }
  return value as Record<string, unknown>
}

function asArray(field: string, value: unknown): readonly unknown[] {
  if (!Array.isArray(value)) fail(`${field} must be an array`)
  return value
}

function assertExactKeys(
  field: string,
  value: Record<string, unknown>,
  expectedKeys: readonly string[],
): void {
  const actual = Object.keys(value).sort(compareUtf8)
  const expected = [...expectedKeys].sort(compareUtf8)
  if (actual.length !== expected.length ||
      actual.some((key, index) => key !== expected[index])) {
    fail(`${field} has unexpected or missing fields`)
  }
}

function assertHash(field: string, value: unknown): SHA256Hex {
  if (typeof value !== 'string' || !HASH_PATTERN.test(value)) {
    fail(`${field} must be lowercase SHA-256 hex`)
  }
  return value as SHA256Hex
}

function assertNonZeroHash(field: string, value: unknown): SHA256Hex {
  const hash = assertHash(field, value)
  if (hash === ZERO_HASH) fail(`${field} must be non-zero`)
  return hash
}

function assertSafeId(field: string, value: unknown): string {
  if (typeof value !== 'string' || !SAFE_ID_PATTERN.test(value)) {
    fail(`${field} is not a canonical safe identifier`)
  }
  return value
}

function assertDecimal(field: string, value: unknown): DecimalStringV1 {
  if (typeof value !== 'string' || value.length > MAX_DECIMAL_DIGITS ||
      !DECIMAL_PATTERN.test(value)) {
    fail(`${field} must be a canonical unsigned decimal string`)
  }
  return value
}

function assertPositiveDecimal(field: string, value: unknown): DecimalStringV1 {
  const decimal = assertDecimal(field, value)
  if (BigInt(decimal) < 1n) fail(`${field} must be positive`)
  return decimal
}

function assertUnsignedPpm(field: string, value: unknown): DecimalStringV1 {
  const decimal = assertDecimal(field, value)
  if (BigInt(decimal) > PPM_LIMIT) fail(`${field} exceeds 1000000 ppm`)
  return decimal
}

function assertSignedPpm(field: string, value: unknown): DecimalStringV1 {
  if (typeof value !== 'string' || value.length > MAX_DECIMAL_DIGITS + 1 ||
      !SIGNED_DECIMAL_PATTERN.test(value) || value === '-0') {
    fail(`${field} must be a canonical signed decimal string`)
  }
  const amount = BigInt(value)
  if (amount < -PPM_LIMIT || amount > PPM_LIMIT) {
    fail(`${field} exceeds the signed 1000000 ppm bound`)
  }
  return value
}

function assertNull(field: string, value: unknown): null {
  if (value !== null) fail(`${field} must be null`)
  return null
}

function assertEnum<T extends string>(
  field: string,
  value: unknown,
  allowed: ReadonlySet<T>,
): T {
  if (typeof value !== 'string' || !allowed.has(value as T)) {
    fail(`${field} is invalid`)
  }
  return value as T
}

function assertMeasurementStatus(
  field: string,
  value: unknown,
): HolonngramMeasurementStatusV1 {
  return assertEnum(field, value, MEASUREMENT_STATUSES)
}

function assertNodeId(field: string, value: unknown): HolonngramNodeIdV1 {
  if (typeof value !== 'string' || !NODE_IDS.has(value)) {
    fail(`${field} is not a HOLONNGRAM_19_V1 node`)
  }
  return value as HolonngramNodeIdV1
}

function assertAuthorityLevel(value: unknown): AuthorityLevelV1 {
  const levels = new Set<AuthorityLevelV1>(['D0', 'D1', 'D2', 'D3', 'D4'])
  return assertEnum('frame.source.authority_level', value, levels)
}

function assertReceiptKind(value: unknown): CrossRuntimeReceiptKindV1 {
  const kinds = new Set<CrossRuntimeReceiptKindV1>([
    'LEASE_ISSUED', 'LEASE_ISSUANCE_DENIED', 'LEASE_RENEWED',
    'LEASE_RENEWAL_DENIED', 'LEASE_EXPIRED', 'LEASE_REVOKED',
    'MUTATION_ADMITTED', 'MUTATION_DENIED', 'MUTATION_COMPLETED',
    'MUTATION_CANCELLED', 'MUTATION_FAILED',
  ])
  return assertEnum('frame.source.terminal_receipt_kind', value, kinds)
}

function assertReceiptOutcome(value: unknown): CrossRuntimeReceiptOutcomeV1 {
  const outcomes = new Set<CrossRuntimeReceiptOutcomeV1>([
    'ADMITTED', 'DENIED', 'COMPLETED', 'CANCELLED',
    'FAILED', 'EXPIRED', 'REVOKED',
  ])
  return assertEnum('frame.source.terminal_outcome', value, outcomes)
}

function assertTerminalKindOutcome(
  kind: CrossRuntimeReceiptKindV1,
  outcome: CrossRuntimeReceiptOutcomeV1,
): void {
  const expected: Readonly<Record<CrossRuntimeReceiptKindV1, CrossRuntimeReceiptOutcomeV1>> = {
    LEASE_ISSUED: 'ADMITTED',
    LEASE_ISSUANCE_DENIED: 'DENIED',
    LEASE_RENEWED: 'ADMITTED',
    LEASE_RENEWAL_DENIED: 'DENIED',
    LEASE_EXPIRED: 'EXPIRED',
    LEASE_REVOKED: 'REVOKED',
    MUTATION_ADMITTED: 'ADMITTED',
    MUTATION_DENIED: 'DENIED',
    MUTATION_COMPLETED: 'COMPLETED',
    MUTATION_CANCELLED: 'CANCELLED',
    MUTATION_FAILED: 'FAILED',
  }
  if (outcome !== expected[kind]) fail('terminal receipt kind/outcome mismatch')
}

function sortUnique(values: readonly SHA256Hex[]): readonly SHA256Hex[] {
  return [...new Set(values)].sort(compareUtf8)
}

function assertSortedUnique(field: string, values: readonly string[]): void {
  for (let index = 1; index < values.length; index += 1) {
    if (compareUtf8(values[index - 1]!, values[index]!) >= 0) {
      fail(`${field} must be unique and strictly sorted by UTF-8 bytes`)
    }
  }
}

function compareUtf8(left: string, right: string): number {
  const leftBytes = new TextEncoder().encode(left)
  const rightBytes = new TextEncoder().encode(right)
  const length = Math.min(leftBytes.length, rightBytes.length)
  for (let index = 0; index < length; index += 1) {
    const difference = leftBytes[index]! - rightBytes[index]!
    if (difference !== 0) return difference
  }
  return leftBytes.length - rightBytes.length
}

function fail(message: string): never {
  throw new HolonngramCompilerError(message)
}
