"""Multi-agent schema-evolution consensus — RFC 0005 §3.

Agents do not trust a proposing agent's certificate; each independently
re-derives the evolution against *its own* local contract graph and discharges
the proof obligations (RFC 0005 §4). Consensus operates on **verified
obligations, not opinions** (the user's refinement):

    φ = (verified obligations) / (total obligations)      committed iff φ ≥ τ

where the default threshold τ is the constitutional 1/φ quorum
``(√5−1)/2`` (RFC 0001 root law). Because the tally is over discharged
obligations rather than votes, it is fully reproducible.

The peer-to-peer gossip transport of RFC 0005 §3 is infrastructure; this
module implements the verifiable core — independent kernel re-verification of
obligations and the deterministic quorum tally.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dc_field

from .evolution import OBLIGATIONS, diff, obligations
from .ir import IR

PHI_QUORUM = 0.6180339887  # (√5 − 1) / 2 — matches the repo's constitutional quorum


@dataclass
class AgentVerdict:
    agent: str
    verified: int          # obligations this agent found holding
    total: int             # obligations checked
    failed: list[str] = dc_field(default_factory=list)

    @property
    def all_hold(self) -> bool:
        return not self.failed


@dataclass
class ConsensusResult:
    verdicts: list[AgentVerdict] = dc_field(default_factory=list)
    threshold: float = PHI_QUORUM
    verified: int = 0
    total: int = 0
    committed: bool = False

    @property
    def ratio(self) -> float:
        return self.verified / self.total if self.total else 0.0

    def text(self) -> str:
        lines = [
            f"CONSENSUS {'COMMITTED' if self.committed else 'REJECTED'} "
            f"(φ={self.ratio:.4f} vs threshold τ={self.threshold:.4f}; "
            f"{self.verified}/{self.total} obligations verified)"
        ]
        for v in self.verdicts:
            status = "all obligations hold" if v.all_hold else f"failed: {', '.join(v.failed)}"
            lines.append(f"  - {v.agent}: {v.verified}/{v.total} — {status}")
        return "\n".join(lines)


def agent_verify(agent: str, local: IR, proposed: IR) -> AgentVerdict:
    """A single agent independently discharges obligations for the proposal
    relative to its own local schema."""
    obls = obligations(diff(local, proposed))
    failed = sorted(name for name, o in obls.items() if not o["holds"])
    verified = len(obls) - len(failed)
    return AgentVerdict(agent=agent, verified=verified, total=len(obls), failed=failed)


def reach_consensus(
    agents: list[tuple[str, IR]],
    proposed: IR,
    threshold: float = PHI_QUORUM,
) -> ConsensusResult:
    """Tally independently-discharged obligations against the 1/φ quorum."""
    if not agents:
        raise ValueError("consensus requires at least one agent")
    verdicts = [agent_verify(name, local, proposed) for name, local in agents]
    verified = sum(v.verified for v in verdicts)
    total = sum(v.total for v in verdicts)
    ratio = verified / total if total else 0.0
    return ConsensusResult(
        verdicts=verdicts,
        threshold=threshold,
        verified=verified,
        total=total,
        committed=ratio >= threshold,
    )
