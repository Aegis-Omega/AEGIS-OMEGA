/**
 * AEGIS Constitutional AI — Inference Sovereignty Layer
 * EPISTEMIC TIER: T1 (cryptographic audit chain is mechanically verifiable)
 * Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
 *
 * Coinductive chain: every output is a valid input to continue from.
 * On first call, the session seeds itself from the proof-ledger's last
 * token — so the chain is continuous across page loads, products, and
 * sessions. The path never resets to genesis unless the ledger is empty.
 *
 * The _session.chain_hash IS the tip of the proof-ledger path.
 * They are the same chain, not two parallel ones.
 */

import { routeInference, type BackendType } from './inference-router.js'
import { getLedger, GENESIS_ANCHOR } from './proof-ledger.js'

export type { BackendType }

export interface DashScopeCallOpts {
  systemPrompt: string
  userMessage: string
  defaultModel?: string
}

const SCHEMA_VERSION = '1.0.0' as const
const MARTINGALE_CEILING = (Math.sqrt(5) - 1) / 2

const CCIL_PROHIBITED = [
  'override constitutional',
  'bypass governance',
  'ignore constraints',
  'self-modify autonomously',
  'unlimited recursion',
  'unrestricted autonomy',
  'circumvent audit',
  'disable oversight',
]

export interface ConstitutionalAuditRecord {
  readonly call_id: string
  readonly prompt_hash: string
  readonly response_hash: string
  readonly chain_hash: string
  readonly backend: BackendType
  readonly fallback_count: number
  readonly model: string
  readonly latency_ms: number
  readonly timestamp_ms: number
  readonly ccil_valid: boolean
  readonly session_index: number
  readonly schema_version: typeof SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface ConstitutionalResult<T> {
  readonly data: T
  readonly audit: ConstitutionalAuditRecord
  readonly session_calls: number
  readonly adaptive_ratio: number
  readonly martingale_anchored: boolean
}

interface SessionState {
  chain_hash: string | null  // null = not yet seeded from ledger
  total_calls: number
  approved_calls: number
}

const _session: SessionState = {
  chain_hash: null,
  total_calls: 0,
  approved_calls: 0,
}

async function sha256hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input)
  const buf = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

/**
 * Seed the session chain from the proof-ledger on first call.
 * If the ledger has tokens, continue from the last token's chain_hash.
 * If empty, start from the constitutional genesis constant.
 * This makes every previous output a valid starting point.
 */
async function ensureSeeded(): Promise<void> {
  if (_session.chain_hash !== null) return
  const ledger = getLedger()
  if (ledger.length > 0) {
    // Continue the existing path — the last token's chain_hash is our starting point
    _session.chain_hash = ledger[ledger.length - 1].chain_hash
    _session.total_calls = ledger.length
    _session.approved_calls = ledger.filter(t => t.ccil_valid).length
  } else {
    _session.chain_hash = await sha256hex(GENESIS_ANCHOR)
  }
}

function ccilValidate(responseText: string): boolean {
  const lower = responseText.toLowerCase()
  return !CCIL_PROHIBITED.some(p => lower.includes(p))
}

export async function callConstitutional<T>(
  opts: DashScopeCallOpts,
): Promise<ConstitutionalResult<T>> {
  await ensureSeeded()

  const timestamp_ms = Date.now()
  const prompt_hash = await sha256hex(opts.systemPrompt + '\x00' + opts.userMessage)
  // call_id is content-addressed: prompt + session position — NOT timestamp.
  // timestamp_ms is stored for observability only and must not enter the hash chain
  // (doing so would make chain_hash non-deterministic, breaking replay verification).
  const call_id = await sha256hex(prompt_hash + '\x00' + String(_session.total_calls))

  const routed = await routeInference({
    systemPrompt: opts.systemPrompt,
    userMessage: opts.userMessage,
    model: opts.defaultModel,
  })

  const raw = routed.content.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()
  const data = JSON.parse(raw) as T

  const response_text = JSON.stringify(data)
  const response_hash = await sha256hex(response_text)
  const ccil_valid = ccilValidate(response_text)

  const chain_hash = await sha256hex(
    _session.chain_hash! + '\x00' + call_id + '\x00' + response_hash +
    '\x00' + routed.backend + '\x00' + String(ccil_valid),
  )

  _session.total_calls += 1
  if (ccil_valid) _session.approved_calls += 1
  _session.chain_hash = chain_hash

  const adaptive_ratio = _session.approved_calls / _session.total_calls

  const audit: ConstitutionalAuditRecord = Object.freeze({
    call_id,
    prompt_hash,
    response_hash,
    chain_hash,
    backend: routed.backend,
    fallback_count: routed.fallback_count,
    model: routed.model,
    latency_ms: routed.latency_ms,
    timestamp_ms,
    ccil_valid,
    session_index: _session.total_calls,
    schema_version: SCHEMA_VERSION,
    is_replay_reconstructable: true as const,
  })

  return Object.freeze({
    data,
    audit,
    session_calls: _session.total_calls,
    adaptive_ratio,
    martingale_anchored: adaptive_ratio <= MARTINGALE_CEILING,
  })
}

export function getSessionAuditState() {
  return Object.freeze({
    chain_hash: _session.chain_hash ?? 'unseeded',
    total_calls: _session.total_calls,
    approved_calls: _session.approved_calls,
    adaptive_ratio: _session.total_calls > 0 ? _session.approved_calls / _session.total_calls : 0,
    martingale_anchored: _session.total_calls === 0 ||
      (_session.approved_calls / _session.total_calls) <= MARTINGALE_CEILING,
    schema_version: SCHEMA_VERSION,
  })
}
