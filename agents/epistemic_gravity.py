"""AEGIS Ω Epistemic Gravity v0.1: a read-only counterfactual verification planner.

This ranks *hypothetical* evidence acquisitions; it cannot issue approvals,
execute probes, certify the truth of claims, or authenticate evidence.
Input evidence status is accepted ONLY as an input-model assumption.
"""
from __future__ import annotations

import argparse
import hashlib
import itertools
import json
from pathlib import Path

MAX_PROBES = 16


def _canonical(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"), allow_nan=False)


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def validate(spec):
    _require(isinstance(spec, dict), "spec must be an object")
    _require(spec.get("schema_version") == "0.1", "schema_version must be 0.1")
    heads, evidence, claims, probes = (spec.get(k) for k in ("heads", "evidence", "claims", "probes"))
    _require(all(isinstance(x, dict) for x in (heads, evidence, claims, probes)), "heads/evidence/claims/probes must be objects")
    _require(all(isinstance(k, str) and isinstance(v, str) and k and v for k, v in heads.items()), "invalid heads")
    _require(len(probes) <= MAX_PROBES, "too many probes: use a bounded slice")
    _require(len(set(evidence) | set(claims)) == len(evidence) + len(claims), "evidence/claim ID collision")
    for eid, rec in evidence.items():
        _require(isinstance(rec, dict) and rec.get("source") in heads, f"{eid}: unknown source")
        _require(isinstance(rec.get("sha"), str) and bool(rec["sha"]), f"{eid}: missing version")
        _require(type(rec.get("verified")) is bool, f"{eid}: verified must be boolean")
    for cid, claim in claims.items():
        _require(isinstance(claim, dict), f"{cid}: invalid claim")
        _require(type(claim.get("value")) is int and claim["value"] > 0, f"{cid}: value must be positive integer")
        choices = claim.get("alternatives")
        _require(isinstance(choices, list) and bool(choices), f"{cid}: empty alternatives")
        for choice in choices:
            _require(isinstance(choice, list) and bool(choice) and len(choice) == len(set(choice)), f"{cid}: empty or duplicate choice")
            _require(all(isinstance(n, str) and n in evidence or isinstance(n, str) and n in claims for n in choice), f"{cid}: missing dependency")
    for pid, probe in probes.items():
        _require(isinstance(probe, dict), f"{pid}: invalid probe")
        _require(probe.get("produces") in evidence, f"{pid}: unknown evidence target")
        _require(type(probe.get("cost")) is int and probe["cost"] > 0, f"{pid}: invalid cost")
    _require(type(spec.get("budget")) is int and spec["budget"] >= 0, "budget must be a nonnegative integer")
    # Prohibit cyclic claims even if another OR path would currently mask them.
    visiting, done = set(), set()
    def walk(cid):
        _require(cid not in visiting, "cyclic claim dependency")
        if cid in done:
            return
        visiting.add(cid)
        for choice in claims[cid]["alternatives"]:
            for dep in choice:
                if dep in claims:
                    walk(dep)
        visiting.remove(cid)
        done.add(cid)
    for cid in claims:
        walk(cid)


def supported(spec, assumed_probes=()):
    """SUPPORTED_FROM_INPUT means dependency satisfaction, NOT scientific truth."""
    heads, evidence, claims, probes = (spec[k] for k in ("heads", "evidence", "claims", "probes"))
    hypothetical = {probes[p]["produces"] for p in assumed_probes}
    memo = {}
    def check(node):
        if node in evidence:
            e = evidence[node]
            return node in hypothetical or (e["verified"] and e["sha"] == heads[e["source"]])
        if node not in memo:
            memo[node] = any(all(check(dep) for dep in path) for path in claims[node]["alternatives"])
        return memo[node]
    return frozenset(cid for cid in sorted(claims) if check(cid))


def plan(spec):
    """Exact subset optimization for <=16 candidate probes; no side effects.

    Choose the affordable hypothetical success subset unlocking maximal declared
    claim value. Cost and lexicographic order break ties. proof_debt is the
    cheapest unrestricted candidate subset that would support each open claim.
    All returned gains are *conditional on future successful independent checks*.
    """
    validate(spec)
    baseline = supported(spec)
    names = sorted(spec["probes"])
    costs = {name: spec["probes"][name]["cost"] for name in names}
    weights = {name: rec["value"] for name, rec in spec["claims"].items()}
    best = (0, 0, ())  # gain, cost, chosen probes
    best_key = (0, 0, ())
    minimal_debt = {name: None for name in sorted(set(weights) - baseline)}
    for n in range(len(names) + 1):
        for subset in itertools.combinations(names, n):
            cost = sum(costs[p] for p in subset)
            newly = supported(spec, subset) - baseline
            for cid in newly:
                old = minimal_debt[cid]
                new = {"cost": cost, "probes": list(subset)}
                if old is None or (cost, list(subset)) < (old["cost"], old["probes"]):
                    minimal_debt[cid] = new
            if cost <= spec["budget"]:
                gain = sum(weights[c] for c in newly)
                # No hardcoded weights. Entire objective from the supplied graph.
                key = (-gain, cost, subset)
                if n == 0 or key < best_key:
                    best_key = key
                    best = (gain, cost, subset)
    gain, cost, chosen = best
    unlocked = sorted(supported(spec, chosen) - baseline)
    receipt = {
        "schema_version": "0.1",
        "engine": "AEGIS_EPISTEMIC_GRAVITY_COUNTERFACTUAL_V1",
        "authority_effect": "NONE",
        "decision": "PROPOSE_ONLY" if chosen else "NO_BENEFICIAL_PROPOSAL",
        "evidence_verification": "NOT_PERFORMED_INPUT_ASSUMPTIONS_ONLY",
        "execution": "NOT_PERFORMED",
        "assumption": "ALL_CHOSEN_PROBES_SUCCEED_AFTER_INDEPENDENT_VERIFICATION",
        "source_snapshot_digest": hashlib.sha256(_canonical(spec).encode()).hexdigest(),
        "baseline_supported_from_input": sorted(baseline),
        "proposed_probes": list(chosen),
        "hypothetical_newly_supported": unlocked,
        "hypothetical_unlocked_value": gain,
        "hypothetical_cost_units": cost,
        "budget_units": spec["budget"],
        "minimal_proof_debt": minimal_debt,
    }
    receipt["receipt_digest"] = hashlib.sha256(_canonical(receipt).encode()).hexdigest()
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("spec", type=Path, help="JSON snapshot with claims/evidence/source heads/probes")
    args = parser.parse_args()
    print(json.dumps(plan(json.loads(args.spec.read_text(encoding="utf-8"))), ensure_ascii=False, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
