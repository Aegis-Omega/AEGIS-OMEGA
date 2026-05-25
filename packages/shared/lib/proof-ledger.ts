/**
 * AEGIS Cross-Product Proof Ledger
 *
 * Equivalence-invariant: a token's validity is independent of which backend
 * produced the inference. The chain_hash IS the token identity — univalent
 * in the HoTT sense: two records with the same chain_hash are identical.
 *
 * The ledger is the canonical presentation of accumulated constitutional proof,
 * stored in localStorage so it persists across products in the same browser.
 */

import type { ConstitutionalAuditRecord, BackendType } from './constitutional-ai.js'

export type ProductId = 'platform-picker' | 'hook-generator' | 'content-calendar' | 'cockpit'

export interface ProofToken {
  readonly token_id: string          // = chain_hash (identity IS the hash)
  readonly product: ProductId
  readonly call_id: string
  readonly prompt_hash: string
  readonly backend: BackendType
  readonly ccil_valid: boolean
  readonly session_index: number
  readonly minted_at: number         // timestamp_ms
  readonly latency_ms: number
}

export interface LedgerStats {
  total: number
  ccil_valid: number
  ccil_ratio: number                 // approved / total — should stay ≤ 1/φ ceiling
  by_product: Record<string, number>
  by_backend: Record<string, number>
  chain_tip: string                  // token_id of the most recent token
}

const LEDGER_KEY = 'aegis_proof_ledger_v1'
const MAX_TOKENS = 500              // prune oldest beyond this

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
    // storage quota exceeded — trim and retry
    try {
      localStorage.setItem(LEDGER_KEY, JSON.stringify(tokens.slice(-Math.floor(MAX_TOKENS / 2))))
    } catch { /* silent */ }
  }
}

/**
 * Mint a proof token from a constitutional audit record.
 * Called automatically by callConstitutional — never call directly.
 */
export function mintToken(
  record: ConstitutionalAuditRecord,
  product: ProductId,
): ProofToken {
  const token: ProofToken = Object.freeze({
    token_id: record.chain_hash,
    product,
    call_id: record.call_id,
    prompt_hash: record.prompt_hash,
    backend: record.backend,
    ccil_valid: record.ccil_valid,
    session_index: record.session_index,
    minted_at: record.timestamp_ms,
    latency_ms: record.latency_ms,
  })

  const ledger = readLedger()
  ledger.push(token)

  // Prune oldest if over cap — keep canonical recent history
  const pruned = ledger.length > MAX_TOKENS ? ledger.slice(-MAX_TOKENS) : ledger
  writeLedger(pruned)

  return token
}

/** Read the full cross-product ledger */
export function getLedger(): ProofToken[] {
  return readLedger()
}

/** Aggregate stats across all products */
export function getLedgerStats(): LedgerStats {
  const tokens = readLedger()
  const by_product: Record<string, number> = {}
  const by_backend: Record<string, number> = {}
  let ccil_valid = 0

  for (const t of tokens) {
    by_product[t.product] = (by_product[t.product] ?? 0) + 1
    by_backend[t.backend] = (by_backend[t.backend] ?? 0) + 1
    if (t.ccil_valid) ccil_valid++
  }

  return {
    total: tokens.length,
    ccil_valid,
    ccil_ratio: tokens.length > 0 ? ccil_valid / tokens.length : 0,
    by_product,
    by_backend,
    chain_tip: tokens.length > 0 ? tokens[tokens.length - 1].token_id : 'genesis',
  }
}

/** Clear the ledger — for testing only */
export function clearLedger(): void {
  try {
    if (typeof localStorage !== 'undefined') localStorage.removeItem(LEDGER_KEY)
  } catch { /* silent */ }
}
