// ============================================================
// AEGIS UCI-1 — Collective Work Declaration Contracts
// EPISTEMIC TIER: T2
// Bounded declarations only; no authority, execution, effect, receipt,
// admission, or production-capability semantics.
// ============================================================

export const CONSEQUENCE_CLASSES = ['D0', 'D1', 'D2', 'D3', 'D4'] as const;
export type ConsequenceClass = (typeof CONSEQUENCE_CLASSES)[number];

export const CAPABILITY_STATUSES = [
  'NOT_TESTED',
  'PARTIAL',
  'TESTED_REFERENCE',
  'VERIFIED_FOR_PROFILE',
  'REVOKED',
] as const;
export type CapabilityStatus = (typeof CAPABILITY_STATUSES)[number];

export interface CapabilityRefV1 {
  capability_kind: 'CAPABILITY_REF_V1';
  capability_id: string;
  status: CapabilityStatus;
  profile?: string;
}

export interface IntentEnvelopeV1 {
  schema_version: '1.0.0';
  intent_kind: 'INTENT_ENVELOPE_V1';
  intent_id: string;
  intent_digest: string;
  actor_identity: string;
  session_identity: string;
  policy_commitment: string;
  authority_epoch: number;
  input_artifact_digests: string[];
  requested_capability_ids: string[];
  max_cost_microunits: number;
  max_tokens: number;
  max_duration_seconds: number;
  consequence_ceiling: ConsequenceClass;
  deterministic_nonce: string;
}

export interface CollectiveWorkNodeV1 {
  schema_version: '1.0.0';
  work_node_kind: 'COLLECTIVE_WORK_NODE_V1';
  work_node_id: string;
  objective_digest: string;
  intent_digest: string;
  required_capabilities: CapabilityRefV1[];
  allowed_providers: string[];
  allowed_tools: string[];
  dependency_ids: string[];
  input_artifact_digests: string[];
  max_cost_microunits: number;
  max_tokens: number;
  max_duration_seconds: number;
  consequence_class: ConsequenceClass;
  authority_epoch: number;
  policy_commitment: string;
  target_commitment: string;
  pre_state_commitment: string;
  nonce: string;
}

export interface CollectiveWorkGraphV1 {
  schema_version: '1.0.0';
  graph_kind: 'COLLECTIVE_WORK_GRAPH_V1';
  graph_id: string;
  intent_digest: string;
  nodes: CollectiveWorkNodeV1[];
  policy_commitment: string;
  authority_epoch: number;
  graph_nonce: string;
}
