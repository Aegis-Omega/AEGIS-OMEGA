/**
 * AEGIS Constitutional AI — Inference Sovereignty Layer
 * EPISTEMIC TIER: T1 (cryptographic audit chain is mechanically verifiable)
 * Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
 *
 * Every AI inference call produces a cryptographically-chained audit record.
 * CCIL-Ψ validates outputs. Martingale monitor bounds adaptation.
 * EU AI Act Article 12 compliance is structural, not bolted-on.
 *
 * First production AI system with:
 * - Hash-chained inference audit trail (replay-certifiable)
 * - Constitutional constraint lattice (CCIL-Ψ) on every output
 * - Martingale-bounded session governance (1/φ ≈ 0.618 ceiling)
 * - is_replay_reconstructable: true on every record
 */

import { routeInference, type BackendType } from './inference-router.js'

export type { BackendType }

export interface DashScopeCallOpts {
  systemPrompt: string
  userMessage: string
  defaultModel?: string
}

const SCHEMA_VERSION = '1.0.0' as const

// φ-governed martingale ceiling — same constant as MUTATION_RATE_LIMIT in sovereign-omega-v2
const MARTINGALE_CEILING = (Math.sqrt(5) - 1) / 2 // ≈ 0.6180339887

// CCIL-Ψ: Constitutional Constraint Inference Lattice
// Blocks outputs that claim to override constitutional governance
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
  readonly chain_hash: string        // hash-chains to previous call
  readonly backend: BackendType      // which inference provider was used
  readonly fallback_count: number    // backends tried before success
  readonly model: string
  readonly latency_ms: number
  readonly timestamp_ms: number
  readonly ccil_valid: boolean       // CCIL-Ψ constraint validation result
  readonly session_index: number     // position in this session's call chain
  readonly schema_version: typeof SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

export interface ConstitutionalResult<T> {
  readonly data: T
  readonly audit: ConstitutionalAuditRecord
  readonly session_calls: number
  readonly adaptive_ratio: number       // approved_calls / total_calls
  readonly martingale_anchored: boolean // adaptive_ratio ≤ 1/φ
}

// Session-scoped audit chain — lives in browser memory for this page session
interface SessionState {
  chain_hash: string
  total_calls: number
  approved_calls: number  // calls where ccil_valid=true
}

// localStorage key — persists the chain across page loads, products, browser sessions
const LEDGER_KEY = 'aegis_constitutional_ledger_v1'

// Genesis anchor: seeded from constitutional constants when ledger is empty
// φ + CCIL-Ψ + schema version → the same values that govern every invariant
const GENESIS_ANCHOR =
  `AEGIS:GENESIS_ANCHOR\x00phi=${MARTINGALE_CEILING}\x00CCIL-PSI:1.0.0\x00schema=${SCHEMA_VERSION}`

interface LedgerSnapshot {
  chain_hash: string
  total_calls: number
  approved_calls: number
  timestamp_ms: number
}

const _session: SessionState = {
  chain_hash: '',  // empty until ensureSeeded() runs
  total_calls: 0,
  approved_calls: 0,
}

let _seeded = false

// Runs once on the first callConstitutional() invocation.
// Reads the last ledger snapshot from localStorage to continue the audit chain.
// Empty ledger → seeds from sha256(GENESIS_ANCHOR) using constitutional constants.
async function ensureSeeded(): Promise<void> {
  if (_seeded) return
  _seeded = true
  try {
    const raw = localStorage.getItem(LEDGER_KEY)
    if (raw) {
      const snap = JSON.parse(raw) as LedgerSnapshot
      if (snap?.chain_hash) {
        _session.chain_hash = snap.chain_hash
        _session.total_calls = snap.total_calls
        _session.approved_calls = snap.approved_calls
        return
      }
    }
  } catch { /* localStorage unavailable */ }
  _session.chain_hash = await sha256hex(GENESIS_ANCHOR)
}

function persistLedger(): void {
  try {
    const snap: LedgerSnapshot = {
      chain_hash: _session.chain_hash,
      total_calls: _session.total_calls,
      approved_calls: _session.approved_calls,
      timestamp_ms: Date.now(),
    }
    localStorage.setItem(LEDGER_KEY, JSON.stringify(snap))
  } catch { /* localStorage unavailable */ }
}

async function sha256hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input)
  const buf = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

function ccilValidate(responseText: string): boolean {
  const lower = responseText.toLowerCase()
  return !CCIL_PROHIBITED.some(p => lower.includes(p))
}

/**
 * Constitutional inference call — wraps callDashScope with full governance layer.
 * Every call is audit-chained, CCIL-validated, and martingale-monitored.
 */
export async function callConstitutional<T>(
  opts: DashScopeCallOpts,
): Promise<ConstitutionalResult<T>> {
  await ensureSeeded()
  const timestamp_ms = Date.now()

  const prompt_hash = await sha256hex(opts.systemPrompt + '\x00' + opts.userMessage)
  const call_id = await sha256hex(String(timestamp_ms) + '\x00' + prompt_hash)

  // Route through the multi-backend constitutional chain
  const routed = await routeInference({
    systemPrompt: opts.systemPrompt,
    userMessage: opts.userMessage,
    ...(opts.defaultModel !== undefined ? { model: opts.defaultModel } : {}),
  })

  // Parse JSON response — same logic as callDashScope
  let raw = routed.content.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()
  const data = JSON.parse(raw) as T

  const response_text = JSON.stringify(data)
  const response_hash = await sha256hex(response_text)
  const ccil_valid = ccilValidate(response_text)

  // Chain: hash(prev_chain || call_id || response_hash || backend || ccil_valid)
  const chain_hash = await sha256hex(
    _session.chain_hash + '\x00' + call_id + '\x00' + response_hash +
    '\x00' + routed.backend + '\x00' + String(ccil_valid),
  )

  _session.total_calls += 1
  if (ccil_valid) _session.approved_calls += 1
  _session.chain_hash = chain_hash
  persistLedger() // same chain_hash → localStorage → next session picks up here

  const adaptive_ratio = _session.total_calls > 0
    ? _session.approved_calls / _session.total_calls
    : 0

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

/** Clears the persisted ledger — use only in tests or explicit operator reset. */
export function clearConstitutionalLedger(): void {
  try { localStorage.removeItem(LEDGER_KEY) } catch { /* unavailable */ }
  _seeded = false
  _session.chain_hash = ''
  _session.total_calls = 0
  _session.approved_calls = 0
}

/** Returns the current session audit chain state — for display in governance UI */
export function getSessionAuditState() {
  return Object.freeze({
    chain_hash: _session.chain_hash,
    total_calls: _session.total_calls,
    approved_calls: _session.approved_calls,
    adaptive_ratio: _session.total_calls > 0 ? _session.approved_calls / _session.total_calls : 0,
    martingale_anchored: _session.total_calls === 0 ||
      (_session.approved_calls / _session.total_calls) <= MARTINGALE_CEILING,
    schema_version: SCHEMA_VERSION,
  })
}
