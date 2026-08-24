"""Research status as a state machine, not a label an author types.

The failure this exists to prevent, observed 2026-08-24: rows in an authority
matrix carried VERIFIED with no computation behind them. They were not lies.
They were entries in a simulated timeline that had been imagined vividly
enough to be recalled as executed.

    CONJECTURED  -> analytically motivated; no code, no certificate
    TYPE_CHECKED -> all registered type gates PASS; spaces and dimensions agree
    COMPUTED     -> numerically established at fixed (receipt, N, tol)
    THEOREM      -> algebra or analysis; independent of threshold and of N

Promotion is one step at a time and carries its evidence. Demotion is always
legal and always recorded -- that is how dim(PV)=2 went from THEOREM back to
COMPUTED once s_min(A_-) was measured dipping to 6.64e-05.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .gates import GateVerdict, SCHEMA_VERSION, digest


class ResearchStatus(str, Enum):
    CONJECTURED = "CONJECTURED"
    TYPE_CHECKED = "TYPE_CHECKED"
    COMPUTED = "COMPUTED"
    THEOREM = "THEOREM"


_ORDER = [
    ResearchStatus.CONJECTURED,
    ResearchStatus.TYPE_CHECKED,
    ResearchStatus.COMPUTED,
    ResearchStatus.THEOREM,
]


class IllegalPromotion(Exception):
    pass


@dataclass(frozen=True)
class Evidence:
    """What a status is standing on. THEOREM stands on no tolerance at all."""
    receipt_digest: Optional[str] = None
    N: Optional[int] = None
    tol: Optional[float] = None
    argument: Optional[str] = None

    def label(self) -> str:
        if self.tol is not None:
            return f"N={self.N}, tol={self.tol:g}, receipt={(self.receipt_digest or '')[:12]}"
        return self.argument or "-"


@dataclass
class Claim:
    claim_id: str
    statement: str
    status: ResearchStatus = ResearchStatus.CONJECTURED
    evidence: Evidence = field(default_factory=Evidence)
    history: list = field(default_factory=list)

    def _record(self, old, new, ev, note):
        self.history.append({
            "schema": SCHEMA_VERSION, "from": old.value, "to": new.value,
            "evidence": ev.label(), "note": note,
            "digest": digest(self.claim_id, old.value, new.value, ev.label()),
        })

    def transition(self, new: ResearchStatus, evidence: Evidence = Evidence(),
                   note: str = "") -> "Claim":
        old = self.status
        i, j = _ORDER.index(old), _ORDER.index(new)

        if j > i + 1:
            raise IllegalPromotion(
                f"{self.claim_id}: {old.value} -> {new.value} skips "
                f"{_ORDER[i + 1].value}; each step carries its own evidence"
            )
        if new is ResearchStatus.TYPE_CHECKED and j > i:
            if evidence.argument is None:
                raise IllegalPromotion(
                    f"{self.claim_id}: TYPE_CHECKED needs the gate set that passed"
                )
        if new is ResearchStatus.COMPUTED and j > i:
            missing = [k for k, v in (("receipt_digest", evidence.receipt_digest),
                                      ("N", evidence.N),
                                      ("tol", evidence.tol)) if v is None]
            if missing:
                raise IllegalPromotion(
                    f"{self.claim_id}: COMPUTED without {', '.join(missing)}; "
                    f"a status that cannot name its run is a recollection"
                )
        if new is ResearchStatus.THEOREM and j > i:
            if evidence.tol is not None:
                raise IllegalPromotion(
                    f"{self.claim_id}: THEOREM cannot rest on tol={evidence.tol:g}; "
                    f"a result that moves with a threshold is COMPUTED, not proved"
                )
            if not evidence.argument:
                raise IllegalPromotion(f"{self.claim_id}: THEOREM needs its argument")

        self.status, self.evidence = new, evidence
        self._record(old, new, evidence, note)
        return self

    def demote(self, new: ResearchStatus, evidence: Evidence, reason: str) -> "Claim":
        """Always legal. Always recorded. Reason is mandatory."""
        if _ORDER.index(new) >= _ORDER.index(self.status):
            raise IllegalPromotion(f"{self.claim_id}: {new.value} is not a demotion")
        if not reason:
            raise IllegalPromotion(f"{self.claim_id}: demotion needs a reason")
        old = self.status
        self.status, self.evidence = new, evidence
        self._record(old, new, evidence, f"DEMOTED: {reason}")
        return self
