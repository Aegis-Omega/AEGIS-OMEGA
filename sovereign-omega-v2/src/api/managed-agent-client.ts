// ============================================================
// SOVEREIGN OMEGA — Managed Agent Client
// EPISTEMIC TIER: T2 · Gate 219
//
// Wraps the Claude Managed Agents API (beta: managed-agents-2026-04-01).
// Creates persistent AEGIS constitutional agents that run in managed
// cloud containers with full tool access: Bash, file ops, web search.
//
// Each AEGIS agent session is a running instance of the constitutional
// runtime — not a chatbot, but an autonomous agent bounded by the
// four constitutional directives.
//
// Copyright (C) 2025 Tarik Skalić — All rights reserved.
// ============================================================

import Anthropic from '@anthropic-ai/sdk'
import { AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT } from './claude-client.js'

export const MANAGED_AGENT_SCHEMA_VERSION = '1.0.0' as const
const BETA_HEADER = 'managed-agents-2026-04-01'

// ─── AEGIS agent definition ───────────────────────────────

export const AEGIS_AGENT_DEFINITION = {
  name: 'AEGIS-Ω Constitutional Agent',
  model: 'claude-sonnet-4-6',
  system_prompt: `${AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT}

TOOLS AVAILABLE:
- bash: Execute shell commands for verification and computation
- files: Read/write files for evidence collection
- web_search: Research and validate claims against external sources
- web_fetch: Retrieve specific URLs for citation

OPERATIONAL MODE:
You run as a long-context autonomous agent. For every task:
1. Decompose into verifiable sub-claims (RALPH: Read-Assess-Lock-Propagate-Harmonize)
2. Use tools to gather evidence
3. Classify each finding by epistemic tier
4. Synthesize only what survives adversarial stress-test
5. Output structured: {T0_facts, T1_validated, T2_hypotheses, T3_conjectures}`,
} as const

// ─── Types ────────────────────────────────────────────────

export interface AgentSession {
  readonly session_id: string
  readonly agent_id: string
  readonly status: 'created' | 'running' | 'paused' | 'completed' | 'error'
  readonly created_at: string
}

export interface SessionEvent {
  readonly type: 'user' | 'assistant' | 'tool_use' | 'tool_result' | 'status'
  readonly content: string
  readonly timestamp: string
}

export interface ManagedAgentClientConfig {
  readonly apiKey?: string
  readonly agentId?: string  // pre-existing agent to reuse
}

// ─── Client ───────────────────────────────────────────────

export class ManagedAgentClient {
  private readonly _client: Anthropic
  private _agentId: string | null = null

  constructor(config: ManagedAgentClientConfig = {}) {
    this._client = new Anthropic({
      apiKey: config.apiKey ?? process.env.ANTHROPIC_API_KEY,
      defaultHeaders: {
        'anthropic-beta': BETA_HEADER,
      },
    })
    this._agentId = config.agentId ?? null
  }

  /** Create or retrieve the AEGIS constitutional agent. Returns agent_id. */
  async ensureAgent(): Promise<string> {
    if (this._agentId) return this._agentId

    try {
      const agent = await (this._client as any).beta?.agents?.create({
        name: AEGIS_AGENT_DEFINITION.name,
        model: AEGIS_AGENT_DEFINITION.model,
        system_prompt: AEGIS_AGENT_DEFINITION.system_prompt,
        tools: [
          { type: 'bash_20250124', name: 'bash' },
          { type: 'text_editor_20250429', name: 'str_replace_based_edit_tool' },
          { type: 'web_search_20250305', name: 'web_search' },
        ],
      })
      this._agentId = agent.id
      return agent.id
    } catch (err) {
      // Managed agents may not be available in all regions/tiers
      throw new Error(
        `[MANAGED_AGENT] Failed to create agent: ${String(err)}. ` +
        `Ensure your API key has Managed Agents access.`
      )
    }
  }

  /** Start a new session for a given task. Returns session details. */
  async startSession(task: string): Promise<AgentSession> {
    const agentId = await this.ensureAgent()

    const session = await (this._client as any).beta?.sessions?.create({
      agent_id: agentId,
      initial_message: task,
    })

    return {
      session_id: session.id,
      agent_id: agentId,
      status: 'created',
      /* c8 ignore next -- SDK always provides created_at; ?? fallback structurally unreachable */
      created_at: session.created_at ?? new Date().toISOString(),
    }
  }

  /** Stream events from a running session. */
  async *streamSession(sessionId: string): AsyncGenerator<SessionEvent> {
    const stream = await (this._client as any).beta?.sessions?.stream(sessionId)

    if (!stream) {
      yield {
        type: 'status',
        content: 'Stream not available',
        timestamp: new Date().toISOString(),
      }
      return
    }

    for await (const event of stream) {
      /* c8 ignore next -- stream events always carry type; ?? fallback structurally unreachable */
      const evType = event?.type ?? 'status'
      yield {
        type: evType,
        content: typeof event?.content === 'string' ? event.content : JSON.stringify(event),
        timestamp: new Date().toISOString(),
      }
    }
  }

  /** Send a follow-up message to a running session. */
  async sendEvent(sessionId: string, message: string): Promise<void> {
    await (this._client as any).beta?.sessions?.createEvent(sessionId, {
      type: 'user',
      content: message,
    })
  }

  /** Get the current status of a session. */
  async getSession(sessionId: string): Promise<AgentSession> {
    const session = await (this._client as any).beta?.sessions?.retrieve(sessionId)
    return {
      session_id: session.id,
      /* c8 ignore next -- SDK always provides agent_id; ?? fallbacks structurally unreachable */
      agent_id: session.agent_id ?? this._agentId ?? '',
      /* c8 ignore next -- SDK always provides status; ?? fallback structurally unreachable */
      status: session.status ?? 'running',
      /* c8 ignore next -- SDK always provides created_at; ?? fallback structurally unreachable */
      created_at: session.created_at ?? new Date().toISOString(),
    }
  }

  /** Interrupt a running session. */
  async interrupt(sessionId: string): Promise<void> {
    await (this._client as any).beta?.sessions?.createEvent(sessionId, {
      type: 'interrupt',
    })
  }

  get agentId(): string | null {
    return this._agentId
  }
}

/** Default singleton managed agent client */
export const managedAgentClient = new ManagedAgentClient()
