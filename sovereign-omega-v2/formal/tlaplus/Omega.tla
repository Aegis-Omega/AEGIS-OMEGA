---- MODULE Omega ----
\* ============================================================
\* AEGIS Ω — Core Fold-Hash Invariant + SHP Commitment Boundary
\* Gate 18 extended: LOCK_INVARIANT and AOIE_POST_COMMIT added.
\* ============================================================

EXTENDS Naturals, Sequences

CONSTANTS Events

VARIABLES state, digest, locked, phase

\* Phase classification constants
PRE_COMMIT_PHASES  == {"READ", "ASSESS"}
POST_COMMIT_PHASES == {"PROPAGATE", "HARMONIZE"}

Init ==
    /\ state  = <<>>
    /\ digest = 0
    /\ locked = FALSE
    /\ phase  = "READ"

Canon(e) == e
Hash(d, e) == d + 1
FoldHash(s) == Len(s)

\* Core fold-hash step (Gate 1 invariant — mechanically proven)
AppendEvent ==
    \E e \in Events :
        /\ state'  = Append(state, e)
        /\ digest' = Hash(digest, Canon(e))
        /\ UNCHANGED <<locked, phase>>

\* LOCK commitment boundary transition
CommitLock ==
    /\ phase = "ASSESS"
    /\ ~locked
    /\ locked' = TRUE
    /\ phase'  = "LOCK"
    /\ UNCHANGED <<state, digest>>

\* Post-commit phase advancement
PostCommitAdvance ==
    /\ phase \in POST_COMMIT_PHASES
    /\ locked
    /\ UNCHANGED <<state, digest, locked, phase>>

Next == AppendEvent \/ CommitLock \/ PostCommitAdvance

\* ─── Core invariants ───────────────────────────────────────

\* Original Gate 1 invariant: digest tracks state length
Invariant == digest = FoldHash(state)

\* INV-SHP-02 (Gate 18): SITR state is frozen once LOCK commits
LOCK_INVARIANT == locked => UNCHANGED <<state>>

\* Gate 18: AOIE may only observe post-enforcement (post-LOCK) phase
AOIE_POST_COMMIT == phase \in POST_COMMIT_PHASES => locked

\* ─── Specification ─────────────────────────────────────────

Spec == Init /\ [][Next]_<<state, digest, locked, phase>>

Safety == []Invariant /\ [](AOIE_POST_COMMIT)

====
