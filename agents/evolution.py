"""
AEGIS-Ω Agent Evolution — Hash-Chained Adaptive Lineage
=======================================================
The evolutionary metabolism of the automaton's agent system.

Skills are not fixed at their birth tier. They may earn promotion through accumulated,
hash-chained evidence — exactly as CLAUDE.md §"Tier Promotion Protocol" specifies:

    T2 → T1   ≥3 independent validations AND verified provenance → eligible; HOLD pending trusted admission
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
import math
import os
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from harness.sdk.skill_authority import compute_registry_root, evaluate_registry

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


def _demotion_evidence_fingerprint(skill: dict) -> str:
    """Stable observation identity, independent of the mutable current tier.

    Equal evidence on repeated ticks must never trigger successive demotions.
    This hash only detects replay; it does NOT authenticate the observations.
    """
    fields = {
        "domain": "AEGIS_DEMOTION_OBSERVATION_V1",
        "skill_id": skill.get("skill_id"),
        "observation_state": skill.get("observation_state"),
        "validated_runs": skill.get("validated_runs"),
        "failure_rate": skill.get("failure_rate"),
        "failure_rate_observed": skill.get("failure_rate_observed"),
        "confidence": skill.get("confidence"),
        "recency_score": skill.get("recency_score"),
        "last_validated": skill.get("last_validated"),
        "evidence_refs": skill.get("evidence_refs"),
    }
    return hashlib.sha256(
        json.dumps(fields, sort_keys=True, separators=(",", ":"), allow_nan=False).encode("utf-8")
    ).hexdigest()


def _coherent_observation(skill: dict) -> bool:
    """Metadata coherence check, NOT independent attestation.

    Even well-formed OBSERVED fields and content-addressed references can be
    self-authored. They may support a provisional numerical eligibility
    result, but must never authorize a T2 -> T1 promotion by themselves.
    """
    if skill.get("observation_state") != "OBSERVED":
        return False
    runs = skill.get("validated_runs")
    if type(runs) is not int or runs < 1:
        return False
    for key in ("failure_rate", "confidence", "recency_score", "failure_rate_observed"):
        v = skill.get(key)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return False
        if not math.isfinite(v) or not 0.0 <= v <= 1.0:
            return False
    if not math.isclose(skill["failure_rate"], skill["failure_rate_observed"], abs_tol=1e-12, rel_tol=0.0):
        return False
    last = skill.get("last_validated")
    if not isinstance(last, str) or not last.strip():
        return False
    refs = skill.get("evidence_refs")
    return isinstance(refs, list) and bool(refs) and all(isinstance(x, str) and x.strip() for x in refs)


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
            if not isinstance(raw, dict) or raw.get("genesis_hash") != EVOLUTION_GENESIS_HASH:
                raise ValueError("lineage genesis metadata invalid")
            events = [LineageEvent(**e) for e in raw.get("events", [])]
            lineage = cls(events)
            if (raw.get("event_count") != len(events) or
                    raw.get("terminal_hash") != lineage.terminal_hash() or
                    not lineage.verify_chain()[0]):
                raise ValueError("lineage metadata or chain integrity invalid")
            return lineage
        return cls()

    def save(self, path: Path = LINEAGE_PATH) -> None:
        if not self.verify_chain()[0]:
            raise ValueError("refusing to persist invalid lineage")
        temporary = path.with_suffix(path.suffix + ".tmp")
        with open(temporary, "w", encoding="utf-8") as f:
            json.dump(
                {
                    "genesis_hash": EVOLUTION_GENESIS_HASH,
                    "terminal_hash": self.terminal_hash(),
                    "event_count": len(self.events),
                    "events": [asdict(e) for e in self.events],
                }, f, indent=2,
            )
            f.write("\n")
        os.replace(temporary, path)


# ── Evolution engine ───────────────────────────────────────────────────────────

@dataclass
class PromotionVerdict:
    skill_id: str
    current_tier: str
    eligible_tier: str | None
    promoted: bool
    reason: str
    requires_guardian: bool = False
    requires_evidence: bool = False


class EvolutionEngine:
    """
    Evaluates the skill tree for tier promotions and records them in the lineage.

    Promotion is evidence-driven, not asserted:
      - T2 → T1: numerical eligibility only; independent proof admission remains a HOLD.
      - T1 → T0: NEVER automatic. Recorded as guardian-required; not self-granted.
      - Demotion: when failure_rate ≥ 0.5 after ≥3 runs, the prior tier basis is
        invalidated → demote one tier (new evidence invalidates the prior basis).
    """

    def __init__(self, tree_path: str = SKILL_TREE_PATH, lineage: AdaptiveLineage | None = None,
                 repo_root: str | Path | None = None):
        self.tree_path = tree_path
        self.repo_root = Path(repo_root).resolve() if repo_root is not None else Path(_REPO_ROOT).resolve()
        self.lineage = lineage if lineage is not None else AdaptiveLineage.load()
        self._tree: dict | None = None

    def _load_tree(self) -> dict:
        if self._tree is None:
            with open(self.tree_path) as f:
                self._tree = json.load(f)
        return self._tree

    def _save_tree(self) -> None:
        if self._tree is not None:
            root = compute_registry_root(self._tree)
            self._tree["registry_root"] = root
            self._tree["genesis_seal"] = root
            receipt = evaluate_registry(self._tree, repo_root=self.repo_root)
            if receipt.outcome != "ADMITTED":
                raise ValueError("refusing to write invalid evolved skill registry")
            tree_path = Path(self.tree_path)
            temporary = tree_path.with_suffix(tree_path.suffix + ".tmp")
            temporary.write_text(json.dumps(self._tree, indent=2) + "\n", encoding="utf-8")
            os.replace(temporary, tree_path)

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

        # Fail closed on forged or malformed observation metadata.
        if not _coherent_observation(skill):
            return PromotionVerdict(
                sid, tier, None, False,
                "HOLD: no coherent OBSERVED evidence metadata (not independent attestation)",
            )

        # Demotion is authority-reducing, but still requires admitted registry
        # and verified lineage at tick() before persistence.
        if runs >= PROMOTION_MIN_RUNS and fail >= 0.5:
            return PromotionVerdict(
                sid, tier, self._lower_tier(tier), False,
                f"failure_rate={fail:.2f} >= 0.5 over {runs} observed runs",
            )

        # T1 -> T0 remains guardian-gated with no self-grant.
        if tier == "T1":
            if runs >= PROMOTION_MIN_RUNS and fail < PROMOTION_MAX_FAILURE_RATE and conf >= 0.95:
                return PromotionVerdict(
                    sid, tier, "T0", False,
                    "T0-eligible only; requires guardian-approved formal proof",
                    requires_guardian=True,
                )
            return PromotionVerdict(sid, tier, None, False, "T1 stable")

        if tier == "T2":
            if (runs >= PROMOTION_MIN_RUNS and fail < PROMOTION_MAX_FAILURE_RATE
                    and conf >= PROMOTION_MIN_CONFIDENCE):
                # Self-reported OBSERVED fields, evidence_refs, and SHA-256
                # registry roots are integrity checks, not signatures. Never
                # make an automatic tier mutation without an independently
                # authenticated, replayable admission receipt.
                return PromotionVerdict(
                    sid, tier, "T1", False,
                    f"numerically eligible ({runs} runs, fail={fail:.2f}, conf={conf:.2f}); "
                    "HOLD: independently authenticated promotion evidence absent",
                    requires_evidence=True,
                )
            return PromotionVerdict(
                sid, tier, None, False,
                f"T2 not yet eligible (runs={runs}/{PROMOTION_MIN_RUNS}, fail={fail:.2f}, conf={conf:.2f})",
            )

        return PromotionVerdict(sid, tier, None, False, f"{tier} requires corpus re-arbitration")

    def tick(self, apply_changes: bool = True) -> list[PromotionVerdict]:
        """Evaluate existing skills; fail closed before any durable state change."""
        tree = self._load_tree()
        admitted = evaluate_registry(tree, repo_root=self.repo_root)
        if admitted.outcome != "ADMITTED":
            raise ValueError("skill registry not admitted: " + "; ".join(admitted.violations))
        valid, bad = self.lineage.verify_chain()
        if not valid:
            raise ValueError(f"adaptive lineage invalid at event {bad}")

        verdicts: list[PromotionVerdict] = []
        changed = False
        for skill in tree.get("skills", []):
            v = self.evaluate_skill(skill)
            verdicts.append(v)
            if not apply_changes:
                continue
            if v.promoted:
                # Defense-in-depth: evaluate_skill must not self-grant T2 -> T1.
                raise ValueError("unexpected unauthenticated automatic promotion")
            if v.eligible_tier and self._is_demotion(v):
                fingerprint = _demotion_evidence_fingerprint(skill)
                witness = "obs=" + fingerprint
                if any(
                    ev.event_type == "TIER_DEMOTION" and ev.skill_id == v.skill_id
                    and ev.evidence.endswith(witness)
                    for ev in self.lineage.events
                ):
                    # Identical observation evidence cannot repeatedly demote.
                    continue
                self.lineage.append(
                    "TIER_DEMOTION", v.skill_id, v.current_tier, v.eligible_tier,
                    v.reason + "; " + witness,
                )
                skill["tier"] = v.eligible_tier
                changed = True
            # A provisional T2 or T0 eligibility is read-only: repeated ticks
            # must not invent validation receipts or multiply lineage events.

        if apply_changes and changed:
            # Persist the evidence chain before the authority-bearing registry.
            # Cross-file crash consistency still needs a future transaction
            # journal; never promote without independent admission.
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
    held = [v for v in verdicts if v.requires_evidence]
    demoted = [v for v in verdicts if engine._is_demotion(v) and not v.promoted]
    guardian = [v for v in verdicts if v.requires_guardian]

    print("AEGIS Agent Evolution — one tick")
    print("=" * 60)
    print(f"  Skills evaluated:   {len(verdicts)}")
    print(f"  Promoted (T2→T1):   {len(promoted)}")
    print(f"  Evidence-held:      {len(held)}")
    print(f"  Demoted:            {len(demoted)}")
    print(f"  T0-eligible (guardian-gated): {len(guardian)}")
    for v in promoted:
        print(f"    ↑ {v.skill_id}: {v.current_tier}→{v.eligible_tier} — {v.reason}")
    for v in held:
        print(f"    HOLD {v.skill_id}: {v.reason}")
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
    eligible = [v for v in verdicts if v.promoted or v.requires_guardian or v.requires_evidence]
    print(f"\n  Promotion-eligible: {len(eligible)}")
    for v in eligible:
        gate = " (guardian-gated)" if v.requires_guardian else (" (evidence-held)" if v.requires_evidence else "")
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
        {"skill_id": "x", "tier": "T2", "validated_runs": 5, "failure_rate": 0.0, "failure_rate_observed": 0.0, "confidence": 0.92, "recency_score": 0.95, "last_validated": "2026-11-16T00:00:00Z", "observation_state": "OBSERVED", "evidence_refs": ["CLAUDE.md"]}
    )
    check("T2 numerical eligibility is held for independent evidence",
          v.requires_evidence and not v.promoted and v.eligible_tier == "T1")

    # 7 — T2 with insufficient runs does not promote
    v = engine.evaluate_skill(
        {"skill_id": "y", "tier": "T2", "validated_runs": 2, "failure_rate": 0.0, "confidence": 0.92}
    )
    check("T2 with 2 runs not promoted", not v.promoted)

    # 8 — T1→T0 is guardian-gated, never auto-promoted
    v = engine.evaluate_skill(
        {"skill_id": "z", "tier": "T1", "validated_runs": 9, "failure_rate": 0.0, "failure_rate_observed": 0.0, "confidence": 0.99, "recency_score": 1.0, "last_validated": "2026-11-16T00:00:00Z", "observation_state": "OBSERVED", "evidence_refs": ["CLAUDE.md"]}
    )
    check("T1→T0 requires guardian, not auto-promoted", v.requires_guardian and not v.promoted)

    # 9 — high failure rate demotes
    v = engine.evaluate_skill(
        {"skill_id": "w", "tier": "T1", "validated_runs": 4, "failure_rate": 0.6, "failure_rate_observed": 0.6, "confidence": 0.8, "recency_score": 1.0, "last_validated": "2026-11-16T00:00:00Z", "observation_state": "OBSERVED", "evidence_refs": ["CLAUDE.md"]}
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
