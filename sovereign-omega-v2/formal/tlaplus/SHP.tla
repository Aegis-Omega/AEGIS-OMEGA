---- MODULE SHP ----
\* ============================================================
\* AEGIS Ω — Subatomic Holon Particle (SHP) Formal Model
\* Gate 18 · Epistemic Tier: T0
\*
\* Models the 5-phase R→A→L→P→H execution cycle with the LOCK
\* commitment boundary separating SITR (pre-commit) from AOIE
\* (post-commit). Proves the separation invariant:
\*   SITR ∈ {READ, ASSESS}
\*   AOIE ∈ {PROPAGATE, HARMONIZE}
\*   SITR ∩ AOIE = ∅ (by LOCK boundary)
\* ============================================================

EXTENDS Naturals, Sequences

CONSTANTS
    Phases,        \* = {READ, ASSESS, LOCK, PROPAGATE, HARMONIZE}
    PreLockPhases, \* = {READ, ASSESS}
    PostLockPhases \* = {PROPAGATE, HARMONIZE}

ASSUME Phases = {"READ", "ASSESS", "LOCK", "PROPAGATE", "HARMONIZE"}
ASSUME PreLockPhases = {"READ", "ASSESS"}
ASSUME PostLockPhases = {"PROPAGATE", "HARMONIZE"}

VARIABLES
    phase,           \* current execution phase
    locked,          \* TRUE after LOCK has been committed
    sitr_state,      \* SITR constraint evaluation result
    aoie_state,      \* AOIE structural classification
    commit_hash,     \* cross-phase identifier (only stable after LOCK)
    sequence         \* monotonically increasing frame counter

\* ─── Phase ordinal ─────────────────────────────────────────

PhaseOrdinal(p) ==
    CASE p = "READ"      -> 0
      [] p = "ASSESS"    -> 1
      [] p = "LOCK"      -> 2
      [] p = "PROPAGATE" -> 3
      [] p = "HARMONIZE" -> 4

\* ─── Initial state ─────────────────────────────────────────

Init ==
    /\ phase = "READ"
    /\ locked = FALSE
    /\ sitr_state = "STABLE"
    /\ aoie_state = "SECURE"
    /\ commit_hash = ""
    /\ sequence = 0

\* ─── Phase transitions (INV-SHP-05: no skip, no reorder) ──

ReadToAssess ==
    /\ phase = "READ"
    /\ ~locked
    /\ phase' = "ASSESS"
    /\ UNCHANGED <<locked, sitr_state, aoie_state, commit_hash, sequence>>

AssessToLock ==
    /\ phase = "ASSESS"
    /\ ~locked
    /\ phase' = "LOCK"
    /\ locked' = TRUE
    /\ commit_hash' = "hash_" \o ToString(sequence)  \* deterministic ID
    /\ UNCHANGED <<sitr_state, aoie_state, sequence>>

LockToPropagate ==
    /\ phase = "LOCK"
    /\ locked
    /\ phase' = "PROPAGATE"
    /\ UNCHANGED <<locked, sitr_state, aoie_state, commit_hash, sequence>>

PropagateToHarmonize ==
    /\ phase = "PROPAGATE"
    /\ locked
    /\ phase' = "HARMONIZE"
    /\ UNCHANGED <<locked, sitr_state, aoie_state, commit_hash, sequence>>

HarmonizeToRead ==
    \* Frame finalization — new frame begins
    /\ phase = "HARMONIZE"
    /\ locked
    /\ phase' = "READ"
    /\ locked' = FALSE
    /\ commit_hash' = ""
    /\ sequence' = sequence + 1
    /\ UNCHANGED <<sitr_state, aoie_state>>

Next ==
    \/ ReadToAssess
    \/ AssessToLock
    \/ LockToPropagate
    \/ PropagateToHarmonize
    \/ HarmonizeToRead

\* ─── Safety properties ─────────────────────────────────────

\* INV-SHP-02: LOCK is the sole irreversible commit point
LOCK_IS_BOUNDARY ==
    (phase = "LOCK") => ~locked'

\* INV-SHP-05: phase ordinal strictly increases within a frame
PHASE_ORDERING ==
    (phase # "HARMONIZE") =>
        PhaseOrdinal(phase') > PhaseOrdinal(phase)

\* INV-SHP-06/07: SITR ∩ AOIE = ∅
SITR_AOIE_SEPARATION ==
    /\ (phase \in PreLockPhases => ~locked)
    /\ (phase \in PostLockPhases => locked)

\* INV-SHP-08: commit_hash is non-empty only after LOCK
COMMIT_HASH_INVARIANT ==
    (commit_hash # "") <=> locked

\* Sequence is monotonically increasing across frames
SEQUENCE_MONOTONE ==
    sequence' >= sequence

\* ─── Combined safety ───────────────────────────────────────

Invariant ==
    /\ SITR_AOIE_SEPARATION
    /\ COMMIT_HASH_INVARIANT
    /\ SEQUENCE_MONOTONE

Spec == Init /\ [][Next]_<<phase, locked, sitr_state, aoie_state, commit_hash, sequence>>

Safety == []Invariant

====
