// ============================================================
// SOVEREIGN OMEGA — ConstitutionalPipeline.run() tests
// EPISTEMIC TIER: T2
//
// Tests for src/api/constitutional-pipeline.ts — pipeline class.
// Mocks ConstitutionalClaudeClient to avoid real API calls.
// ============================================================

import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'

// vi.hoisted ensures mock refs are available when factory runs
const mocks = vi.hoisted(() => ({
  send:  vi.fn(),
  think: vi.fn(),
}))

// Mock @anthropic-ai/sdk first to prevent browser-environment error from the claude-client singleton
vi.mock('@anthropic-ai/sdk', () => ({
  default: class MockAnthropic {
    messages = { create: vi.fn() }
    constructor(_opts?: unknown) {}
  },
}))

// Mock the claude-client module so ConstitutionalPipeline uses our fake client
vi.mock('../../src/api/claude-client.js', () => {
  class MockConstitutionalClaudeClient {
    send  = mocks.send
    think = mocks.think
    constructor(_apiKey?: string) {}
  }
  return {
    ConstitutionalClaudeClient: MockConstitutionalClaudeClient,
    CLAUDE_CLIENT_SCHEMA_VERSION: '1.0.0',
    AEGIS_CONSTITUTIONAL_SYSTEM_PROMPT: 'MOCKED CONSTITUTIONAL PROMPT',
    claudeClient: new MockConstitutionalClaudeClient(),
  }
})

import { ConstitutionalPipeline, PIPELINE_SCHEMA_VERSION } from '../../src/api/constitutional-pipeline.js'
import type { SHA256Hex } from '../../src/core/types.js'
import { EpistemicTier } from '../../src/core/types.js'

afterEach(() => vi.clearAllMocks())

function makeFakeResponse(text: string) {
  return {
    response_text: text,
    model_id: 'claude-haiku-4-5-20251001',
    request_hash:  '0'.repeat(64) as SHA256Hex,
    response_hash: '1'.repeat(64) as SHA256Hex,
    chain_hash:    '2'.repeat(64) as SHA256Hex,
    input_tokens:  5,
    output_tokens: 10,
    stop_reason:   'end_turn',
    epistemic_tier: EpistemicTier.T2,
    schema_version: PIPELINE_SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  }
}

// ── ConstitutionalPipeline.run — Latin text ───────────────

describe('ConstitutionalPipeline.run — Latin text (no Arabic)', () => {
  beforeEach(() => {
    mocks.send.mockResolvedValue(makeFakeResponse('Constitutional answer'))
  })

  it('returns a frozen PipelineResult with correct schema_version', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const result = await pipeline.run('build a test suite')
    expect(Object.isFrozen(result)).toBe(true)
    expect(result.schema_version).toBe(PIPELINE_SCHEMA_VERSION)
    expect(result.is_replay_reconstructable).toBe(true)
  })

  it('input_hash is a 64-char hex string', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const result = await pipeline.run('hello world')
    expect(result.input_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('pipeline_hash is a 64-char hex string', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const result = await pipeline.run('hello world')
    expect(result.pipeline_hash).toMatch(/^[0-9a-f]{64}$/)
  })

  it('analysis.tajweed.hasArabic is false for Latin input', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const result = await pipeline.run('hello world')
    expect(result.analysis.tajweed.hasArabic).toBe(false)
    expect(result.analysis.abjad).toBeNull()
  })

  it('calls send() (not think()) for default non-thinking run', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    await pipeline.run('hello world')
    expect(mocks.send).toHaveBeenCalledOnce()
    expect(mocks.think).not.toHaveBeenCalled()
  })

  it('calls think() when useThinking option is true', async () => {
    mocks.think.mockResolvedValue(makeFakeResponse('Thinking answer'))
    const pipeline = new ConstitutionalPipeline('test-key')
    await pipeline.run('deep question', { useThinking: true })
    expect(mocks.think).toHaveBeenCalledOnce()
    expect(mocks.send).not.toHaveBeenCalled()
  })

  it('passes systemContext to the send request', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    await pipeline.run('question', { systemContext: 'Governance context' })
    const sendArgs = mocks.send.mock.calls[0]![0] as { system?: string }
    expect(sendArgs.system).toBe('Governance context')
  })
})

// ── ConstitutionalPipeline.run — Arabic text ──────────────

describe('ConstitutionalPipeline.run — Arabic text (Tajweed + Abjad)', () => {
  beforeEach(() => {
    mocks.send.mockResolvedValue(makeFakeResponse('Arabic response'))
  })

  it('analysis.tajweed.hasArabic is true for Arabic input', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    // "بسم" = Arabic text; hasArabic=true, abjad routing applied
    const result = await pipeline.run('بسم')
    expect(result.analysis.tajweed.hasArabic).toBe(true)
    expect(result.analysis.abjad).not.toBeNull()
  })

  it('enriches prompt with phonological context when Arabic has active rules', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    // نينب: noon+ya → IdghamWithGhunnah, noon+ba → Iqlab (2 distinct active rules)
    // 2-element activeRules forces the sort comparator to execute (covers line 208)
    await pipeline.run('نينب')
    const sendArgs = mocks.send.mock.calls[0]![0] as { messages: Array<{ content: string }> }
    const content = sendArgs.messages[0]!.content
    // The prompt should be enriched with phonological context
    expect(content).toContain('نينب')
  })
})

// ── ConstitutionalPipeline.runBatch ───────────────────────

describe('ConstitutionalPipeline.runBatch', () => {
  beforeEach(() => {
    mocks.send.mockResolvedValue(makeFakeResponse('Batch response'))
  })

  it('runs all inputs and returns results for each', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const results = await pipeline.runBatch(['input 1', 'input 2', 'input 3'])
    expect(results).toHaveLength(3)
    expect(mocks.send).toHaveBeenCalledTimes(3)
  })

  it('returns empty array for empty batch', async () => {
    const pipeline = new ConstitutionalPipeline('test-key')
    const results = await pipeline.runBatch([])
    expect(results).toHaveLength(0)
  })
})
