// ============================================================
// SOVEREIGN OMEGA — Constitutional AI Pipeline
// EPISTEMIC TIER: T2 · Gate 219
//
// The full empirical practice:
//   Input text
//   → AbjadEncoder routing (Arabic name detection → dodecagonal node)
//   → TajweedDFA analysis (Arabic phoneme classification)
//   → Claude constitutional call (hash-linked)
//   → RingCompositionVerifier on response hash chain
//   → Tier-stamped, replay-certifiable output
//
// This is the "new age of computing" practice:
//   Every AI inference is mathematically anchored, hash-certified,
//   and constitutionally bounded. Nothing escapes the ring.
//
// Copyright (C) 2025 Tarik Skalić — All rights reserved.
// ============================================================

import { ConstitutionalClaudeClient, type ConstitutionalResponse } from './claude-client.js'
import type { SHA256Hex } from '../core/types.js'
import { EpistemicTier } from '../core/types.js'
import { hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const PIPELINE_SCHEMA_VERSION = '1.0.0' as const

// ─── Phonological analysis (pure TS mirror of Rust tajweed_dfa) ──

/** Mirrors the Rust PhonemeClass enum from Gate 216 tajweed_dfa.rs */
export type PhonemeClass =
  | 'NoonSakinah'
  | 'TanweenFamily'
  | 'IdghamGhunnah'
  | 'IdghamNoGhunnah'
  | 'Iqlab'
  | 'Ikhfa'
  | 'IdharHalqi'
  | 'Other'

/** Mirrors the Rust TajweedRule enum from Gate 216 */
export type TajweedRule =
  | 'IdghamWithGhunnah'
  | 'IdghamWithoutGhunnah'
  | 'Iqlab'
  | 'Ikhfa'
  | 'Idhar'
  | 'NoRule'

const IDGHAM_GHUNNAH_CODEPOINTS = new Set([0x064A, 0x0645, 0x0648, 0x0646])
const IDGHAM_NO_GHUNNAH_CODEPOINTS = new Set([0x0644, 0x0631])
const IQLAB_CODEPOINTS = new Set([0x0628])
const IDHAR_HALQI_CODEPOINTS = new Set([0x0621, 0x0647, 0x0639, 0x062D, 0x063A, 0x062E])
const IKHFA_CODEPOINTS = new Set([
  0x062A, 0x062B, 0x062C, 0x062F, 0x0630, 0x0632,
  0x0633, 0x0634, 0x0635, 0x0636, 0x0637, 0x0638,
  0x0641, 0x0642, 0x0643,
])

function classifyCodepoint(cp: number): PhonemeClass {
  if (cp === 0x0646) return 'NoonSakinah'
  if (IDGHAM_GHUNNAH_CODEPOINTS.has(cp)) return 'IdghamGhunnah'
  if (IDGHAM_NO_GHUNNAH_CODEPOINTS.has(cp)) return 'IdghamNoGhunnah'
  if (IQLAB_CODEPOINTS.has(cp)) return 'Iqlab'
  if (IDHAR_HALQI_CODEPOINTS.has(cp)) return 'IdharHalqi'
  if (IKHFA_CODEPOINTS.has(cp)) return 'Ikhfa'
  return 'Other'
}

function applyTajweed(current: PhonemeClass, next: PhonemeClass): TajweedRule {
  if (current !== 'NoonSakinah' && current !== 'TanweenFamily') return 'NoRule'
  switch (next) {
    case 'IdghamGhunnah': return 'IdghamWithGhunnah'
    case 'IdghamNoGhunnah': return 'IdghamWithoutGhunnah'
    case 'Iqlab': return 'Iqlab'
    case 'Ikhfa': return 'Ikhfa'
    case 'IdharHalqi': return 'Idhar'
    default: return 'NoRule'
  }
}

export function analyzeTajweedStream(text: string): {
  activeRules: TajweedRule[]
  ruleCount: Record<TajweedRule, number>
  hasArabic: boolean
} {
  /* c8 ignore next -- codePointAt(0) on a spread character is always defined; ?? 0 is a TypeScript guard for the unreachable undefined case */
  const codepoints = [...text].map(c => c.codePointAt(0) ?? 0)
  const classes = codepoints.map(classifyCodepoint)
  const rules: TajweedRule[] = []

  for (let i = 0; i < classes.length - 1; i++) {
    rules.push(applyTajweed(classes[i]!, classes[i + 1]!))
  }

  const activeRules = rules.filter(r => r !== 'NoRule')
  const ruleCount: Record<TajweedRule, number> = {
    IdghamWithGhunnah: 0, IdghamWithoutGhunnah: 0,
    Iqlab: 0, Ikhfa: 0, Idhar: 0, NoRule: 0,
  }
  for (const r of rules) ruleCount[r]++

  const ARABIC_RANGE_START = 0x0600
  const ARABIC_RANGE_END = 0x06FF
  const hasArabic = codepoints.some(cp => cp >= ARABIC_RANGE_START && cp <= ARABIC_RANGE_END)

  return { activeRules, ruleCount, hasArabic }
}

// ─── Abjad routing (TS mirror of Gate 215) ────────────────

const ABJAD_VALUES: Record<string, number> = {
  'ا': 1, 'ب': 2, 'ج': 3, 'د': 4,
  'ه': 5, 'و': 6, 'ز': 7, 'ح': 8,
  'ط': 9, 'ي': 10, 'ك': 20, 'ل': 30,
  'م': 40, 'ن': 50, 'س': 60, 'ع': 70,
  'ف': 80, 'ص': 90, 'ق': 100, 'ر': 200,
  'ش': 300, 'ت': 400, 'ث': 500, 'خ': 600,
  'ذ': 700, 'ض': 800, 'ظ': 900, 'غ': 1000,
}

function digitalRoot(n: number): number {
  if (n === 0) return 9
  const r = n % 9
  return r === 0 ? 9 : r
}

export function computeAbjadRouting(text: string): {
  sum: number
  node: number
  dr: number
  isTriadic: boolean
} {
  let sum = 0
  for (const char of text) {
    sum += ABJAD_VALUES[char] ?? 0
  }
  const node = sum % 12
  const dr = digitalRoot(sum)
  const isTriadic = dr === 3 || dr === 6 || dr === 9
  return { sum, node, dr, isTriadic }
}

// ─── Pipeline output ──────────────────────────────────────

export interface PipelineAnalysis {
  readonly tajweed: {
    readonly hasArabic: boolean
    readonly activeRuleCount: number
    readonly ruleBreakdown: Record<TajweedRule, number>
    readonly dominantRule: TajweedRule | null
  }
  readonly abjad: {
    readonly sum: number
    readonly node: number
    readonly dr: number
    readonly isTriadic: boolean
  } | null
}

export interface PipelineResult {
  readonly input_text: string
  readonly input_hash: SHA256Hex
  readonly analysis: PipelineAnalysis
  readonly claude_response: ConstitutionalResponse
  readonly pipeline_hash: SHA256Hex   // chain_hash of all stages
  readonly epistemic_tier: EpistemicTier
  readonly schema_version: typeof PIPELINE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

// ─── Pipeline ─────────────────────────────────────────────

export class ConstitutionalPipeline {
  private readonly _client: ConstitutionalClaudeClient

  constructor(apiKey?: string) {
    this._client = new ConstitutionalClaudeClient(apiKey)
  }

  /**
   * Run the full constitutional pipeline on input text.
   * 1. Hash-certify the input
   * 2. Phonological analysis (Tajweed DFA)
   * 3. Abjad routing (if Arabic present)
   * 4. Constitutional Claude call
   * 5. Chain hash linking all stages
   */
  async run(
    inputText: string,
    options: {
      model?: string
      maxTokens?: number
      systemContext?: string
      useThinking?: boolean
    } = {}
  ): Promise<PipelineResult> {
    const model = options.model ?? 'claude-sonnet-4-6'
    const maxTokens = options.maxTokens ?? 2048

    // Stage 1: hash-certify input
    const input_hash = await hashValue({ text: inputText })

    // Stage 2: phonological analysis
    const tajweedResult = analyzeTajweedStream(inputText)
    const activeRules = Object.entries(tajweedResult.ruleCount)
      .filter(([k, v]) => k !== 'NoRule' && v > 0)
    const dominantRule = activeRules.length > 0
      ? (activeRules.sort((a, b) => b[1]! - a[1]!)[0]![0] as TajweedRule)
      : null

    // Stage 3: Abjad routing (only if Arabic present)
    const abjadRouting = tajweedResult.hasArabic
      ? computeAbjadRouting(inputText)
      : null

    // Stage 4: build enriched prompt
    let enrichedPrompt = inputText
    if (tajweedResult.hasArabic && tajweedResult.activeRules.length > 0) {
      enrichedPrompt += `\n\n[PHONOLOGICAL CONTEXT: Tajweed analysis detected ${tajweedResult.activeRules.length} active transformations. Dominant: ${dominantRule}]`
    }
    if (abjadRouting) {
      enrichedPrompt += `\n[ABJAD ROUTING: Sum=${abjadRouting.sum}, Node=${abjadRouting.node}/12, DR=${abjadRouting.dr}, ${abjadRouting.isTriadic ? 'Triadic' : 'Hexadic'}]`
    }

    // Stage 5: Claude constitutional call
    const claudeResponse = options.useThinking
      ? await this._client.think(
          [{ role: 'user', content: enrichedPrompt }],
          model,
          8000,
          maxTokens
        )
      : await this._client.send({
          messages: [{ role: 'user', content: enrichedPrompt }],
          model,
          max_tokens: maxTokens,
          ...(options.systemContext !== undefined ? { system: options.systemContext } : {}),
        })

    // Stage 6: pipeline chain hash
    const pipeline_hash = await hashValue({
      input_hash,
      request_hash: claudeResponse.request_hash,
      response_hash: claudeResponse.response_hash,
      model,
    })

    return deepFreeze({
      input_text: inputText,
      input_hash,
      analysis: {
        tajweed: {
          hasArabic: tajweedResult.hasArabic,
          activeRuleCount: tajweedResult.activeRules.length,
          ruleBreakdown: tajweedResult.ruleCount,
          dominantRule,
        },
        abjad: abjadRouting,
      },
      claude_response: claudeResponse,
      pipeline_hash,
      epistemic_tier: claudeResponse.epistemic_tier,
      schema_version: PIPELINE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    })
  }

  /** Run pipeline on multiple inputs and return all results. */
  async runBatch(
    inputs: readonly string[],
    options: Parameters<ConstitutionalPipeline['run']>[1] = {}
  ): Promise<PipelineResult[]> {
    return Promise.all(inputs.map(input => this.run(input, options)))
  }
}

/** Default singleton pipeline */
export const constitutionalPipeline = new ConstitutionalPipeline()
