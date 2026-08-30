"""
AEGIS-Ω Agent Evolution — Hash-Chained Adaptive Lineage
=======================================================
The evolutionary metabolism of the automaton's agent system.

Skills are not fixed at their birth tier. They earn promotion through accumulated,
hash-chained evidence — exactly as CLAUDE.md §"Tier Promotion Protocol" specifies:

    T2 → T1   ≥3 independent validations (failure_rate < 0.1)   → TIER_PROMOTION entry
    T1 → T0   formal proof OR byte-identical cross-platform demo → TIER_PROMOTION + guardian
    Any → lower   new evidence invalidates the prior basis        → TIER_PROMOTION (demotion)

This module is the replay-certifiable substrate for that evolution. Every event is
a SHA-256 hash-linked entry in an AdaptiveLineage chain:

    entry_hash = SHA-256(prev_hash ‖ sequence ‖ canonical(event))   genesis = '0'*64

The chain satisfies the root law: AdaptivePower(T) ≤ ReplayVerifiability(T). No skill
is promoted faster than the chain can account for the promotion. `verify_chain()`
re-walks every entry; tampering any event flips it invalid. The evolution is therefore
earned, tamper-evident, and reconstructable from genesis — not asserted.

T1 → T0 promotions are NEVER automatic. They require a guardian-approved formal-proof
or cross-platform-determinism flag. The engine records the eligibility but will not
self-grant a T0 promotion (no autonomous mutation authority — a constitutional T0_ABORT).

Usage:
    python -m agents.evolution evolve     # run one evolution tick over the skill tree
    python -m agents.evolution status     # show current tiers + promotion eligibility
    python -m agents.evolution verify     # re-walk the lineage chain, assert integrity
    python -m agents.evolution selftest    # run the embedded test ring (no pytest needed)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

_ROOT = os.path.dirname(os.path.abspath(__file__))
_REPO_ROOT = os.path.dirname(_ROOT)
SKILL_TREE_PATH = os.path.join(_REPO_ROOT, "harness", "skill_tree.json")
LINEAGE_PATH = Path(_ROOT) / "adaptive_lineage.json"

EVOLUTION_GENESIS_HASH = "0" * 64

# Tier ordering — lower index = higher certainty.
TIER_ORDER = ["T0", "T1", "T2", "T3", "T4", "T5"]

# T2→T1 promotion criteria (CLAUDE.md): ≥3 independent validations, low failure rate.
PROMOTION_MIN_RUNS = 3
PROMOTION_MAX_FAILURE_RATE = 0.1
PROMOTION_MIN_CONFIDENCE = 0.9  # T1 candidates must have earned high confidence


# ── Canonicalization (deterministic, sorted — mirrors EventEnvelope) ───────────

def _canonical(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


# ── Lineage event ──────────────────────────────────────────────────────────────

@dataclass
class LineageEvent:
    """One hash-linked evolution event."""
    sequence: int
    event_type: str        # CAPABILITY_EVOLUTION | TIER_PROMOTION | TIER_DEMOTION | EVIDENCE_RECORDED
    skill_id: str
    from_tier: str
    to_tier: str
    evidence: str
    timestamp_ms: int
    entry_hash: str = ""
    prev_hash: str = ""

    def payload(self) -> dict[str, Any]:
        """The canonical, hash-bound fields (excludes the hashes themselves)."""
        return {
            "sequence": self.sequence,
            "event_type": self.event_type,
            "skill_id": self.skill_id,
            "from_tier": self.from_tier,
            "to_tier": self.to_tier,
            "evidence": self.evidence,
            "timestamp_ms": self.timestamp_ms,
        }


def _compute_entry_hash(prev_hash: str, sequence: int, payload: dict[str, Any]) -> str:
    h = hashlib.sha256()
    h.update(prev_hash.encode("utf-8"))
    h.update(str(sequence).encode("utf-8"))
    h.update(_canonical(payload).encode("utf-8"))
    return h.hexdigest()


# ── Adaptive lineage chain ─────────────────────────────────────────────────────

class AdaptiveLineage:
    """Append-only, hash-chained record of agent-system evolution."""

    def __init__(self, events: list[LineageEvent] | None = None):
        self.events: list[LineageEvent] = events or []

    def terminal_hash(self) -> str:
        return self.events[-1].entry_hash if self.events else EVOLUTION_GENESIS_HASH

    def append(self, event_type: str, skill_id: str, from_tier: str,
               to_tier: str, evidence: str, timestamp_ms: int | None = None) -> LineageEvent:
        prev = self.terminal_hash()
        seq = len(self.events)
        ts = timestamp_ms if timestamp_ms is not None else int(time.time() * 1000)
        ev = LineageEvent(
            sequence=seq, event_type=event_type, skill_id=skill_id,
            from_tier=from_tier, to_tier=to_tier, evidence=evidence,
            timestamp_ms=ts, prev_hash=prev,
        )
        ev.entry_hash = _compute_entry_hash(prev, seq, ev.payload())
        self.events.append(ev)
        return ev

    def verify_chain(self) -> tuple[bool, int | None]:
        """Re-walk the chain. (True, None) if intact, else (False, first_bad_index)."""
        prev = EVOLUTION_GENESIS_HASH
        for i, ev in enumerate(self.events):
            if ev.prev_hash != prev or ev.sequence != i:
                return (False, i)
            if ev.entry_hash != _compute_entry_hash(prev, ev.sequence, ev.payload()):
                return (False, i)
            prev = ev.entry_hash
        return (True, None)

    # ── Persistence ────────────────────────────────────────────────────────────

    @classmethod
    def load(cls, path: Path = LINEAGE_PATH) -> "AdaptiveLineage":
        if path.exists():
            with open(path) as f:
                raw = json.load(f)
            events = [LineageEvent(**e) for e in raw.get("events", [])]
            return cls(events)
        return cls()

    def save(self, path: Path = LINEAGE_PATH) -> None:
        with open(path, "w") as f:
            json.dump(
                {
                    "genesis_hash": EVOLUTION_GENESIS_HASH,
                    "terminal_hash": self.terminal_hash(),
                    "event_count": len(self.events),
                    "events": [asdict(e) for e in self.events],
                },
                f,
                indent=2,
            )


# ── Evolution engine ───────────────────────────────────────────────────────────

@dataclass
class PromotionVerdict:
    skill_id: str
    current_tier: str
    eligible_tier: str | None
    promoted: bool
    reason: str
    requires_guardian: bool = False


class EvolutionEngine:
    """
    Evaluates the skill tree for tier promotions and records them in the lineage.

    Promotion is evidence-driven, not asserted:
      - T2 → T1: automatic when ≥3 validated_runs, failure_rate < 0.1, confidence ≥ 0.9.
      - T1 → T0: NEVER automatic. Recorded as guardian-required; not self-granted.
      - Demotion: when failure_rate ≥ 0.5 after ≥3 runs, the prior tier basis is
        invalidated → demote one tier (new evidence invalidates the prior basis).
    """

    def __init__(self, tree_path: str = SKILL_TREE_PATH, lineage: AdaptiveLineage | None = None):
        self.tree_path = tree_path
        self.lineage = lineage if lineage is not None else AdaptiveLineage.load()
        self._tree: dict | None = None

    def _load_tree(self) -> dict:
        if self._tree is None:
            with open(self.tree_path) as f:
                self._tree = json.load(f)
        return self._tree

    def _save_tree(self) -> None:
        if self._tree is not None:
            with open(self.tree_path, "w") as f:
                json.dump(self._tree, f, indent=2)

    @staticmethod
    def _lower_tier(tier: str) -> str:
        idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else len(TIER_ORDER) - 1
        return TIER_ORDER[min(idx + 1, len(TIER_ORDER) - 1)]

    @staticmethod
    def _higher_tier(tier: str) -> str:
        idx = TIER_ORDER.index(tier) if tier in TIER_ORDER else 0
        return TIER_ORDER[max(idx - 1, 0)]

    def evaluate_skill(self, skill: dict) -> PromotionVerdict:
        sid = skill["skill_id"]
        tier = skill.get("tier", "T2")
        runs = skill.get("validated_runs", 0)
        fail = skill.get("failure_rate", 0.0)
        conf = skill.get("confidence", 0.5)

        # Demotion check first — new failing evidence invalidates the prior basis.
        if runs >= PROMOTION_MIN_RUNS and fail >= 0.5:
            return PromotionVerdict(
                sid, tier, self._lower_tier(tier), False,
                f"failure_rate={fail:.2f} ≥ 0.5 over {runs} runs — prior tier basis invalidated",
            )

        # T1 → T0 is never automatic (no autonomous mutation authority).
        if tier == "T1":
            if runs >= PROMOTION_MIN_RUNS and fail < PROMOTION_MAX_FAILURE_RATE and conf >= 0.95:
                return PromotionVerdict(
                    sid, tier, "T0", False,
                    f"T1→T0 eligible ({runs} runs, fail={fail:.2f}) — requires /guardian APPROVED formal proof",
                    requires_guardian=True,
                )
            return PromotionVerdict(sid, tier, None, False, "T1 stable — no promotion criteria met")

        # T2 → T1 — automatic when the evidence threshold is crossed.
        if tier == "T2":
            if (runs >= PROMOTION_MIN_RUNS and fail < PROMOTION_MAX_FAILURE_RATE
                    and conf >= PROMOTION_MIN_CONFIDENCE):
                return PromotionVerdict(
                    sid, tier, "T1", True,
                    f"T2→T1: {runs} validations, failure_rate={fail:.2f}, confidence={conf:.2f}",
                )
            return PromotionVerdict(
                sid, tier, None, False,
                f"T2 not yet eligible (runs={runs}/{PROMOTION_MIN_RUNS}, fail={fail:.2f}, conf={conf:.2f})",
            )

        # T3+ require corpus re-arbitration, not run-count evolution.
        return PromotionVerdict(sid, tier, None, False, f"{tier} evolves via corpus re-arbitration, not run count")

    def tick(self, apply_changes: bool = True) -> list[PromotionVerdict]:
        """Run one evolution tick across all skills. Records lineage events."""
        tree = self._load_tree()
        verdicts: list[PromotionVerdict] = []

        for skill in tree.get("skills", []):
            v = self.evaluate_skill(skill)
            verdicts.append(v)

            if v.promoted and apply_changes:
                # Earned T2→T1 promotion — record and apply.
                self.lineage.append(
                    "TIER_PROMOTION", v.skill_id, v.current_tier, v.eligible_tier or v.current_tier, v.reason,
                )
                skill["tier"] = v.eligible_tier
            elif v.eligible_tier and self._is_demotion(v) and apply_changes:
                self.lineage.append(
                    "TIER_DEMOTION", v.skill_id, v.current_tier, v.eligible_tier, v.reason,
                )
                skill["tier"] = v.eligible_tier
            elif v.requires_guardian and apply_changes:
                # Record eligibility WITHOUT promoting (no self-grant of T0).
                self.lineage.append(
                    "EVIDENCE_RECORDED", v.skill_id, v.current_tier, v.eligible_tier or v.current_tier,
                    f"T0-eligible, guardian gate not yet satisfied: {v.reason}",
                )

        if apply_changes:
            self.lineage.save()
            self._save_tree()
        return verdicts

    @staticmethod
    def _is_demotion(v: PromotionVerdict) -> bool:
        if not v.eligible_tier:
            return False
        cur = TIER_ORDER.index(v.current_tier) if v.current_tier in TIER_ORDER else 0
        elig = TIER_ORDER.index(v.eligible_tier) if v.eligible_tier in TIER_ORDER else 0
        return elig > cur


# ── CLI ─────────────────────────────────────────────────────────────────────────

def _cmd_evolve() -> int:
    engine = EvolutionEngine()
    verdicts = engine.tick(apply_changes=True)
    promoted = [v for v in verdicts if v.promoted]
    demoted = [v for v in verdicts if engine._is_demotion(v) and not v.promoted]
    guardian = [v for v in verdicts if v.requires_guardian]

    print("AEGIS Agent Evolution — one tick")
    print("=" * 60)
    print(f"  Skills evaluated:   {len(verdicts)}")
    print(f"  Promoted (T2→T1):   {len(promoted)}")
    print(f"  Demoted:            {len(demoted)}")
    print(f"  T0-eligible (guardian-gated): {len(guardian)}")
    for v in promoted:
        print(f"    ↑ {v.skill_id}: {v.current_tier}→{v.eligible_tier} — {v.reason}")
    for v in demoted:
        print(f"    ↓ {v.skill_id}: {v.current_tier}→{v.eligible_tier} — {v.reason}")
    for v in guardian:
        print(f"    ⊘ {v.skill_id}: {v.current_tier}→{v.eligible_tier} BLOCKED — needs /guardian APPROVED")
    valid, bad = engine.lineage.verify_chain()
    print(f"\n  Lineage chain valid: {valid}  (events={len(engine.lineage.events)})")
    print(f"  Terminal hash: {engine.lineage.terminal_hash()[:32]}…")
    return 0 if valid else 1


def _cmd_status() -> int:
    engine = EvolutionEngine()
    verdicts = engine.tick(apply_changes=False)
    by_tier: dict[str, int] = {}
    for v in verdicts:
        by_tier[v.current_tier] = by_tier.get(v.current_tier, 0) + 1
    print("AEGIS Skill Tier Distribution")
    print("=" * 60)
    for tier in TIER_ORDER:
        if tier in by_tier:
            print(f"  {tier}: {by_tier[tier]} skills")
    eligible = [v for v in verdicts if v.promoted or v.requires_guardian]
    print(f"\n  Promotion-eligible: {len(eligible)}")
    for v in eligible:
        gate = " (guardian-gated)" if v.requires_guardian else ""
        print(f"    {v.skill_id}: {v.current_tier}→{v.eligible_tier}{gate}")
    return 0


def _cmd_verify() -> int:
    lineage = AdaptiveLineage.load()
    valid, bad = lineage.verify_chain()
    print(f"AdaptiveLineage: {len(lineage.events)} events")
    print(f"  Genesis:  {EVOLUTION_GENESIS_HASH[:32]}…")
    print(f"  Terminal: {lineage.terminal_hash()[:32]}…")
    print(f"  Chain valid: {valid}" + (f" (broken at {bad})" if not valid else ""))
    return 0 if valid else 1


def _cmd_selftest() -> int:
    """Embedded test ring — no pytest dependency."""
    failures = 0

    def check(name: str, cond: bool) -> None:
        nonlocal failures
        status = "ok" if cond else "FAIL"
        if not cond:
            failures += 1
        print(f"  [{status}] {name}")

    # 1 — empty lineage is genesis and verifies
    lin = AdaptiveLineage()
    check("empty lineage terminal == genesis", lin.terminal_hash() == EVOLUTION_GENESIS_HASH)
    check("empty lineage verifies", lin.verify_chain() == (True, None))

    # 2 — append links and verifies
    lin.append("TIER_PROMOTION", "skill_a", "T2", "T1", "3 validations", timestamp_ms=1000)
    lin.append("TIER_PROMOTION", "skill_b", "T2", "T1", "3 validations", timestamp_ms=2000)
    check("two events verify", lin.verify_chain() == (True, None))
    check("event 1 links to event 0", lin.events[1].prev_hash == lin.events[0].entry_hash)
    check("terminal != genesis after append", lin.terminal_hash() != EVOLUTION_GENESIS_HASH)

    # 3 — determinism: same inputs → same hash
    lin2 = AdaptiveLineage()
    lin2.append("TIER_PROMOTION", "skill_a", "T2", "T1", "3 validations", timestamp_ms=1000)
    check("deterministic entry_hash across instances",
          lin2.events[0].entry_hash == lin.events[0].entry_hash)

    # 4 — tamper detection: mutate evidence
    lin.events[0].evidence = "TAMPERED"
    check("tampered evidence detected", lin.verify_chain() == (False, 0))
    lin.events[0].evidence = "3 validations"  # restore
    check("restored chain re-verifies", lin.verify_chain() == (True, None))

    # 5 — tamper detection: mutate prev_hash link
    lin.events[1].prev_hash = "f" * 64
    check("tampered prev_hash detected", lin.verify_chain() == (False, 1))

    # 6 — promotion engine: T2 with enough evidence promotes
    engine = EvolutionEngine.__new__(EvolutionEngine)
    engine.tree_path = SKILL_TREE_PATH
    engine.lineage = AdaptiveLineage()
    engine._tree = None
    v = engine.evaluate_skill(
        {"skill_id": "x", "tier": "T2", "validated_runs": 5, "failure_rate": 0.0, "confidence": 0.92}
    )
    check("T2 with 5 clean runs is promotion-eligible", v.promoted and v.eligible_tier == "T1")

    # 7 — T2 with insufficient runs does not promote
    v = engine.evaluate_skill(
        {"skill_id": "y", "tier": "T2", "validated_runs": 2, "failure_rate": 0.0, "confidence": 0.92}
    )
    check("T2 with 2 runs not promoted", not v.promoted)

    # 8 — T1→T0 is guardian-gated, never auto-promoted
    v = engine.evaluate_skill(
        {"skill_id": "z", "tier": "T1", "validated_runs": 9, "failure_rate": 0.0, "confidence": 0.99}
    )
    check("T1→T0 requires guardian, not auto-promoted", v.requires_guardian and not v.promoted)

    # 9 — high failure rate demotes
    v = engine.evaluate_skill(
        {"skill_id": "w", "tier": "T1", "validated_runs": 4, "failure_rate": 0.6, "confidence": 0.8}
    )
    check("high failure_rate triggers demotion", engine._is_demotion(v) and v.eligible_tier == "T2")

    print(f"\n  {'ALL PASS' if failures == 0 else f'{failures} FAILED'}")
    return 1 if failures else 0


def main() -> None:
    parser = argparse.ArgumentParser(description="AEGIS Agent Evolution — hash-chained tier promotion")
    sub = parser.add_subparsers(dest="command")
    sub.add_parser("evolve", help="Run one evolution tick (applies promotions)")
    sub.add_parser("status", help="Show tier distribution + promotion eligibility")
    sub.add_parser("verify", help="Re-walk the lineage chain and assert integrity")
    sub.add_parser("selftest", help="Run the embedded test ring")
    args = parser.parse_args()

    if args.command == "evolve":
        sys.exit(_cmd_evolve())
    elif args.command == "status":
        sys.exit(_cmd_status())
    elif args.command == "verify":
        sys.exit(_cmd_verify())
    elif args.command == "selftest":
        sys.exit(_cmd_selftest())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
