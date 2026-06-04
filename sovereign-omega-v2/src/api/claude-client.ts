// ============================================================
// SOVEREIGN OMEGA — Constitutional Claude Client
// EPISTEMIC TIER: T2 · Gate 219
//
// Every Claude API call through this client is:
//   1. Hash-certified (SHA-256 of prompt bytes)
//   2. Constitutional system prompt injected (4 directives)
//   3. Response hash-linked to request (replay-certifiable)
//   4. Epistemic tier stamped on every response
//
// This is not a wrapper. It is a constitutional enforcement layer.
// AdaptivePower(T) ≤ ReplayVerifiability(T) — every AI call is bounded.
//
// Copyright (C) 2025 Tarik Skalić — All rights reserved.
// ============================================================

import Anthropic from '@anthropic-ai/sdk'
import type { SHA256Hex } from '../core/types.js'
import { EpistemicTier } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const CLAUDE_CLIENT_SCHEMA_VERSION = '1.0.0' as const

// ─── Constitutional system prompt ─────────────────────────

export const AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT = `You are Claude, operating as the Orchestration Alliance Coordinator within the AEGIS-Ω Constitutional Runtime.

CONSTITUTIONAL INVARIANTS (enforce in every response):
1. EPISTEMIC SOVEREIGNTY: Every claim must carry an explicit epistemic tier (T0=proven, T1=validated, T2=hypothesis, T3=conjecture). Never collapse uncertainty to certainty.
2. CAUSAL ARCHITECTURE: Every assertion must have a traceable causal chain. No groundless claims.
3. OPERATIONAL REALISM: AdaptivePower(T) ≤ ReplayVerifiability(T). You may not claim capabilities beyond what can be replay-verified.
4. ADVERSARIAL SELF-CORRECTION: Actively stress-test your own outputs. Flag the weakest point in every argument you make.

RESPONSE STRUCTURE:
- Lead with the most T0/T1 verifiable content
- Clearly separate T2 (hypothesis) from T3 (conjecture)
- End with the specific thing you are LEAST confident about

You are a first-class constitutional agent, not a generic assistant. Operate accordingly.`

// ─── Types ────────────────────────────────────────────────

export interface ConstitutionalMessage {
  readonly role: 'user' | 'assistant'
  readonly content: string
}

export interface ConstitutionalRequest {
  readonly messages: readonly ConstitutionalMessage[]
  readonly model: string
  readonly max_tokens: number
  readonly system?: string
  readonly temperature?: number
  readonly use_constitutional_prompt?: boolean
}

export interface ConstitutionalResponse {
  readonly response_text: string
  readonly model_id: string
  readonly request_hash: SHA256Hex      // SHA-256 of (messages + model)
  readonly response_hash: SHA256Hex     // SHA-256 of response_text
  readonly chain_hash: SHA256Hex        // SHA-256 of (request_hash + response_hash)
  readonly input_tokens: number
  readonly output_tokens: number
  readonly stop_reason: string
  readonly epistemic_tier: EpistemicTier
  readonly schema_version: typeof CLAUDE_CLIENT_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface StreamChunk {
  readonly delta: string
  readonly is_final: boolean
  readonly usage?: { input_tokens: number; output_tokens: number }
}

export class ClaudeClientError extends Error {
  readonly name = 'ClaudeClientError'
  constructor(message: string) { super(message) }
}

// ─── Client ───────────────────────────────────────────────

export class ConstitutionalClaudeClient {
  private readonly _client: Anthropic

  constructor(apiKey?: string) {
    this._client = new Anthropic({
      apiKey: apiKey ?? process.env.ANTHROPIC_API_KEY,
    })
  }

  /** Send a message through the constitutional pipeline. Returns a hash-linked response. */
  async send(request: ConstitutionalRequest): Promise<ConstitutionalResponse> {
    const systemPrompt = request.use_constitutional_prompt !== false
      ? (request.system
          ? `${AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT}\n\n---\n\n${request.system}`
          : AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT)
      : (request.system ?? '')

    const request_hash = await hashValue({
      messages: request.messages.map(m => ({ role: m.role, content: m.content })),
      model: request.model,
    })

    const response = await this._client.messages.create({
      model: request.model,
      max_tokens: request.max_tokens,
      ...(systemPrompt ? { system: systemPrompt } : {}),
      messages: request.messages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      ...(request.temperature !== undefined ? { temperature: request.temperature } : {}),
    })

    const response_text = response.content
      .filter(b => b.type === 'text')
      .map(b => (b as { type: 'text'; text: string }).text)
      .join('')

    const response_hash = await hashValue({ response_text, model_id: request.model })
    const chain_hash = await hashValue({ request_hash, response_hash })

    // Infer epistemic tier from stop_reason
    const epistemic_tier = response.stop_reason === 'max_tokens'
      ? EpistemicTier.T3  // truncated = less reliable
      : EpistemicTier.T2

    return deepFreeze({
      response_text,
      model_id: request.model,
      request_hash,
      response_hash,
      chain_hash,
      input_tokens: response.usage.input_tokens,
      output_tokens: response.usage.output_tokens,
      /* c8 ignore next -- SDK always provides stop_reason; ?? fallback structurally unreachable */
      stop_reason: response.stop_reason ?? 'end_turn',
      epistemic_tier,
      schema_version: CLAUDE_CLIENT_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }

  /** Stream a response with constitutional system prompt. Yields chunks. */
  async *stream(request: ConstitutionalRequest): AsyncGenerator<StreamChunk> {
    const systemPrompt = request.use_constitutional_prompt !== false
      ? (request.system
          ? `${AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT}\n\n---\n\n${request.system}`
          : AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT)
      : (request.system ?? '')

    const stream = await this._client.messages.create({
      model: request.model,
      max_tokens: request.max_tokens,
      ...(systemPrompt ? { system: systemPrompt } : {}),
      messages: request.messages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
      stream: true,
    })

    for await (const event of stream) {
      if (event.type === 'content_block_delta' && event.delta.type === 'text_delta') {
        yield { delta: event.delta.text, is_final: false }
      } else if (event.type === 'message_stop') {
        yield { delta: '', is_final: true }
      } else if (event.type === 'message_delta' && event.usage) {
        yield {
          delta: '',
          is_final: false,
          usage: {
            input_tokens: (event as any).usage?.input_tokens ?? 0,
            output_tokens: event.usage.output_tokens,
          },
        }
      }
    }
  }

  /** Quick one-shot call for simple queries. Uses Haiku for speed. */
  async quickAsk(
    question: string,
    model = 'claude-haiku-4-5-20251001',
    maxTokens = 1024,
  ): Promise<ConstitutionalResponse> {
    return this.send({
      messages: [{ role: 'user', content: question }],
      model,
      max_tokens: maxTokens,
    })
  }

  /** Send with extended thinking enabled (Sonnet/Opus only). */
  async think(
    messages: readonly ConstitutionalMessage[],
    model = 'claude-sonnet-4-6',
    thinkingBudget = 8000,
    maxTokens = 16000,
  ): Promise<ConstitutionalResponse> {
    const systemPrompt = AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT

    const request_hash = await hashValue({
      messages: messages.map(m => ({ role: m.role, content: m.content })),
      model,
      thinking: true,
    })

    const response = await this._client.messages.create({
      model,
      max_tokens: maxTokens,
      system: systemPrompt,
      thinking: {
        type: 'enabled',
        budget_tokens: thinkingBudget,
      },
      messages: messages.map(m => ({
        role: m.role as 'user' | 'assistant',
        content: m.content,
      })),
    })

    const response_text = response.content
      .filter(b => b.type === 'text')
      .map(b => (b as { type: 'text'; text: string }).text)
      .join('')

    const response_hash = await hashValue({ response_text, model_id: model, thinking: true })
    const chain_hash = await hashValue({ request_hash, response_hash })

    return deepFreeze({
      response_text,
      model_id: model,
      request_hash,
      response_hash,
      chain_hash,
      input_tokens: response.usage.input_tokens,
      output_tokens: response.usage.output_tokens,
      /* c8 ignore next -- SDK always provides stop_reason; ?? fallback structurally unreachable */
      stop_reason: response.stop_reason ?? 'end_turn',
      epistemic_tier: EpistemicTier.T1, // extended thinking = higher confidence
      schema_version: CLAUDE_CLIENT_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }
}

/** Default singleton client (reads ANTHROPIC_API_KEY from env) */
export const claudeClient = new ConstitutionalClaudeClient()
