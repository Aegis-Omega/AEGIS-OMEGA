---- MODULE CRDTLattice ----
\* ============================================================
\* AEGIS Ω — CRDT Convergence Lattice Formal Model
\* Gate 25 · Epistemic Tier: T0
\*
\* Models the SITRState join semilattice.
\* Proves three core semilattice laws:
\*
\*   IDEMPOTENT:   Join(s, s) = s
\*   COMMUTATIVE:  Join(a, b) = Join(b, a)
\*   MONOTONE:     PhaseOrdinal(Join(a, b)) >= PhaseOrdinal(a)
\*
\* The six SITRState values form a total order:
\*   STABLE < DEGRADED < UNSTABLE < CONSTITUTIONAL_RISK
\*            < CONTAINED < COMPROMISED
\*
\* Join is the least upper bound (supremum) in this lattice:
\*   Join(a, b) = the state with the higher ordinal.
\* ============================================================

EXTENDS Naturals

CONSTANTS
    SITRStates   \* = { STABLE, DEGRADED, UNSTABLE, CONSTITUTIONAL_RISK, CONTAINED, COMPROMISED }

ASSUME SITRStates = { "STABLE", "DEGRADED", "UNSTABLE",
                      "CONSTITUTIONAL_RISK", "CONTAINED", "COMPROMISED" }

VARIABLES state_a, state_b

\* ─── Phase ordinal (total order on SITRState) ────────────

PhaseOrdinal(s) ==
    CASE s = "STABLE"              -> 0
      [] s = "DEGRADED"            -> 1
      [] s = "UNSTABLE"            -> 2
      [] s = "CONSTITUTIONAL_RISK" -> 3
      [] s = "CONTAINED"           -> 4
      [] s = "COMPROMISED"         -> 5

\* ─── Join (least upper bound) ────────────────────────────

Join(a, b) ==
    IF PhaseOrdinal(a) >= PhaseOrdinal(b) THEN a ELSE b

\* ─── Initial state ───────────────────────────────────────

Init ==
    /\ state_a \in SITRStates
    /\ state_b \in SITRStates

\* ─── Stuttering step: model state exploration ────────────

Next ==
    \/ \E s \in SITRStates : state_a' = s /\ UNCHANGED state_b
    \/ \E s \in SITRStates : state_b' = s /\ UNCHANGED state_a

\* ─── Semilattice laws ────────────────────────────────────

\* LAW 1: Idempotency — Join(s, s) = s
IDEMPOTENT ==
    \A s \in SITRStates : Join(s, s) = s

\* LAW 2: Commutativity — Join(a, b) = Join(b, a)
COMMUTATIVE ==
    \A a \in SITRStates :
    \A b \in SITRStates :
        Join(a, b) = Join(b, a)

\* LAW 3: Monotonicity — PhaseOrdinal(Join(a, b)) >= PhaseOrdinal(a)
MONOTONE ==
    \A a \in SITRStates :
    \A b \in SITRStates :
        PhaseOrdinal(Join(a, b)) >= PhaseOrdinal(a)

\* LAW 4: Associativity — Join(Join(a,b),c) = Join(a,Join(b,c))
ASSOCIATIVE ==
    \A a \in SITRStates :
    \A b \in SITRStates :
        \A c \in SITRStates :
            Join(Join(a, b), c) = Join(a, Join(b, c))

\* ─── Per-state invariants ────────────────────────────────

\* Both state_a and state_b satisfy all semilattice laws at all times.
Invariant ==
    /\ IDEMPOTENT
    /\ COMMUTATIVE
    /\ MONOTONE
    /\ ASSOCIATIVE

\* ─── Convergence: repeated joins stabilise ───────────────

\* Once state escalates to COMPROMISED it cannot be reduced by Join.
COMPROMISED_IS_ABSORBING ==
    \A b \in SITRStates :
        Join("COMPROMISED", b) = "COMPROMISED"

\* Escalation is irreversible under Join:
\*   if PhaseOrdinal(a) > PhaseOrdinal(b) then Join(a, b) = a
JOIN_PRESERVES_HIGHER ==
    \A a \in SITRStates :
    \A b \in SITRStates :
        PhaseOrdinal(a) >= PhaseOrdinal(b) => Join(a, b) = a

\* ─── Safety and specification ────────────────────────────

Spec == Init /\ [][Next]_<<state_a, state_b>>

Safety == []Invariant

====
