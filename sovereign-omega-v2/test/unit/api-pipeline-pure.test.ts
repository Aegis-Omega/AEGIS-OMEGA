// ============================================================
// SOVEREIGN OMEGA — Constitutional Pipeline pure-function tests
// EPISTEMIC TIER: T2
//
// Tests for the pure (non-Claude) functions in:
//   src/api/constitutional-pipeline.ts
//
//   analyzeTajweedStream  — Tajweed DFA over Arabic text
//   computeAbjadRouting   — Abjad numerology routing
//   PIPELINE_SCHEMA_VERSION constant
// ============================================================

import { describe, it, expect, vi } from 'vitest'

// Anthropic SDK is imported transitively via constitutional-pipeline → claude-client.
// Mock it to prevent the browser-environment check from throwing at module load.
vi.mock('@anthropic-ai/sdk', () => ({
  default: class MockAnthropic {
    messages = { create: async () => ({}) }
    constructor(_opts?: unknown) {}
  },
}))

import {
  analyzeTajweedStream,
  computeAbjadRouting,
  PIPELINE_SCHEMA_VERSION,
} from '../../src/api/constitutional-pipeline.js'

// ── PIPELINE_SCHEMA_VERSION ───────────────────────────────

describe('PIPELINE_SCHEMA_VERSION', () => {
  it('is a non-empty string', () => {
    expect(typeof PIPELINE_SCHEMA_VERSION).toBe('string')
    expect(PIPELINE_SCHEMA_VERSION.length).toBeGreaterThan(0)
  })
})

// ── analyzeTajweedStream ──────────────────────────────────

describe('analyzeTajweedStream', () => {
  it('returns hasArabic=false and no active rules for Latin text', () => {
    const result = analyzeTajweedStream('hello world')
    expect(result.hasArabic).toBe(false)
    expect(result.activeRules).toHaveLength(0)
    expect(result.ruleCount.NoRule).toBeGreaterThanOrEqual(0)
  })

  it('returns hasArabic=true for Arabic text', () => {
    // Arabic word: بِسْمِ (contains Arabic codepoints)
    const result = analyzeTajweedStream('بسم')
    expect(result.hasArabic).toBe(true)
  })

  it('detects IdghamWithGhunnah rule (noon + ya)', () => {
    // ن (noon, 0x0646) followed by ي (ya, 0x064A) → IdghamWithGhunnah
    const noon = 'ن'
    const ya   = 'ي'
    const result = analyzeTajweedStream(noon + ya)
    expect(result.activeRules).toContain('IdghamWithGhunnah')
    expect(result.ruleCount['IdghamWithGhunnah']).toBe(1)
  })

  it('detects IdghamWithoutGhunnah rule (noon + lam)', () => {
    // ن (noon) followed by ل (lam, 0x0644) → IdghamWithoutGhunnah
    const noon = 'ن'
    const lam  = 'ل'
    const result = analyzeTajweedStream(noon + lam)
    expect(result.activeRules).toContain('IdghamWithoutGhunnah')
  })

  it('detects Iqlab rule (noon + ba)', () => {
    // ن (noon) followed by ب (ba, 0x0628) → Iqlab
    const noon = 'ن'
    const ba   = 'ب'
    const result = analyzeTajweedStream(noon + ba)
    expect(result.activeRules).toContain('Iqlab')
  })

  it('detects Ikhfa rule (noon + ta)', () => {
    // ن (noon) followed by ت (ta, 0x062A) → Ikhfa
    const noon = 'ن'
    const ta   = 'ت'
    const result = analyzeTajweedStream(noon + ta)
    expect(result.activeRules).toContain('Ikhfa')
  })

  it('detects Idhar rule (noon + ha)', () => {
    // ن (noon) followed by ه (ha, 0x0647) → Idhar
    const noon = 'ن'
    const ha   = 'ه'
    const result = analyzeTajweedStream(noon + ha)
    expect(result.activeRules).toContain('Idhar')
  })

  it('returns NoRule for non-noon followed by any character', () => {
    // ا (alif) followed by ب (ba) — no tajweed rule applies
    const alif = 'ا'
    const ba   = 'ب'
    const result = analyzeTajweedStream(alif + ba)
    expect(result.activeRules).toHaveLength(0)
  })

  it('returns NoRule (default branch) when NoonSakinah is followed by Other class', () => {
    // ن (noon=0x0646 → NoonSakinah) followed by ا (alif=0x0627 → Other)
    // Passes the first if-check but falls through to default: return 'NoRule'
    const noon = 'ن'
    const alif = 'ا'
    const result = analyzeTajweedStream(noon + alif)
    expect(result.activeRules).toHaveLength(0)
    expect(result.hasArabic).toBe(true)
    expect(result.ruleCount['NoRule']).toBeGreaterThan(0)
  })

  it('returns empty activeRules for empty string', () => {
    const result = analyzeTajweedStream('')
    expect(result.activeRules).toHaveLength(0)
    expect(result.hasArabic).toBe(false)
  })

  it('accumulates rule counts correctly across multiple occurrences', () => {
    // Two noon+ya sequences → 2 IdghamWithGhunnah
    const noon = 'ن'
    const ya   = 'ي'
    const result = analyzeTajweedStream(noon + ya + noon + ya)
    expect(result.ruleCount['IdghamWithGhunnah']).toBe(2)
  })
})

// ── computeAbjadRouting ───────────────────────────────────

describe('computeAbjadRouting', () => {
  it('returns zero sum for empty string', () => {
    const result = computeAbjadRouting('')
    expect(result.sum).toBe(0)
    expect(result.node).toBe(0)
  })

  it('returns zero sum for Latin text (no Abjad values)', () => {
    const result = computeAbjadRouting('hello')
    expect(result.sum).toBe(0)
  })

  it('computes correct sum for a single Arabic letter — alif = 1', () => {
    const alif = 'ا'
    const result = computeAbjadRouting(alif)
    expect(result.sum).toBe(1)
    expect(result.node).toBe(1)  // 1 % 12 = 1
  })

  it('computes node as sum % 12', () => {
    // ب (ba=2) + ج (jeem=3) = 5; 5 % 12 = 5
    const ba    = 'ب'
    const jeem  = 'ج'
    const result = computeAbjadRouting(ba + jeem)
    expect(result.sum).toBe(5)
    expect(result.node).toBe(5)
  })

  it('identifies triadic digital root (multiples of 3)', () => {
    // ج (jeem=3) → sum=3, dr=3, isTriadic=true
    const jeem = 'ج'
    const result = computeAbjadRouting(jeem)
    expect(result.isTriadic).toBe(true)
    expect(result.dr).toBe(3)
  })

  it('identifies non-triadic digital root', () => {
    // ا (alif=1) → dr=1, isTriadic=false
    const alif = 'ا'
    const result = computeAbjadRouting(alif)
    expect(result.isTriadic).toBe(false)
  })

  it('digital root of sum=9 is 9 (special case)', () => {
    // ط (tta=9) → sum=9, dr=9 (special: 9%9=0 → return 9), isTriadic=true
    const tta = 'ط'
    const result = computeAbjadRouting(tta)
    expect(result.sum).toBe(9)
    expect(result.dr).toBe(9)
    expect(result.isTriadic).toBe(true)
  })

  it('digital root of multiples of 9 is 9', () => {
    // ط (9) + ط (9) = 18, dr=9
    const tta = 'ط'
    const result = computeAbjadRouting(tta + tta)
    expect(result.sum).toBe(18)
    expect(result.dr).toBe(9)
  })
})
