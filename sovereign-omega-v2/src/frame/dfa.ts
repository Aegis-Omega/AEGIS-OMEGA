// ============================================================
// SOVEREIGN OMEGA — SHP Transition Certifier (Replay DFA)
// EPISTEMIC TIER: T0 · Gate 28
//
// Formal deterministic finite automaton enforcing the SHP
// 5-phase execution cycle at runtime. Produces a cryptographic
// transition certificate for each phase boundary — a proof
// chain that the execution is constitutionally valid.
//
// Invariants enforced mechanically:
//   INV-SHP-01  ASSESS must occur before LOCK
//   INV-SHP-02  LOCK is a single immutable commit point
//   INV-SHP-05  No phase may be reordered or skipped
//
// The transition_hash is:
//   sha256(canonicalize({from, to, state_hash, prev_hash, seq}))
// forming a cryptographic chain over the execution trace.
// ============================================================

import { deepFreeze } from '../core/immutable.js'
import { hashValue } from '../core/hashing.js'
import type { SHA256Hex, SequenceNumber } from '../core/types.js'
import type { Phase } from '../shp/types.js'

export { type Phase }

// ─── DFA State Type ────────────────────────────────────────

export type DFAState = Phase | 'IDLE'

// ─── Transition Table ──────────────────────────────────────
// Linear R→A→L→P→H — no branching, no backtracking.

const TRANSITION_TABLE: ReadonlyArray<readonly [DFAState, Phase]> = Object.freeze([
  ['IDLE',       'READ'      ],
  ['READ',       'ASSESS'    ],
  ['ASSESS',     'LOCK'      ],
  ['LOCK',       'PROPAGATE' ],
  ['PROPAGATE',  'HARMONIZE' ],
])

function nextPhase(from: DFAState): Phase | null {
  const entry = TRANSITION_TABLE.find(([f]) => f === from)
  return entry != null ? entry[1]! : null
}

// ─── Error ─────────────────────────────────────────────────

export class SHPExecutionError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SHPExecutionError'
  }
}

// ─── Types ─────────────────────────────────────────────────

/**
 * Cryptographic record of one phase transition.
 * transition_hash chains from the previous record's transition_hash,
 * forming a tamper-evident log of the execution trace.
 */
export interface FrameTransitionRecord {
  readonly from_phase: DFAState
  readonly to_phase: Phase
  readonly state_hash: SHA256Hex
  readonly transition_hash: SHA256Hex
  readonly sequence: SequenceNumber
  readonly is_replay_reconstructable: true
}

/** Immutable DFA state machine snapshot after each transition. */
export interface SHPTransitionMachine {
  readonly current_phase: DFAState
  readonly last_transition_hash: SHA256Hex | null
  readonly sequence: SequenceNumber
  readonly step_count: number
}

/** Result of certifyExecution() — proof that a trace is constitutionally valid. */
export interface ExecutionCertificate {
  readonly is_valid: boolean
  readonly certificate_hash: SHA256Hex
  readonly step_count: number
  readonly sequence: SequenceNumber
  readonly is_replay_reconstructable: true
}

// ─── Factory ───────────────────────────────────────────────

/** Create a fresh DFA in the IDLE state for a given frame sequence. */
export function initialMachine(sequence: SequenceNumber): SHPTransitionMachine {
  return deepFreeze({
    current_phase: 'IDLE' as DFAState,
    last_transition_hash: null,
    sequence,
    step_count: 0,
  })
}

// ─── Transition ────────────────────────────────────────────

/**
 * Advance the DFA by one phase. Throws SHPExecutionError if the
 * requested phase is not the constitutional next phase.
 *
 * @param machine  Current DFA state (frozen)
 * @param toPhase  Requested next phase
 * @param stateHash  SHA-256 of the caller's state at this boundary
 * @returns New frozen machine + frozen transition record
 */
export async function transition(
  machine: SHPTransitionMachine,
  toPhase: Phase,
  stateHash: SHA256Hex,
): Promise<{ readonly machine: SHPTransitionMachine; readonly record: FrameTransitionRecord }> {
  const allowed = nextPhase(machine.current_phase)
  if (allowed === null || toPhase !== allowed) {
    throw new SHPExecutionError(
      `Invalid SHP transition: ${machine.current_phase} → ${toPhase}. ` +
      `Expected: ${machine.current_phase} → ${allowed ?? '(terminal)'}`
    )
  }

  const transitionHash = await hashValue({
    from_phase: machine.current_phase,
    to_phase: toPhase,
    state_hash: stateHash,
    prev_transition_hash: machine.last_transition_hash,
    sequence: machine.sequence,
  }) as SHA256Hex

  const record = deepFreeze<FrameTransitionRecord>({
    from_phase: machine.current_phase,
    to_phase: toPhase,
    state_hash: stateHash,
    transition_hash: transitionHash,
    sequence: machine.sequence,
    is_replay_reconstructable: true,
  })

  const nextMachine = deepFreeze<SHPTransitionMachine>({
    current_phase: toPhase,
    last_transition_hash: transitionHash,
    sequence: machine.sequence,
    step_count: machine.step_count + 1,
  })

  return Object.freeze({ machine: nextMachine, record })
}

// ─── Certification ─────────────────────────────────────────

/**
 * Verify that a sequence of transition records forms a complete,
 * constitutionally valid R→A→L→P→H execution trace.
 *
 * Checks:
 *   1. Exactly 5 records (IDLE→READ→ASSESS→LOCK→PROPAGATE→HARMONIZE)
 *   2. Each record's from_phase is the previous record's to_phase
 *   3. Each transition_hash chains from prev_transition_hash correctly
 *   4. The terminal phase is HARMONIZE
 */
export async function certifyExecution(
  records: readonly FrameTransitionRecord[],
  sequence: SequenceNumber,
): Promise<ExecutionCertificate> {
  const FULL_TRACE_LEN = TRANSITION_TABLE.length // 5

  if (records.length !== FULL_TRACE_LEN) {
    const certHash = await hashValue({ valid: false, reason: 'incomplete', step_count: records.length, sequence }) as SHA256Hex
    return deepFreeze<ExecutionCertificate>({
      is_valid: false,
      certificate_hash: certHash,
      step_count: records.length,
      sequence,
      is_replay_reconstructable: true,
    })
  }

  // Verify each link in the transition chain
  let prevHash: SHA256Hex | null = null
  let prevTo: DFAState = 'IDLE'
  for (const rec of records) {
    if (rec.from_phase !== prevTo) {
      const certHash = await hashValue({ valid: false, reason: 'phase_mismatch', sequence }) as SHA256Hex
      return deepFreeze<ExecutionCertificate>({
        is_valid: false, certificate_hash: certHash, step_count: records.length, sequence,
        is_replay_reconstructable: true,
      })
    }
    // Re-derive the expected transition_hash
    const expected = await hashValue({
      from_phase: rec.from_phase,
      to_phase: rec.to_phase,
      state_hash: rec.state_hash,
      prev_transition_hash: prevHash,
      sequence: rec.sequence,
    }) as SHA256Hex
    if (rec.transition_hash !== expected) {
      const certHash = await hashValue({ valid: false, reason: 'hash_mismatch', sequence }) as SHA256Hex
      return deepFreeze<ExecutionCertificate>({
        is_valid: false, certificate_hash: certHash, step_count: records.length, sequence,
        is_replay_reconstructable: true,
      })
    }
    prevHash = rec.transition_hash
    prevTo = rec.to_phase
  }

  if (prevTo !== 'HARMONIZE') {
    const certHash = await hashValue({ valid: false, reason: 'terminal_phase_wrong', sequence }) as SHA256Hex
    return deepFreeze<ExecutionCertificate>({
      is_valid: false, certificate_hash: certHash, step_count: records.length, sequence,
      is_replay_reconstructable: true,
    })
  }

  const certHash = await hashValue({
    valid: true,
    terminal_hash: prevHash,
    step_count: FULL_TRACE_LEN,
    sequence,
  }) as SHA256Hex

  return deepFreeze<ExecutionCertificate>({
    is_valid: true,
    certificate_hash: certHash,
    step_count: FULL_TRACE_LEN,
    sequence,
    is_replay_reconstructable: true,
  })
}
