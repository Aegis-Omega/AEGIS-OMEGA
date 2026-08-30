// ============================================================
// SOVEREIGN OMEGA — Anthropic SDK client tests
// EPISTEMIC TIER: T2
//
// Tests for:
//   src/api/claude-client.ts — ConstitutionalClaudeClient
//   src/api/managed-agent-client.ts — ManagedAgentClient
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// ── Hoisted mock refs ─────────────────────────────────────
// vi.hoisted ensures these run before vi.mock factories

const mocks = vi.hoisted(() => ({
  messagesCreate:     vi.fn(),
  betaAgentsCreate:   vi.fn(),
  sessionsCreate:     vi.fn(),
  sessionsStream:     vi.fn(),
  sessionsCreateEvent: vi.fn(),
  sessionsRetrieve:   vi.fn(),
}))

vi.mock('@anthropic-ai/sdk', () => ({
  default: class MockAnthropic {
    messages = { create: mocks.messagesCreate }
    beta = {
      agents:   { create: mocks.betaAgentsCreate },
      sessions: {
        create:      mocks.sessionsCreate,
        stream:      mocks.sessionsStream,
        createEvent: mocks.sessionsCreateEvent,
        retrieve:    mocks.sessionsRetrieve,
      },
    }
    constructor(_opts?: unknown) {}
  },
}))

import {
  ConstitutionalClaudeClient,
  ClaudeClientError,
  CLAUDE_CLIENT_SCHEMA_VERSION,
  AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT,
} from '../../src/api/claude-client.js'
import {
  ManagedAgentClient,
  MANAGED_AGENT_SCHEMA_VERSION,
} from '../../src/api/managed-agent-client.js'
import { EpistemicTier } from '../../src/core/types.js'

// Clear call records between every test to avoid cross-test contamination
afterEach(() => vi.clearAllMocks())

// ── Helpers ───────────────────────────────────────────────

function makeApiResponse(text: string, stopReason = 'end_turn') {
  return {
    content: [{ type: 'text', text }],
    usage:   { input_tokens: 5, output_tokens: 10 },
    stop_reason: stopReason,
  }
}

// ── CLAUDE_CLIENT_SCHEMA_VERSION + ClaudeClientError ─────

describe('CLAUDE_CLIENT_SCHEMA_VERSION', () => {
  it('is a non-empty string', () => {
    expect(typeof CLAUDE_CLIENT_SCHEMA_VERSION).toBe('string')
    expect(CLAUDE_CLIENT_SCHEMA_VERSION.length).toBeGreaterThan(0)
  })
})

describe('ClaudeClientError', () => {
  it('is an Error subclass with name=ClaudeClientError', () => {
    const err = new ClaudeClientError('test message')
    expect(err).toBeInstanceOf(Error)
    expect(err.name).toBe('ClaudeClientError')
    expect(err.message).toBe('test message')
  })
})

describe('AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT', () => {
  it('contains constitutional invariants text', () => {
    expect(AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT).toContain('CONSTITUTIONAL INVARIANTS')
  })
})

// ── ConstitutionalClaudeClient.send ───────────────────────

describe('ConstitutionalClaudeClient.send', () => {
  beforeEach(() => {
    mocks.messagesCreate.mockResolvedValue(makeApiResponse('Hello constitutional world'))
  })

  it('returns a hash-linked ConstitutionalResponse', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    const res = await client.send({
      messages: [{ role: 'user', content: 'ping' }],
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 100,
    })
    expect(res.response_text).toBe('Hello constitutional world')
    expect(res.request_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(res.response_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(res.chain_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(res.is_replay_reconstructable).toBe(true)
    expect(res.schema_version).toBe(CLAUDE_CLIENT_SCHEMA_VERSION)
  })

  it('infers T3 epistemic tier when stop_reason is max_tokens', async () => {
    mocks.messagesCreate.mockResolvedValue(makeApiResponse('short', 'max_tokens'))
    const client = new ConstitutionalClaudeClient('test-key')
    const res = await client.send({
      messages: [{ role: 'user', content: 'q' }],
      model:     'claude-haiku-4-5-20251001',
      max_tokens: 100,
    })
    expect(res.epistemic_tier).toBe(EpistemicTier.T3)
  })

  it('injects constitutional system prompt by default', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.send({
      messages: [{ role: 'user', content: 'q' }],
      model:     'claude-haiku-4-5-20251001',
      max_tokens: 100,
    })
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toContain('CONSTITUTIONAL INVARIANTS')
  })

  it('merges caller system with constitutional prompt', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.send({
      messages: [{ role: 'user', content: 'q' }],
      model:     'claude-haiku-4-5-20251001',
      max_tokens: 100,
      system:    'Custom context',
    })
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toContain('Custom context')
    expect(args.system).toContain('CONSTITUTIONAL INVARIANTS')
  })

  it('bypasses constitutional prompt when use_constitutional_prompt=false', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.send({
      messages: [{ role: 'user', content: 'q' }],
      model:     'claude-haiku-4-5-20251001',
      max_tokens: 100,
      use_constitutional_prompt: false,
    })
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toBeUndefined()
  })

  it('bypasses constitutional prompt but keeps caller system when use_constitutional_prompt=false', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.send({
      messages: [{ role: 'user', content: 'q' }],
      model:     'claude-haiku-4-5-20251001',
      max_tokens: 100,
      use_constitutional_prompt: false,
      system: 'Only caller',
    })
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toBe('Only caller')
  })

  it('passes temperature to messages.create when provided', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.send({
      messages:    [{ role: 'user', content: 'q' }],
      model:       'claude-haiku-4-5-20251001',
      max_tokens:  100,
      temperature: 0.5,
    })
    const args = mocks.messagesCreate.mock.calls[0]![0] as { temperature?: number }
    expect(args.temperature).toBe(0.5)
  })
})

// ── ConstitutionalClaudeClient.quickAsk ───────────────────

describe('ConstitutionalClaudeClient.quickAsk', () => {
  beforeEach(() => {
    mocks.messagesCreate.mockResolvedValue(makeApiResponse('Quick answer'))
  })

  it('delegates to send() with default haiku model', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    const res = await client.quickAsk('What is 1+1?')
    expect(res.response_text).toBe('Quick answer')
  })
})

// ── ConstitutionalClaudeClient.think ─────────────────────

describe('ConstitutionalClaudeClient.think', () => {
  beforeEach(() => {
    mocks.messagesCreate.mockResolvedValue({
      content: [{ type: 'text', text: 'Thinking output' }],
      usage:   { input_tokens: 50, output_tokens: 100 },
      stop_reason: 'end_turn',
    })
  })

  it('returns T1 epistemic tier (extended thinking)', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    const res = await client.think([{ role: 'user', content: 'Deep question' }])
    expect(res.epistemic_tier).toBe(EpistemicTier.T1)
    expect(res.response_text).toBe('Thinking output')
  })

  it('passes thinking budget to messages.create', async () => {
    const client = new ConstitutionalClaudeClient('test-key')
    await client.think([{ role: 'user', content: 'q' }], 'claude-sonnet-4-6', 5000, 10000)
    const args = mocks.messagesCreate.mock.calls[0]![0] as { thinking?: { budget_tokens: number } }
    expect(args.thinking?.budget_tokens).toBe(5000)
  })
})

// ── ConstitutionalClaudeClient.stream ────────────────────

describe('ConstitutionalClaudeClient.stream', () => {
  it('yields text_delta events and terminates at message_stop', async () => {
    const events = [
      { type: 'content_block_delta', delta: { type: 'text_delta', text: 'Hello' } },
      { type: 'message_delta', usage: { output_tokens: 5 } },
      { type: 'message_stop' },
    ]
    async function* gen() { for (const e of events) yield e }
    mocks.messagesCreate.mockResolvedValue(gen())

    const client = new ConstitutionalClaudeClient('test-key')
    const chunks: Array<{ delta: string; is_final: boolean }> = []
    for await (const c of client.stream({
      messages: [{ role: 'user', content: 'q' }],
      model:    'claude-haiku-4-5-20251001',
      max_tokens: 100,
    })) {
      chunks.push(c)
    }
    expect(chunks.some(c => c.delta === 'Hello')).toBe(true)
    expect(chunks.some(c => c.is_final)).toBe(true)
  })

  it('merges caller system with constitutional prompt in stream', async () => {
    async function* gen() { yield { type: 'message_stop' } }
    mocks.messagesCreate.mockResolvedValue(gen())
    const client = new ConstitutionalClaudeClient('test-key')
    for await (const _ of client.stream({
      messages: [{ role: 'user', content: 'q' }],
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 100,
      system: 'Custom context',
    })) { /* drain */ }
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toContain('Custom context')
    expect(args.system).toContain('CONSTITUTIONAL INVARIANTS')
  })

  it('omits system entirely when use_constitutional_prompt=false and no system provided', async () => {
    async function* gen() { yield { type: 'message_stop' } }
    mocks.messagesCreate.mockResolvedValue(gen())
    const client = new ConstitutionalClaudeClient('test-key')
    for await (const _ of client.stream({
      messages: [{ role: 'user', content: 'q' }],
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 100,
      use_constitutional_prompt: false,
    })) { /* drain */ }
    const args = mocks.messagesCreate.mock.calls[0]![0] as { system?: string }
    expect(args.system).toBeUndefined()
  })

  it('skips usage chunk when message_delta has no usage field', async () => {
    const events = [
      { type: 'content_block_delta', delta: { type: 'text_delta', text: 'Hi' } },
      { type: 'message_delta' },
      { type: 'message_stop' },
    ]
    async function* gen() { for (const e of events) yield e }
    mocks.messagesCreate.mockResolvedValue(gen())
    const client = new ConstitutionalClaudeClient('test-key')
    const chunks: Array<{ delta: string; is_final: boolean; usage?: unknown }> = []
    for await (const c of client.stream({
      messages: [{ role: 'user', content: 'q' }],
      model: 'claude-haiku-4-5-20251001',
      max_tokens: 100,
    })) { chunks.push(c) }
    expect(chunks.some(c => c.delta === 'Hi')).toBe(true)
    expect(chunks.some(c => c.is_final)).toBe(true)
    expect(chunks.every(c => c.usage === undefined)).toBe(true)
  })
})

// ── MANAGED_AGENT_SCHEMA_VERSION ──────────────────────────

describe('MANAGED_AGENT_SCHEMA_VERSION', () => {
  it('is a non-empty string', () => {
    expect(typeof MANAGED_AGENT_SCHEMA_VERSION).toBe('string')
  })
})

// ── ManagedAgentClient ────────────────────────────────────

describe('ManagedAgentClient', () => {
  beforeEach(() => {
    mocks.betaAgentsCreate.mockResolvedValue({ id: 'agent-xyz' })
    mocks.sessionsCreate.mockResolvedValue({ id: 'sess-abc', created_at: '2026-01-01T00:00:00Z' })
    mocks.sessionsRetrieve.mockResolvedValue({
      id: 'sess-abc', agent_id: 'agent-xyz', status: 'running', created_at: '2026-01-01T00:00:00Z',
    })
    mocks.sessionsCreateEvent.mockResolvedValue(undefined)
  })

  it('agentId is null by default', () => {
    expect(new ManagedAgentClient().agentId).toBeNull()
  })

  it('accepts pre-existing agentId in config', () => {
    expect(new ManagedAgentClient({ agentId: 'pre-existing' }).agentId).toBe('pre-existing')
  })

  it('ensureAgent returns pre-existing agentId without API call', async () => {
    const client = new ManagedAgentClient({ agentId: 'pre-existing' })
    expect(await client.ensureAgent()).toBe('pre-existing')
    expect(mocks.betaAgentsCreate).not.toHaveBeenCalled()
  })

  it('ensureAgent creates agent when none exists', async () => {
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    expect(await client.ensureAgent()).toBe('agent-xyz')
    expect(client.agentId).toBe('agent-xyz')
  })

  it('ensureAgent wraps creation errors with MANAGED_AGENT prefix', async () => {
    mocks.betaAgentsCreate.mockRejectedValue(new Error('network fail'))
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    await expect(client.ensureAgent()).rejects.toThrow('[MANAGED_AGENT]')
  })

  it('startSession ensures agent then creates a session', async () => {
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    const session = await client.startSession('Run the tests')
    expect(session.session_id).toBe('sess-abc')
    expect(session.agent_id).toBe('agent-xyz')
    expect(session.status).toBe('created')
  })

  it('getSession returns current session state', async () => {
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    const session = await client.getSession('sess-abc')
    expect(session.session_id).toBe('sess-abc')
    expect(session.status).toBe('running')
  })

  it('sendEvent calls sessions.createEvent with user message', async () => {
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    await client.sendEvent('sess-abc', 'follow-up')
    expect(mocks.sessionsCreateEvent).toHaveBeenCalledWith('sess-abc', { type: 'user', content: 'follow-up' })
  })

  it('interrupt sends interrupt event to the session', async () => {
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    await client.interrupt('sess-abc')
    expect(mocks.sessionsCreateEvent).toHaveBeenCalledWith('sess-abc', { type: 'interrupt' })
  })

  it('streamSession yields events from the session stream', async () => {
    const events = [
      { type: 'assistant', content: 'Working...' },
      { type: 'tool_use', content: 'bash' },
    ]
    async function* gen() { for (const e of events) yield e }
    mocks.sessionsStream.mockReturnValue(gen())

    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    const out: Array<{ type: string; content: string }> = []
    for await (const ev of client.streamSession('sess-abc')) out.push(ev)
    expect(out).toHaveLength(2)
    expect(out[0]!.content).toBe('Working...')
  })

  it('streamSession yields status event when stream is null', async () => {
    mocks.sessionsStream.mockReturnValue(null)
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    const out: Array<{ type: string; content: string }> = []
    for await (const ev of client.streamSession('sess-abc')) out.push(ev)
    expect(out).toHaveLength(1)
    expect(out[0]!.type).toBe('status')
    expect(out[0]!.content).toBe('Stream not available')
  })

  it('streamSession stringifies non-string event content', async () => {
    const events = [{ type: 'tool_result', content: { data: 'raw' } }]
    async function* gen() { for (const e of events) yield e }
    mocks.sessionsStream.mockReturnValue(gen())
    const client = new ManagedAgentClient({ apiKey: 'test-key' })
    const out: Array<{ type: string; content: string }> = []
    for await (const ev of client.streamSession('sess-abc')) out.push(ev)
    expect(out).toHaveLength(1)
    expect(out[0]!.content).toBe(JSON.stringify({ type: 'tool_result', content: { data: 'raw' } }))
  })
})
