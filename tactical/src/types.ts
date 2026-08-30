// Tactical dashboard types — DEPARTMENTS re-exported from canonical shared contract to prevent drift.

export type CollaborationMode =
  | 'revenue' | 'analysis' | 'gtm' | 'retention'
  | 'competitive' | 'technical' | 'regulatory' | 'fundraising'

export type SseEventType = 'dag_step' | 'agent_event' | 'tool_call' | 'error' | 'completion' | 'heartbeat'

export interface SseEvent {
  type: SseEventType
  execution_id: string
  timestamp: string
  payload: Record<string, unknown>
}

export interface CollaborationResult {
  cycle_id: string
  objective: string
  mode: CollaborationMode
  departments_collaborated: number
  artifacts: readonly { role: string; output: string }[]
  projection: {
    first_year_arr_usd?: number
    tier?: string
    governed_note?: string
  }
  constitutional_audit: {
    verdict: 'APPROVED' | 'FLAG' | 'QUARANTINE'
    concerns?: string[]
  }
  chain_valid: boolean
  audit_chain_hash: string
  execution_id: string
}

export type AgentState = 'idle' | 'active' | 'done' | 'error'

export interface AgentNode {
  id: string       // dept_id e.g. 'REV-01'
  role: string
  category: string
  state: AgentState
  index: number    // 0–38
}

export type SystemStatus = 'IDLE' | 'INITIALIZING' | 'STREAMING' | 'COMPLETE' | 'ERROR'

export interface LogEntry {
  id: string
  ts: string
  level: 'SYSTEM' | 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR' | 'STREAM'
  message: string
}

// Single source of truth: tactical re-exports the canonical 39-dept roster.
// Adding a 40th dept to platform-contract.ts automatically appears here.
export { PLATFORM_DEPARTMENTS as DEPARTMENTS } from '../../packages/shared/lib/platform-contract.js'

export const CATEGORY_COLOR: Record<string, string> = {
  revenue:        'border-emerald-500 bg-emerald-500/20 text-emerald-400',
  marketing:      'border-blue-500 bg-blue-500/20 text-blue-400',
  sales:          'border-cyan-500 bg-cyan-500/20 text-cyan-400',
  product:        'border-purple-500 bg-purple-500/20 text-purple-400',
  engineering:    'border-orange-500 bg-orange-500/20 text-orange-400',
  operations:     'border-yellow-500 bg-yellow-500/20 text-yellow-400',
  research:       'border-pink-500 bg-pink-500/20 text-pink-400',
  finance:        'border-teal-500 bg-teal-500/20 text-teal-400',
  executive:      'border-red-500 bg-red-500/20 text-red-400',
  governance:     'border-amber-500 bg-amber-500/20 text-amber-400',
  constitutional: 'border-white bg-white/20 text-white',
}
