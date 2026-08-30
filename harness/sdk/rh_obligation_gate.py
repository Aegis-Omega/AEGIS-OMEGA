"""Executable fail-closed obligation ledger for the RH proofline.

The gate is intentionally unable to infer mathematical closure from numerical,
empirical, CI, or prose evidence. Only FORMALLY_VERIFIED obligations count
as closed for the final verdict.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any, Mapping


class ObligationState(str, Enum):
    OPEN = "OPEN"
    BLOCKED = "BLOCKED"
    PARTIALLY_FORMALIZED = "PARTIALLY_FORMALIZED"
    FORMALLY_VERIFIED = "FORMALLY_VERIFIED"
    REFUTED = "REFUTED"


@dataclass(frozen=True)
class Obligation:
    obligation_id: str
    state: ObligationState
    depends_on: tuple[str, ...] = ()
    authority_note: str = ""


DEFAULT_OBLIGATIONS: tuple[Obligation, ...] = (
    # Conservative initial classifications: do not promote analytic or
    # computational evidence to machine-checked theorem status.
    Obligation("W0_XiFormulation", ObligationState.PARTIALLY_FORMALIZED,
               authority_note="Xi/Weil setup exists, but final concrete criterion closure is not machine-bound."),
    Obligation("W1_FinitePrimePhaseBoundary", ObligationState.BLOCKED,
               depends_on=("W0_XiFormulation",),
               authority_note="Reflection/index-set boundary requires an explicit term-wise or boundary-corrected theorem."),
    Obligation("W2_ConstructiveTrigCalculus", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="Prime-diagonal constructive trig/calculus witness remains open."),
    Obligation("W3_ArchimedeanSingularity", ObligationState.PARTIALLY_FORMALIZED,
               depends_on=("W0_XiFormulation",),
               authority_note="Analytic removable-singularity reasoning is not promoted here to proof-kernel closure."),
    Obligation("W4_GaussianTailTheorem", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="QForm constant arithmetic exists; the real-analysis theorem remains open."),
    Obligation("W5_CompositeTrapezoidTheorem", ObligationState.OPEN,
               depends_on=("W0_XiFormulation",),
               authority_note="Composite-trapezoid remainder theorem remains open in the authority lane."),
    Obligation("W6_GuinandWeilOperatorIdentity", ObligationState.OPEN,
               depends_on=("W1_FinitePrimePhaseBoundary", "W2_ConstructiveTrigCalculus", "W3_ArchimedeanSingularity"),
               authority_note="Concrete formula-to-Weil operator identity is not machine-bound."),
    Obligation("W7_ContinuousArchimedeanOrder", ObligationState.OPEN,
               depends_on=("W3_ArchimedeanSingularity",),
               authority_note="Finite exact Gram PSD does not establish the continuous representation/order theorem."),
    Obligation("W8_DensityContinuityCoverage", ObligationState.OPEN,
               depends_on=("W4_GaussianTailTheorem", "W5_CompositeTrapezoidTheorem", "W6_GuinandWeilOperatorIdentity", "W7_ContinuousArchimedeanOrder"),
               authority_note="Density, continuity, approximation, and universal coverage remain load-bearing."),
    Obligation("W9_ConcreteWeilCriterion", ObligationState.OPEN,
               depends_on=("W8_DensityContinuityCoverage",),
               authority_note="Global positivity for the actual Weil form and the concrete criterion are not machine-bound."),
    Obligation("W10_FinalRiemannHypothesis", ObligationState.BLOCKED,
               depends_on=("W9_ConcreteWeilCriterion",),
               authority_note="Final RH theorem is blocked until every dependency is formally verified."),
)


class RHObligationLedger:
    def __init__(self, obligations: tuple[Obligation, ...] = DEFAULT_OBLIGATIONS):
        self._obligations = {o.obligation_id: o for o in obligations}
        if len(self._obligations) != len(obligations):
            raise ValueError("duplicate obligation_id")
        self._validate_dependencies()

    @property
    def obligations(self) -> Mapping[str, Obligation]:
        return dict(self._obligations)

    def _validate_dependencies(self) -> None:
        ids = set(self._obligations)
        for obligation in self._obligations.values():
            missing = set(obligation.depends_on) - ids
            if missing:
                raise ValueError(f"{obligation.obligation_id} has unknown dependencies: {sorted(missing)}")

    def with_state(self, obligation_id: str, state: ObligationState, authority_note: str) -> "RHObligationLedger":
        """Return a new ledger with one explicit state update.

        State changes require an authority note so callers cannot silently promote
        an obligation. This class still does not validate a proof artifact itself;
        the external proof-kernel/receipt verifier must do that before calling it.
        """
        if obligation_id not in self._obligations:
            raise KeyError(obligation_id)
        if not authority_note.strip():
            raise ValueError("authority_note is required for every state transition")
        updated = []
        for obligation in self._obligations.values():
            if obligation.obligation_id == obligation_id:
                updated.append(Obligation(obligation_id, state, obligation.depends_on, authority_note))
            else:
                updated.append(obligation)
        return RHObligationLedger(tuple(updated))

    def verify_final_closure(self) -> dict[str, Any]:
        unresolved = [
            o.obligation_id
            for o in self._obligations.values()
            if o.state is not ObligationState.FORMALLY_VERIFIED
        ]
        dependency_violations = []
        for obligation in self._obligations.values():
            if obligation.state is ObligationState.FORMALLY_VERIFIED:
                open_dependencies = [
                    dep for dep in obligation.depends_on
                    if self._obligations[dep].state is not ObligationState.FORMALLY_VERIFIED
                ]
                if open_dependencies:
                    dependency_violations.append({
                        "obligation": obligation.obligation_id,
                        "unverified_dependencies": open_dependencies,
                    })

        if unresolved or dependency_violations:
            return {
                "verdict": "RH_NOT_PROVEN",
                "gate_status": "FAIL_CLOSED",
                "open_obligations": unresolved,
                "dependency_violations": dependency_violations,
                "highest_leverage_blocker": unresolved[0] if unresolved else None,
            }

        return {
            "verdict": "RH_PROVEN_FORMALLY",
            "gate_status": "ADMITTED",
            "open_obligations": [],
            "dependency_violations": [],
            "highest_leverage_blocker": None,
        }
