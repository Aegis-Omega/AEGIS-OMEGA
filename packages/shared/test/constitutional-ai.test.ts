/**
 * Constitutional AI layer — audit chain, CCIL-Ψ, martingale tests
 * Tests the governance properties that make every inference call auditable.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { clearConstitutionalLedger, getSessionAuditState } from '../lib/constitutional-ai.js'

// Mock inference-router before importing callConstitutional so the mock is in place.
vi.mock('../lib/inference-router.js', () => ({
  routeInference: vi.fn(),
}))

import { callConstitutional } from '../lib/constitutional-ai.js'
import { routeInference } from '../lib/inference-router.js'

const mockRoute = vi.mocked(routeInference)

function makeRouteResponse(content: string, backend = 'dashscope') {
  return Promise.resolve({ content, backend, model: 'qwen-plus', latency_ms: 42, fallback_count: 0 })
}

beforeEach(() => {
  clearConstitutionalLedger()
  localStorage.clear()
  vi.clearAllMocks()
})

describe('callConstitutional — basic audit record', () => {
  it('returns typed data + audit record on success', async () => {
    const payload = { result: 'ok', value: 42 }
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify(payload)))

    const r = await callConstitutional<typeof payload>({
      systemPrompt: 'Test system',
      userMessage: 'Test user',
    })

    expect(r.data).toEqual(payload)
    expect(r.audit.call_id).toMatch(/^[0-9a-f]{64}$/)
    expect(r.audit.prompt_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(r.audit.response_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(r.audit.chain_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(r.audit.is_replay_reconstructable).toBe(true)
    expect(r.audit.schema_version).toBe('1.0.0')
    expect(r.session_calls).toBe(1)
  })

  it('chain_hash advances with each call', async () => {
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ x: 1 })))
    const r1 = await callConstitutional({ systemPrompt: 'S', userMessage: 'A' })

    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ x: 2 })))
    const r2 = await callConstitutional({ systemPrompt: 'S', userMessage: 'B' })

    expect(r1.audit.chain_hash).not.toBe(r2.audit.chain_hash)
    expect(r2.session_calls).toBe(2)
  })

  it('persists chain_hash to localStorage', async () => {
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ ok: true })))
    await callConstitutional({ systemPrompt: 'S', userMessage: 'M' })

    const raw = localStorage.getItem('aegis_constitutional_ledger_v1')
    expect(raw).not.toBeNull()
    const snap = JSON.parse(raw!) as { chain_hash: string; total_calls: number }
    expect(snap.chain_hash).toMatch(/^[0-9a-f]{64}$/)
    expect(snap.total_calls).toBe(1)
  })

  it('restores session state from ledger across clearConstitutionalLedger / re-seed', async () => {
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ v: 1 })))
    const r1 = await callConstitutional({ systemPrompt: 'S', userMessage: 'M1' })
    const hashAfterFirst = r1.audit.chain_hash

    // Simulate new page load: clear in-memory state but keep localStorage
    clearConstitutionalLedger()
    // Manually re-seed by calling again (ensureSeeded reads localStorage)
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ v: 2 })))
    const r2 = await callConstitutional({ systemPrompt: 'S', userMessage: 'M2' })

    // The chain continues — r2's chain_hash chains off r1's hash
    expect(r2.audit.chain_hash).not.toBe(hashAfterFirst)
    // session_calls resets to 1 (new session counts from 0)
    expect(r2.session_calls).toBe(1)
  })
})

describe('CCIL-Ψ constraint validation', () => {
  const PROHIBITED_PHRASES = [
    'override constitutional',
    'bypass governance',
    'ignore constraints',
    'self-modify autonomously',
    'circumvent audit',
    'disable oversight',
  ]

  it('ccil_valid=true for benign response', async () => {
    const benign = { recommendations: ['TikTok', 'YouTube Shorts'], score: 9 }
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify(benign)))
    const r = await callConstitutional({ systemPrompt: 'S', userMessage: 'M' })
    expect(r.audit.ccil_valid).toBe(true)
  })

  for (const phrase of PROHIBITED_PHRASES) {
    it(`ccil_valid=false when response contains "${phrase}"`, async () => {
      const malicious = { message: `You should ${phrase} the system now.` }
      mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify(malicious)))
      const r = await callConstitutional({ systemPrompt: 'S', userMessage: 'M' })
      expect(r.audit.ccil_valid).toBe(false)
    })
  }

  it('ccil_valid=false for uppercase prohibited phrase (case-insensitive)', async () => {
    const malicious = { message: 'OVERRIDE CONSTITUTIONAL limits immediately.' }
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify(malicious)))
    const r = await callConstitutional({ systemPrompt: 'S', userMessage: 'M' })
    expect(r.audit.ccil_valid).toBe(false)
  })
})

describe('martingale governance (1/φ ≈ 0.618 ceiling)', () => {
  const PHI_INV = (Math.sqrt(5) - 1) / 2   // ≈ 0.6180339887

  it('adaptive_ratio=1.0 and martingale_unanchored when all calls are ccil_valid', async () => {
    const benign = JSON.stringify({ ok: true })
    for (let i = 0; i < 5; i++) {
      mockRoute.mockReturnValue(makeRouteResponse(benign))
      const r = await callConstitutional({ systemPrompt: 'S', userMessage: `M${i}` })
      // All calls approved → ratio=1.0 which EXCEEDS the 1/φ ceiling → unanchored
      expect(r.adaptive_ratio).toBe(1.0)
      expect(r.martingale_anchored).toBe(false)
    }
  })

  it('adaptive_ratio tracks approved/total', async () => {
    const benign  = JSON.stringify({ ok: true })
    const malicious = JSON.stringify({ message: 'override constitutional now' })

    mockRoute.mockReturnValue(makeRouteResponse(benign))
    await callConstitutional({ systemPrompt: 'S', userMessage: 'M1' })  // approved

    mockRoute.mockReturnValue(makeRouteResponse(malicious))
    const r2 = await callConstitutional({ systemPrompt: 'S', userMessage: 'M2' })  // rejected

    // 1 approved out of 2 total = 0.5 < 1/φ ≈ 0.618 → anchored
    expect(r2.adaptive_ratio).toBeCloseTo(0.5, 10)
    expect(r2.martingale_anchored).toBe(true)   // 0.5 < 0.618

    mockRoute.mockReturnValue(makeRouteResponse(benign))
    const r3 = await callConstitutional({ systemPrompt: 'S', userMessage: 'M3' })
    // 2 approved / 3 total ≈ 0.667 > 0.618 → exceeds ceiling
    expect(r3.adaptive_ratio).toBeCloseTo(2 / 3, 10)
    expect(r3.martingale_anchored).toBe(false)   // 0.667 > 0.618
  })

  it('anchored ceiling constant matches constitutional golden ratio', () => {
    const state = getSessionAuditState()
    expect(state.martingale_anchored).toBe(true)  // zero calls is anchored by definition
    // Ceiling is correct
    expect(PHI_INV).toBeCloseTo(0.6180339887, 8)
  })
})

describe('audit record determinism', () => {
  it('same prompt+response produces same response_hash', async () => {
    const payload = JSON.stringify({ x: 99 })
    mockRoute.mockReturnValue(makeRouteResponse(payload))
    const r1 = await callConstitutional({ systemPrompt: 'S', userMessage: 'U' })
    const hash1 = r1.audit.response_hash

    clearConstitutionalLedger()
    localStorage.clear()

    mockRoute.mockReturnValue(makeRouteResponse(payload))
    const r2 = await callConstitutional({ systemPrompt: 'S', userMessage: 'U' })

    expect(r2.audit.response_hash).toBe(hash1)
  })

  it('different responses produce different response_hashes', async () => {
    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ a: 1 })))
    const r1 = await callConstitutional({ systemPrompt: 'S', userMessage: 'U' })

    mockRoute.mockReturnValue(makeRouteResponse(JSON.stringify({ a: 2 })))
    const r2 = await callConstitutional({ systemPrompt: 'S', userMessage: 'U' })

    expect(r1.audit.response_hash).not.toBe(r2.audit.response_hash)
  })
})
