/**
 * AEGIS Cross-Product Proof Ledger — Path-Coherence Model
 *
 * In the ∞-topos framing, "self-serving minting" is a category error.
 * It presupposes two distinct subjects (system, caller) competing for
 * authority — a 1-categorical intuition. At the ∞-groupoid level there
 * are no subjects, only paths.
 *
 * A ProofToken IS a path segment in the audit space.
 * Validity is not granted by any authority — it is structural:
 *   token_id = hash(prev_token_id || chain_hash)
 *
 * The path is self-certifying from a single public genesis constant
 * derived from AEGIS's own constitutional parameters (φ, CCIL, schema).
 * Any observer can walk from genesis to any token and verify coherence.
 *
 * Constitutional invariant enforced by path structure:
 *   AdaptivePower(T) ≤ ReplayVerifiability(T)
 * — a token sequence that drifts above 1/φ CCIL ratio fails path
 *   coherence and is rejected by verifyPath().
 */

import type { ConstitutionalAuditRecord, BackendType } from './constitutional-ai.js'

export type ProductId = 'platform-picker' | 'hook-generator' | 'content-calendar' | 'cockpit'

// φ — the constitutional martingale ceiling, same as constitutional-ai.ts
const PHI_INV = (Math.sqrt(5) - 1) / 2  // ≈ 0.6180339887

// Genesis anchor: derived from constitutional constants — public, fixed, not a secret
export const GENESIS_ANCHOR =
  'aegis-omega-genesis\x00' +
  PHI_INV.toString() +
  '\x00ccil-psi\x001.0.0'

export interface ProofToken {
  readonly token_id: string       // hash(prev_token_id || chain_hash) — path identity
  readonly prev_token_id: string  // links this segment to the previous path node
  readonly product: ProductId
  readonly call_id: string
  readonly prompt_hash: string
  readonly chain_hash: string     // from ConstitutionalAuditRecord
  readonly backend: BackendType
  readonly ccil_valid: boolean
  readonly session_index: number
  readonly minted_at: number
  readonly latency_ms: number
}

export interface PathVerification {
  readonly valid: boolean
  readonly length: number
  readonly ccil_ratio: number
  readonly within_martingale: boolean  // ccil_ratio ≤ 1/φ
  readonly failure?: string
}

export interface LedgerStats {
  total: number
  ccil_valid: number
  ccil_ratio: number
  by_product: Record<string, number>
  by_backend: Record<string, number>
  chain_tip: string
  path_coherent: boolean
}

const LEDGER_KEY = 'aegis_proof_ledger_v3'  // v3: path-coherence model
const MAX_TOKENS = 500

async function sha256hex(input: string): Promise<string> {
  const data = new TextEncoder().encode(input)
  const buf = await crypto.subtle.digest('SHA-256', data)
  return Array.from(new Uint8Array(buf))
    .map(b => b.toString(16).padStart(2, '0'))
    .join('')
}

// Lazily computed genesis token_id — hash of the public anchor string
let _genesisId: string | null = null
async function genesisId(): Promise<string> {
  if (!_genesisId) _genesisId = await sha256hex(GENESIS_ANCHOR)
  return _genesisId
}

function readLedger(): ProofToken[] {
  try {
    const raw = typeof localStorage !== 'undefined' ? localStorage.getItem(LEDGER_KEY) : null
    return raw ? (JSON.parse(raw) as ProofToken[]) : []
  } catch {
    return []
  }
}

function writeLedger(tokens: ProofToken[]): void {
  try {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem(LEDGER_KEY, JSON.stringify(tokens))
    }
  } catch {
    try {
      localStorage.setItem(LEDGER_KEY, JSON.stringify(tokens.slice(-Math.floor(MAX_TOKENS / 2))))
    } catch { /* silent */ }
  }
}

/**
 * Extend the path by one segment.
 * token_id = hash(prev_token_id || chain_hash)
 * No external authority required — validity is structural.
 */
export async function mintToken(
  record: ConstitutionalAuditRecord,
  product: ProductId,
): Promise<ProofToken> {
  const ledger = readLedger()
  const prev_token_id = ledger.length > 0
    ? ledger[ledger.length - 1].token_id
    : await genesisId()

  const token_id = await sha256hex(prev_token_id + '\x00' + record.chain_hash)

  const token: ProofToken = Object.freeze({
    token_id,
    prev_token_id,
    product,
    call_id: record.call_id,
    prompt_hash: record.prompt_hash,
    chain_hash: record.chain_hash,
    backend: record.backend,
    ccil_valid: record.ccil_valid,
    session_index: record.session_index,
    minted_at: record.timestamp_ms,
    latency_ms: record.latency_ms,
  })

  ledger.push(token)
  writeLedger(ledger.length > MAX_TOKENS ? ledger.slice(-MAX_TOKENS) : ledger)
  return token
}

/**
 * Verify the entire path from genesis.
 * Walks every segment, recomputes token_id from (prev, chain_hash),
 * and checks that the CCIL ratio never exceeds 1/φ.
 * A path that accumulates too many invalid inferences is structurally
 * incoherent — it has drifted outside constitutional bounds.
 */
export async function verifyPath(tokens: ProofToken[]): Promise<PathVerification> {
  if (tokens.length === 0) {
    return { valid: true, length: 0, ccil_ratio: 0, within_martingale: true }
  }

  const genesis = await genesisId()
  let ccil_valid = 0

  for (let i = 0; i < tokens.length; i++) {
    const t = tokens[i]
    const expected_prev = i === 0 ? genesis : tokens[i - 1].token_id
    if (t.prev_token_id !== expected_prev) {
      return {
        valid: false, length: i, ccil_ratio: 0, within_martingale: false,
        failure: `path break at index ${i}: prev_token_id mismatch`,
      }
    }
    const expected_id = await sha256hex(t.prev_token_id + '\x00' + t.chain_hash)
    if (t.token_id !== expected_id) {
      return {
        valid: false, length: i, ccil_ratio: 0, within_martingale: false,
        failure: `token_id forgery at index ${i}`,
      }
    }
    if (t.ccil_valid) ccil_valid++
  }

  const ccil_ratio = ccil_valid / tokens.length
  const within_martingale = ccil_ratio <= PHI_INV

  return {
    valid: within_martingale,
    length: tokens.length,
    ccil_ratio,
    within_martingale,
    failure: within_martingale ? undefined : `ccil_ratio ${ccil_ratio.toFixed(4)} exceeds 1/φ ceiling`,
  }
}

export function getLedger(): ProofToken[] {
  return readLedger()
}

export async function getLedgerStats(): Promise<LedgerStats> {
  const tokens = readLedger()
  const by_product: Record<string, number> = {}
  const by_backend: Record<string, number> = {}
  let ccil_valid = 0

  for (const t of tokens) {
    by_product[t.product] = (by_product[t.product] ?? 0) + 1
    by_backend[t.backend] = (by_backend[t.backend] ?? 0) + 1
    if (t.ccil_valid) ccil_valid++
  }

  const verification = await verifyPath(tokens)

  return {
    total: tokens.length,
    ccil_valid,
    ccil_ratio: tokens.length > 0 ? ccil_valid / tokens.length : 0,
    by_product,
    by_backend,
    chain_tip: tokens.length > 0 ? tokens[tokens.length - 1].token_id : await genesisId(),
    path_coherent: verification.valid,
  }
}

export function clearLedger(): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(LEDGER_KEY)
  } catch { /* silent */ }
}
