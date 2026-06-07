/**
 * /platform/* API Contract — Single Source of Truth
 * EPISTEMIC TIER: T0 (schema definitions are mechanically enforced at runtime)
 *
 * All /platform/* endpoints on aegis-vertex.aegisomega.com derive their
 * request/response shapes exclusively from this file. The Python bridge
 * validates every payload against these shapes before responding.
 *
 * Breaking changes: increment PLATFORM_CONTRACT_VERSION and add /platform/v2/*.
 * The /platform/* namespace aliases the current version until deprecated.
 */

// ── Versioning ─────────────────────────────────────────────────────────────────

export const PLATFORM_CONTRACT_VERSION = '1.0.0' as const

// ── Shared envelope (every response is wrapped in this) ───────────────────────

export interface PlatformEnvelope<T> {
  readonly contract_version: typeof PLATFORM_CONTRACT_VERSION
  readonly execution_id: string
  readonly timestamp: string               // ISO-8601, UTC
  readonly is_replay_reconstructable: true
  readonly data: T
}

// ── SSE event contract (GET /platform/executions/live) ─────────────────────────
// No deviations permitted. All events must match this exact shape.

export type SseEventType =
  | 'dag_step'
  | 'agent_event'
  | 'tool_call'
  | 'error'
  | 'completion'
  | 'heartbeat'

export interface SseEvent {
  readonly type: SseEventType
  readonly execution_id: string
  readonly timestamp: string               // ISO-8601, UTC
  readonly payload: SseDagStepPayload | SseAgentEventPayload | SseToolCallPayload | SseErrorPayload | SseCompletionPayload | SseHeartbeatPayload
}

/** type: 'dag_step' — a department activating in the execution graph */
export interface SseDagStepPayload {
  readonly dept_id: string                 // e.g. 'REV-01'
  readonly dept_name: string               // e.g. 'Strategy'
  readonly category: string               // e.g. 'revenue'
  readonly step_index: number             // 0-based
  readonly total_steps: number            // always 39
}

/** type: 'agent_event' — a department has produced output */
export interface SseAgentEventPayload {
  readonly dept_id: string
  readonly role: string
  readonly output_preview: string         // max 120 chars
}

/** type: 'tool_call' — a tool invocation within agent execution */
export interface SseToolCallPayload {
  readonly tool_name: string
  readonly args_hash: string              // SHA-256 of serialized args
}

/** type: 'error' — execution failed */
export interface SseErrorPayload {
  readonly code: PlatformErrorCode
  readonly message: string
}

/** type: 'completion' — execution finished successfully */
export interface SseCompletionPayload extends CollaborationResult {}

/** type: 'heartbeat' — keepalive (no meaningful data) */
export interface SseHeartbeatPayload {
  readonly seq: number
}

// ── POST /platform/collaborate ─────────────────────────────────────────────────

export interface CollaborationRequest {
  readonly objective: string
  readonly mode: CollaborationMode
  readonly live: boolean
}

export type CollaborationMode = 'revenue' | 'analysis' | 'gtm' | 'retention'

export interface CollaborationResult {
  readonly cycle_id: string
  readonly objective: string
  readonly mode: CollaborationMode
  readonly departments_collaborated: number
  readonly artifacts: readonly DeptArtifact[]
  readonly projection: CollaborationProjection
  readonly constitutional_audit: ConstitutionalAudit
  readonly chain_valid: boolean
  readonly audit_chain_hash: string
  readonly execution_id: string
}

export interface DeptArtifact {
  readonly role: string
  readonly output: string
}

export interface CollaborationProjection {
  readonly first_year_arr_usd?: number
  readonly tier?: string
  readonly governed_note?: string
}

export interface ConstitutionalAudit {
  readonly verdict: ConstitutionalVerdict
  readonly concerns?: readonly string[]
}

export type ConstitutionalVerdict = 'APPROVED' | 'FLAG' | 'QUARANTINE'

// ── POST /platform/executions (async) ─────────────────────────────────────────

export interface ExecutionInitRequest extends CollaborationRequest {}

export interface ExecutionInitResult {
  readonly execution_id: string
  readonly stream_url: string             // /platform/executions/live?id={execution_id}
  readonly status: 'pending'
}

// ── GET /platform/executions/{id} ─────────────────────────────────────────────

export interface ExecutionGetResult {
  readonly execution_id: string
  readonly status: 'pending' | 'running' | 'complete' | 'error'
  readonly result?: CollaborationResult   // present when status === 'complete'
  readonly error?: string                 // present when status === 'error'
}

// ── GET /platform/status ──────────────────────────────────────────────────────

export interface PlatformStatus {
  readonly version: string
  readonly contract_version: typeof PLATFORM_CONTRACT_VERSION
  readonly total_agents: number
  readonly chain_valid: boolean
  readonly audit_chain_hash: string
  readonly available: boolean
  readonly reason?: string               // present when available === false
  readonly usage?: PlatformStatusUsage   // present when x-api-key header is supplied
}

/** Per-key usage info — returned when x-api-key is provided to GET /platform/status */
export interface PlatformStatusUsage {
  readonly customer_email: string
  readonly tier: 'explorer' | 'operator' | 'sovereign'
  readonly usage_count: number
  readonly usage_limit: number
  readonly remaining_runs: number
}

// ── Error schema (all endpoints on 4xx/5xx) ──────────────────────────────────

export type PlatformErrorCode =
  | 'UNAUTHORIZED'
  | 'INVALID_REQUEST'
  | 'RATE_LIMITED'
  | 'NOT_FOUND'
  | 'INTERNAL'

export interface PlatformError {
  readonly error: string
  readonly code: PlatformErrorCode
  readonly execution_id?: string
}

// ── Response header contract (all /platform/* responses) ─────────────────────
// Headers added by the bridge on every response:
//   X-Contract-Version: {PLATFORM_CONTRACT_VERSION}
//   X-Git-SHA: {AEGIS_GIT_SHA env var, or 'dev'}
//   Access-Control-Allow-Origin: *
//   Access-Control-Allow-Headers: Content-Type, x-api-key

// ── Department roster (39 departments, deterministic ordering) ────────────────

export const PLATFORM_DEPARTMENTS = [
  { id: 'REV-01', role: 'Strategy',    category: 'revenue' },
  { id: 'REV-02', role: 'Finance',     category: 'revenue' },
  { id: 'REV-03', role: 'Pricing',     category: 'revenue' },
  { id: 'MKT-01', role: 'Brand',       category: 'marketing' },
  { id: 'MKT-02', role: 'Content',     category: 'marketing' },
  { id: 'MKT-03', role: 'SEO',         category: 'marketing' },
  { id: 'MKT-04', role: 'Paid',        category: 'marketing' },
  { id: 'MKT-05', role: 'Social',      category: 'marketing' },
  { id: 'SLS-01', role: 'Outbound',    category: 'sales' },
  { id: 'SLS-02', role: 'Inbound',     category: 'sales' },
  { id: 'SLS-03', role: 'Partner',     category: 'sales' },
  { id: 'SLS-04', role: 'Enterprise',  category: 'sales' },
  { id: 'PRD-01', role: 'Product',     category: 'product' },
  { id: 'PRD-02', role: 'UX',          category: 'product' },
  { id: 'PRD-03', role: 'Data',        category: 'product' },
  { id: 'PRD-04', role: 'API',         category: 'product' },
  { id: 'ENG-01', role: 'Backend',     category: 'engineering' },
  { id: 'ENG-02', role: 'Frontend',    category: 'engineering' },
  { id: 'ENG-03', role: 'Infra',       category: 'engineering' },
  { id: 'ENG-04', role: 'Security',    category: 'engineering' },
  { id: 'ENG-05', role: 'AI/ML',       category: 'engineering' },
  { id: 'OPS-01', role: 'RevOps',      category: 'operations' },
  { id: 'OPS-02', role: 'Support',     category: 'operations' },
  { id: 'OPS-03', role: 'Legal',       category: 'operations' },
  { id: 'OPS-04', role: 'Compliance',  category: 'operations' },
  { id: 'RES-01', role: 'Research',    category: 'research' },
  { id: 'RES-02', role: 'Competitive', category: 'research' },
  { id: 'RES-03', role: 'Customer',    category: 'research' },
  { id: 'FIN-01', role: 'Accounting',  category: 'finance' },
  { id: 'FIN-02', role: 'Treasury',    category: 'finance' },
  { id: 'FIN-03', role: 'Tax',         category: 'finance' },
  { id: 'EXE-01', role: 'CEO',         category: 'executive' },
  { id: 'EXE-02', role: 'COO',         category: 'executive' },
  { id: 'EXE-03', role: 'CTO',         category: 'executive' },
  { id: 'EXE-04', role: 'CFO',         category: 'executive' },
  { id: 'GOV-01', role: 'Ethics',      category: 'governance' },
  { id: 'GOV-02', role: 'Risk',        category: 'governance' },
  { id: 'CON-01', role: 'Audit',       category: 'constitutional' },
  { id: 'CON-09', role: 'Guardian',    category: 'constitutional' },
] as const satisfies readonly { id: string; role: string; category: string }[]
