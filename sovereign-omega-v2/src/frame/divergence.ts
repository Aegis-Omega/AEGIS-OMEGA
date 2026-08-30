// ============================================================
// SOVEREIGN OMEGA — Divergence Classification Engine
// EPISTEMIC TIER: T0 · Gate 31
//
// Implements the constitutional Divergence Laws from the
// production handoff. Classifies topology divergence between
// two governance nodes and enforces the Divergence Freeze Law:
//
//   TopologyHash_A ≠ TopologyHash_B → mutation authority suspended
//
// Divergence Classes (D0..D4):
//   D0 — observational drift (sequence delta only)
//   D1 — serializer mismatch (same seq, different verdict/state)
//   D2 — topology mismatch (different ledger or DFA certificate)
//   D3 — ownership inconsistency (different consensus QC)
//   D4 — constitutional invalidity (verification fails)
//
// A DivergenceReport is the constitutional incident record.
// mutationAuthorityActive() enforces the freeze law.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import { verifyTopology } from '../frame/topology.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { GovernanceTopology } from '../frame/topology.js'

export const DIVERGENCE_SCHEMA_VERSION = '1.0.0' as const

// ─── Divergence class ──────────────────────────────────────

export type DivergenceClass = 'D0' | 'D1' | 'D2' | 'D3' | 'D4'

const DIVERGENCE_SEVERITY: Record<DivergenceClass, number> = {
  D0: 0, D1: 1, D2: 2, D3: 3, D4: 4,
}

/** True iff class a is strictly more severe than class b. */
export function isMoreSevere(a: DivergenceClass, b: DivergenceClass): boolean {
  return DIVERGENCE_SEVERITY[a] > DIVERGENCE_SEVERITY[b]
}

// ─── Types ─────────────────────────────────────────────────

/** The constitutional incident record for a topology divergence. */
export interface DivergenceReport {
  readonly divergence_class: DivergenceClass
  readonly topology_hash_a: SHA256Hex
  readonly topology_hash_b: SHA256Hex
  readonly sequence_a: SequenceNumber
  readonly sequence_b: SequenceNumber
  readonly mutation_authority_active: boolean
  readonly report_hash: SHA256Hex
  readonly schema_version: typeof DIVERGENCE_SCHEMA_VERSION
  readonly is_replay_reconstructable: true
}

/** Result when both topologies are identical — no divergence. */
export interface ConvergenceRecord {
  readonly topology_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly is_converged: true
  readonly is_replay_reconstructable: true
}

export type ComparisonResult =
  | { readonly kind: 'CONVERGED'; readonly record: ConvergenceRecord }
  | { readonly kind: 'DIVERGED';  readonly report: DivergenceReport }

// ─── Classification logic ──────────────────────────────────

async function classifyDivergence(
  a: GovernanceTopology,
  b: GovernanceTopology,
): Promise<DivergenceClass> {
  // D4: either topology fails self-verification
  const [validA, validB] = await Promise.all([verifyTopology(a), verifyTopology(b)])
  if (!validA || !validB) return 'D4'

  // D3: same everything except consensus_qc_hash
  if (
    a.sitr_state === b.sitr_state &&
    a.aoie_global_state === b.aoie_global_state &&
    a.constitutional_verdict === b.constitutional_verdict &&
    a.ledger_root === b.ledger_root &&
    a.dfa_certificate_hash === b.dfa_certificate_hash &&
    a.consensus_qc_hash !== b.consensus_qc_hash
  ) return 'D3'

  // D2: topology mismatch in ledger root or DFA certificate
  if (a.ledger_root !== b.ledger_root || a.dfa_certificate_hash !== b.dfa_certificate_hash) return 'D2'

  // D1: same sequence, same structural hashes, different classification
  if (
    a.sequence === b.sequence &&
    (a.sitr_state !== b.sitr_state ||
     a.aoie_global_state !== b.aoie_global_state ||
     a.constitutional_verdict !== b.constitutional_verdict)
  ) return 'D1'

  // D0: sequence delta only
  return 'D0'
}

// ─── Core functions ────────────────────────────────────────

/**
 * Compare two topology snapshots. Returns CONVERGED if topology_hash
 * values are identical, or a classified DivergenceReport otherwise.
 *
 * Enforces the Divergence Freeze Law: mutation_authority_active is
 * false whenever divergence_class >= D2.
 */
export async function compareTopologies(
  a: GovernanceTopology,
  b: GovernanceTopology,
): Promise<ComparisonResult> {
  if (a.topology_hash === b.topology_hash) {
    return {
      kind: 'CONVERGED',
      record: deepFreeze<ConvergenceRecord>({
        topology_hash: a.topology_hash,
        sequence: a.sequence,
        is_converged: true,
        is_replay_reconstructable: true,
      }),
    }
  }

  const divergence_class = await classifyDivergence(a, b)
  const mutation_authority_active = DIVERGENCE_SEVERITY[divergence_class] < 2

  const report_hash = await hashValue({
    divergence_class,
    topology_hash_a: a.topology_hash,
    topology_hash_b: b.topology_hash,
    sequence_a: a.sequence,
    sequence_b: b.sequence,
    schema_version: DIVERGENCE_SCHEMA_VERSION,
  }) as SHA256Hex

  return {
    kind: 'DIVERGED',
    report: deepFreeze<DivergenceReport>({
      divergence_class,
      topology_hash_a: a.topology_hash,
      topology_hash_b: b.topology_hash,
      sequence_a: a.sequence,
      sequence_b: b.sequence,
      mutation_authority_active,
      report_hash,
      schema_version: DIVERGENCE_SCHEMA_VERSION,
      is_replay_reconstructable: true,
    }),
  }
}

/**
 * The Divergence Freeze Law: mutation authority is active only
 * when the most severe divergence in a set is below D2.
 */
export function mutationAuthorityActive(
  reports: readonly DivergenceReport[],
): boolean {
  if (reports.length === 0) return true
  return reports.every(r => DIVERGENCE_SEVERITY[r.divergence_class] < 2)
}
