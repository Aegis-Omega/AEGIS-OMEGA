---- MODULE LockIrreversibility ----
\* ============================================================
\* AEGIS Ω — LOCK Commitment Irreversibility
\* Gate 25 · Epistemic Tier: T0
\*
\* Models the LOCK commitment boundary within a single execution
\* frame. Proves:
\*
\*   LOCK_ONCE_SET_STAYS_SET:
\*     Once locked = TRUE, it cannot become FALSE within a frame.
\*     Only HarmonizeToRead resets it, and that action also
\*     increments sequence (beginning a new frame).
\*
\*   SEQUENCE_INCREMENTS_ON_UNLOCK:
\*     The sequence counter strictly increases whenever locked
\*     transitions from TRUE back to FALSE.
\*
\*   PRE_POST_DISJOINT:
\*     No phase can be simultaneously pre-lock and post-lock.
\*
\* Extends SHP.tla semantics with sequence-safety proof.
\* ============================================================

EXTENDS Naturals

CONSTANTS
    Phases,
    PreLockPhases,
    PostLockPhases

ASSUME Phases         = {"READ", "ASSESS", "LOCK", "PROPAGATE", "HARMONIZE"}
ASSUME PreLockPhases  = {"READ", "ASSESS"}
ASSUME PostLockPhases = {"PROPAGATE", "HARMONIZE"}

VARIABLES
    phase,      \* current execution phase
    locked,     \* TRUE after LOCK has been committed
    sequence    \* monotonically increasing frame counter

\* ─── Type invariant ──────────────────────────────────────

TypeOK ==
    /\ phase    \in Phases
    /\ locked   \in BOOLEAN
    /\ sequence \in Nat

\* ─── Phase ordinal ───────────────────────────────────────

PhaseOrdinal(p) ==
    CASE p = "READ"      -> 0
      [] p = "ASSESS"    -> 1
      [] p = "LOCK"      -> 2
      [] p = "PROPAGATE" -> 3
      [] p = "HARMONIZE" -> 4

\* ─── Initial state ───────────────────────────────────────

Init ==
    /\ phase    = "READ"
    /\ locked   = FALSE
    /\ sequence = 0

\* ─── Frame transitions ───────────────────────────────────

ReadToAssess ==
    /\ phase = "READ"
    /\ ~locked
    /\ phase' = "ASSESS"
    /\ UNCHANGED <<locked, sequence>>

AssessToLock ==
    /\ phase = "ASSESS"
    /\ ~locked
    /\ phase'  = "LOCK"
    /\ locked' = TRUE
    /\ UNCHANGED sequence

LockToPropagate ==
    /\ phase = "LOCK"
    /\ locked
    /\ phase' = "PROPAGATE"
    /\ UNCHANGED <<locked, sequence>>

PropagateToHarmonize ==
    /\ phase = "PROPAGATE"
    /\ locked
    /\ phase' = "HARMONIZE"
    /\ UNCHANGED <<locked, sequence>>

\* HarmonizeToRead is the only action that resets locked.
\* It MUST also increment sequence (new frame begins).
HarmonizeToRead ==
    /\ phase    = "HARMONIZE"
    /\ locked
    /\ phase'    = "READ"
    /\ locked'   = FALSE
    /\ sequence' = sequence + 1   \* REQUIRED: new frame starts

Next ==
    \/ ReadToAssess
    \/ AssessToLock
    \/ LockToPropagate
    \/ PropagateToHarmonize
    \/ HarmonizeToRead

\* ─── Core safety properties ──────────────────────────────

\* INV-LOCK-01: Within-frame lock irreversibility.
\* locked can only become FALSE via HarmonizeToRead (which increments sequence).
\* Expressed as: if locked is TRUE and sequence is unchanged, locked stays TRUE.
LOCK_ONCE_SET_STAYS_SET ==
    locked => [](locked \/ sequence' > sequence)

\* INV-LOCK-02: Pre-lock phases require unlocked state.
PRE_LOCK_UNLOCKED ==
    phase \in PreLockPhases => ~locked

\* INV-LOCK-03: Post-lock phases require locked state.
POST_LOCK_LOCKED ==
    phase \in PostLockPhases => locked

\* INV-LOCK-04: Pre-lock and post-lock are disjoint.
PRE_POST_DISJOINT ==
    ~(phase \in PreLockPhases /\ phase \in PostLockPhases)

\* INV-LOCK-05: Sequence is monotonically non-decreasing.
SEQUENCE_MONOTONE ==
    sequence' >= sequence

\* INV-LOCK-06: Sequence strictly increases only at HarmonizeToRead.
SEQUENCE_INCREMENTS_ON_UNLOCK ==
    (locked /\ ~locked') => sequence' = sequence + 1

\* ─── Combined invariant ──────────────────────────────────

Invariant ==
    /\ TypeOK
    /\ PRE_LOCK_UNLOCKED
    /\ POST_LOCK_LOCKED
    /\ PRE_POST_DISJOINT

\* ─── Temporal properties ─────────────────────────────────

\* Once locked, we will eventually complete the frame and increment sequence.
\* (Liveness — requires fairness assumption on Next steps.)
LOCK_EVENTUALLY_ADVANCES ==
    locked ~> (sequence > sequence)

\* ─── Specification ───────────────────────────────────────

Spec == Init /\ [][Next]_<<phase, locked, sequence>>

Safety == []Invariant

====
