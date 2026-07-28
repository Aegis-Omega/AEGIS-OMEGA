// ============================================================
// SOVEREIGN OMEGA - Authoritative Receipt Provenance Replay
// PROVENANCE ASSURANCE: T2->T3 implemented; comparator remains advisory
//
// Resolves an independently signed terminal receipt chain before allowing the
// existing authenticated outcome-evidence replay to reach persistence. This
// adapter verifies provenance bindings only. It grants no authority, executes
// no mutation, and does not change the comparator's epistemic status.
// ============================================================

import { assertIJsonValue } from '../core/i-json.js'
import { deepFreeze } from '../core/immutable.js'
import type { SequenceNumber, SHA256Hex } from '../core/types.js'
import type {
  CrossRuntimeReceiptSourceV1,
  CrossRuntimeReceiptVerificationDecisionV1,
  TrustedReceiptResolutionContextV1,
} from '../provenance/receipt-resolver.js'
import {
  resolveAndVerifyCrossRuntimeReceiptChainV1,
  verifyCrossRuntimeReceiptVerificationDecisionDigestV1,
} from '../provenance/receipt-resolver.js'
import type { MetacognitiveLoop } from './loop.js'
import type { ReadableOutcomeEvidenceArtifactStore } from './outcome-evidence-artifact-store.js'
import type {
  DurableTerminalStatus,
  TerminalExecutionOutcome,
} from './outcome-comparator.js'
import {
  replayAuthenticatedOutcomeEvidenceV1,
} from './outcome-evidence-replay.js'
import type {
  OutcomeEvidenceReplayResultV1,
  OutcomeReplayEvidenceV1,
  TrustedOutcomeReplayContextV1,
} from './outcome-evidence-replay.js'

export const AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED =
  'AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED' as const

export interface AuthoritativeOutcomeEvidenceReplayResultV1
  extends OutcomeEvidenceReplayResultV1 {
  readonly provenance_status: typeof AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED
  readonly provenance_decision: CrossRuntimeReceiptVerificationDecisionV1
}

export class AuthoritativeOutcomeEvidenceReplayError extends Error {
  override readonly name = 'AuthoritativeOutcomeEvidenceReplayError'

  constructor(message: string) {
    super(message)
    Object.setPrototypeOf(this, new.target.prototype)
  }
}

/**
 * Resolve authoritative receipt provenance first, bind it to the signed
 * outcome bundle, and only then invoke the existing persistence-capable replay.
 */
export async function replayAuthoritativeOutcomeEvidenceV1(
  loop: MetacognitiveLoop,
  artifactStore: ReadableOutcomeEvidenceArtifactStore,
  allocatedSequence: SequenceNumber,
  trustedOutcomeContext: TrustedOutcomeReplayContextV1,
  evidence: OutcomeReplayEvidenceV1,
  receiptSource: CrossRuntimeReceiptSourceV1,
  terminalReceiptId: SHA256Hex,
  trustedReceiptContext: TrustedReceiptResolutionContextV1,
): Promise<AuthoritativeOutcomeEvidenceReplayResultV1> {
  // This must remain the first fallible boundary: unverifiable provenance may
  // never reach the outcome artifact store or advance the metacognitive loop.
  const resolvedDecision = await resolveAndVerifyCrossRuntimeReceiptChainV1(
    receiptSource,
    terminalReceiptId,
    trustedReceiptContext,
  )
  const decision = await verifyCrossRuntimeReceiptVerificationDecisionDigestV1(
    resolvedDecision,
  )

  const evidenceSnapshot = snapshotIJson(evidence, 'authoritative outcome replay evidence')
  const terminal = evidenceSnapshot.input.terminal_execution
  if (terminal === undefined) {
    fail('authoritative receipt provenance requires terminal execution evidence')
  }

  const expectedTerminal = expectedTerminalDisposition(decision)
  const authority = evidenceSnapshot.input.authority
  const baseline = evidenceSnapshot.input.baseline.snapshot
  const proposal = evidenceSnapshot.input.baseline.proposal
  const post = evidenceSnapshot.input.post_snapshot

  assertBinding(
    decision.authority_level,
    proposal.consequence_class,
    'receipt authority level and proposal consequence class',
  )
  assertBinding(
    decision.actor_identity_root,
    authority.execution_identity_root,
    'receipt actor and authority execution identity',
  )
  assertBinding(
    decision.actor_identity_root,
    terminal.execution_identity_root,
    'receipt actor and terminal execution identity',
  )
  assertBinding(
    decision.workspace_identity_root,
    authority.workspace_binding,
    'receipt and authority workspace',
  )
  assertBinding(
    decision.workspace_identity_root,
    terminal.workspace_binding,
    'receipt and terminal workspace',
  )
  assertBinding(
    decision.action_digest,
    authority.requested_action_digest,
    'receipt and authority action',
  )
  assertBinding(
    decision.action_digest,
    terminal.requested_action_digest,
    'receipt and terminal action',
  )
  assertBinding(
    'ADMITTED',
    authority.outcome,
    'legacy authority admission outcome',
  )
  assertBinding(
    'ADMITTED',
    terminal.lease_outcome,
    'legacy lease admission outcome',
  )
  assertBinding(
    decision.authority_receipt_hash,
    authority.authority_receipt_root,
    'authoritative and legacy authority receipt',
  )
  assertBinding(
    decision.authority_receipt_hash,
    terminal.authority_receipt_root,
    'authoritative and terminal authority receipt',
  )
  assertBinding(
    decision.lease_authorization_receipt_hash,
    terminal.lease_authorization_receipt_root,
    'authoritative and legacy lease authorization receipt',
  )
  assertBinding(
    decision.before_state_root,
    baseline.state_root,
    'receipt pre-state and evidence baseline',
  )
  assertBinding(
    decision.before_state_root,
    terminal.pre_state_root,
    'receipt and terminal pre-state',
  )
  assertBinding(
    decision.after_state_root,
    post.state_root,
    'receipt post-state and evidence post snapshot',
  )
  assertBinding(
    decision.after_state_root,
    terminal.post_state_root,
    'receipt and terminal post-state',
  )
  assertBinding(
    decision.result_digest,
    terminal.provider_result_digest,
    'receipt and provider result',
  )
  assertBinding(
    decision.terminal_receipt_id,
    terminal.mutation_receipt_root,
    'authoritative and legacy mutation receipt',
  )
  assertBinding(
    'VERIFIED',
    terminal.receipt_chain_status,
    'authoritative receipt-chain status',
  )
  assertBinding(
    decision.chain_digest,
    terminal.receipt_chain_verification_root,
    'authoritative receipt-chain digest',
  )
  assertBinding(
    expectedTerminal.durableStatus,
    terminal.durable_status,
    'receipt and terminal durable status',
  )
  assertBinding(
    expectedTerminal.outcome,
    terminal.outcome,
    'receipt and terminal outcome',
  )

  // Reconstruct all terminal fields available from the resolver. Equality was
  // checked above so the verifier certificate remains bound to these exact
  // authoritative values; the subsequent replay authenticates that signature.
  const authoritativeEvidence = deepFreeze({
    input: {
      ...evidenceSnapshot.input,
      terminal_execution: {
        ...terminal,
        execution_identity_root: decision.actor_identity_root,
        workspace_binding: decision.workspace_identity_root,
        authority_receipt_root: decision.authority_receipt_hash,
        requested_action_digest: decision.action_digest,
        lease_authorization_receipt_root: decision.lease_authorization_receipt_hash,
        mutation_receipt_root: decision.terminal_receipt_id,
        receipt_chain_status: 'VERIFIED' as const,
        receipt_chain_verification_root: decision.chain_digest,
        durable_status: expectedTerminal.durableStatus,
        outcome: expectedTerminal.outcome,
        pre_state_root: decision.before_state_root,
        post_state_root: decision.after_state_root,
        provider_result_digest: decision.result_digest,
      },
    },
    trust_policy: evidenceSnapshot.trust_policy,
  })

  const result = await replayAuthenticatedOutcomeEvidenceV1(
    loop,
    artifactStore,
    allocatedSequence,
    trustedOutcomeContext,
    authoritativeEvidence,
  )
  return Object.freeze({
    ...result,
    provenance_status: AUTHORITATIVE_RECEIPT_PROVENANCE_VERIFIED,
    provenance_decision: decision,
  })
}

function expectedTerminalDisposition(
  decision: CrossRuntimeReceiptVerificationDecisionV1,
): { readonly durableStatus: DurableTerminalStatus; readonly outcome: TerminalExecutionOutcome } {
  switch (decision.terminal_receipt_kind) {
    case 'MUTATION_COMPLETED':
      if (decision.terminal_outcome === 'COMPLETED') {
        return { durableStatus: 'COMPLETED', outcome: 'SUCCEEDED' }
      }
      break
    case 'MUTATION_DENIED':
      if (decision.terminal_outcome === 'DENIED') {
        return { durableStatus: 'DENIED', outcome: 'DENIED' }
      }
      break
    case 'MUTATION_FAILED':
      if (decision.terminal_outcome === 'FAILED') {
        return { durableStatus: 'FAILED', outcome: 'FAILED' }
      }
      break
    case 'MUTATION_CANCELLED':
      fail('cancelled mutation receipt chains cannot advance outcome replay')
    default:
      fail('receipt chain does not terminate in mutation outcome evidence')
  }
  return fail('receipt terminal kind and outcome are inconsistent')
}

function snapshotIJson<T>(value: T, label: string): Readonly<T> {
  try {
    assertIJsonValue(value, label)
    const snapshot = structuredClone(value) as T
    assertIJsonValue(snapshot, label)
    return deepFreeze(snapshot)
  } catch (error) {
    if (error instanceof AuthoritativeOutcomeEvidenceReplayError) throw error
    fail(`${label} is not a closed I-JSON value: ${error instanceof Error ? error.message : String(error)}`)
  }
}

function assertBinding(actual: string, expected: string, label: string): void {
  if (actual !== expected) fail(`${label} binding mismatch`)
}

function fail(message: string): never {
  throw new AuthoritativeOutcomeEvidenceReplayError(message)
}
