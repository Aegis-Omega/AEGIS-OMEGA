import { hashValue } from '../../core/hashing.js'
import type { SHA256Hex } from '../../core/types.js'

export interface CanonicalEvidenceRef {
  readonly receipt_hash: SHA256Hex
  readonly admission_root: SHA256Hex
  readonly artifact_digest: SHA256Hex
}

export type ContinuationTransport =
  | 'OPENAI_PREVIOUS_RESPONSE_ID'
  | 'OPENAI_ENCRYPTED_REPLAY'
  | 'AEGIS_STRUCTURED_CONTINUATION'

export type ProviderContinuationHandle =
  | Readonly<{
      transport: 'OPENAI_PREVIOUS_RESPONSE_ID'
      previous_response_id: string
      provider_compaction_item_refs?: readonly string[]
      opaque_payload_digest: SHA256Hex
    }>
  | Readonly<{
      transport: 'OPENAI_ENCRYPTED_REPLAY'
      /**
       * Opaque references to the complete stateless Responses context window,
       * in provider replay order. This includes prior user input and every
       * provider output item required for continuation (reasoning, messages,
       * tool items, compaction items, etc.). Tier 2 stores references/digests
       * only; payloads are resolved ephemerally at request construction.
       */
      stateless_context_item_refs: readonly string[]
      provider_compaction_item_refs?: readonly string[]
      opaque_payload_digest: SHA256Hex
    }>
  | Readonly<{
      transport: 'AEGIS_STRUCTURED_CONTINUATION'
      structured_checkpoint_digest: SHA256Hex
      opaque_payload_digest: SHA256Hex
    }>

export interface WorkingCognitiveStateV1 {
  readonly schema_version: '1.0.0'
  readonly lineage_root: SHA256Hex
  readonly objective: string
  readonly active_plan: readonly string[]
  readonly hypotheses: readonly string[]
  readonly falsified_hypotheses: readonly string[]
  readonly unresolved_obligations: readonly string[]
  readonly evidence_refs: readonly CanonicalEvidenceRef[]
  readonly artifact_refs: readonly SHA256Hex[]
  readonly next_actions: readonly string[]
  readonly provider_continuation?: ProviderContinuationHandle
  readonly budget_state: Readonly<{
    token_budget_remaining: number
    action_budget_remaining: number
  }>
}

function assertBudgetState(state: WorkingCognitiveStateV1): void {
  for (const [name, value] of Object.entries(state.budget_state)) {
    if (!Number.isSafeInteger(value) || value < 0) {
      throw new RangeError(`Cognitive ${name} must be a non-negative safe integer`)
    }
  }
}

function stateDigestPayload(state: WorkingCognitiveStateV1): Readonly<Record<string, unknown>> {
  assertBudgetState(state)
  return Object.freeze({
    schema_version: state.schema_version,
    lineage_root: state.lineage_root,
    objective: state.objective,
    active_plan: state.active_plan,
    hypotheses: state.hypotheses,
    falsified_hypotheses: state.falsified_hypotheses,
    unresolved_obligations: state.unresolved_obligations,
    evidence_refs: state.evidence_refs,
    artifact_refs: state.artifact_refs,
    next_actions: state.next_actions,
    provider_continuation: state.provider_continuation ?? null,
    budget_state: state.budget_state,
  })
}

/**
 * Canonical Tier-2 identity: RFC 8785/JCS -> UTF-8 -> SHA-256 through the
 * repository's single integrity primitive. Portable plaintext chain-of-thought
 * and embedded Tier-4 knowledge are intentionally absent from the type.
 */
export async function computeCognitiveStateDigest(
  state: WorkingCognitiveStateV1,
): Promise<SHA256Hex> {
  return hashValue(stateDigestPayload(state))
}
