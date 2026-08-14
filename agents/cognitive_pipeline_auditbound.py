"""AEGIS-Ω audit-bound cognitive pipeline.

This module recovers the interrupted Copenhagen Work hardening without changing
INT4 LUT-KAN scoring semantics.  Claim wording can request an epistemic tier,
but only a structurally bound external witness can satisfy T0/T1.  The KAN hash
chain proves local scoring-log integrity only; it is never a truth certificate.

Offline execution never fabricates research claims.  Callers must supply claims
explicitly, or run live research through a provider/tool path that returns real
claims.  Provider/model output remains advisory and receives no authority here.
"""
from __future__ import annotations

import asyncio
import re
import uuid
from dataclasses import dataclass, field
from typing import Any

from agents.cognitive_pipeline import (
    ADMISSION_THRESHOLD,
    KanInferenceLog,
    KanScorer,
    constitutional_scorer,
    quantise_claim,
)

_T0_KW = (
    "formally verified",
    "mechanically proven",
    "sha-256",
    "hash chain",
    "byte-identical",
    "deterministic",
)
_T1_KW = (
    "empirically validated",
    "benchmark",
    "measurement",
    "observed across runs",
    "production metric",
)
_T2_KW = (
    "engineering hypothesis",
    "proposed",
    "stub",
    "seam",
    "lut-kan",
    "rwkv-7",
    "plonky3",
    "bls",
    "pbft",
    "zk-snark",
    "bernstein",
    "mersenne",
)
_T45_KW = (
    "planetary",
    "civilizational",
    "sovereign consciousness",
    "omnipotent",
    "subquantum",
    "quantum vacuum",
    "compute bonds",
    "autopoietic closure",
    "metabolic computing",
    "self-improving",
    "unrestricted agi",
)
_SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
_TIER_STRENGTH = {"T0": 0, "T1": 1, "T2": 2, "T3": 3}


class EvidenceBindingError(ValueError):
    pass


@dataclass(frozen=True)
class EvidenceBinding:
    evidence_tier: str
    source: str
    reference: str
    artifact_digest: str

    def validate(self) -> "EvidenceBinding":
        if self.evidence_tier not in _TIER_STRENGTH:
            raise EvidenceBindingError("unsupported evidence tier")
        if not self.source or not self.reference:
            raise EvidenceBindingError("evidence source and reference are required")
        if _SHA256_RE.fullmatch(self.artifact_digest) is None:
            raise EvidenceBindingError("artifact_digest must be lowercase SHA-256 hex")
        return self

    def satisfies(self, requested_tier: str) -> bool:
        self.validate()
        if requested_tier not in _TIER_STRENGTH:
            return False
        return _TIER_STRENGTH[self.evidence_tier] <= _TIER_STRENGTH[requested_tier]


@dataclass
class PipelineResult:
    pipeline_id: str
    topic: str
    arbitration: list[dict[str, Any]] = field(default_factory=list)
    admitted: list[dict[str, Any]] = field(default_factory=list)
    quarantined: list[dict[str, Any]] = field(default_factory=list)
    kan_terminal_hash: str = ""
    chain_valid: bool = True
    stage_results: dict[str, str] = field(default_factory=dict)


def _requested_tier(claim: str) -> tuple[str, str | None]:
    low = claim.lower()
    t45_hit = next((keyword for keyword in _T45_KW if keyword in low), None)
    if t45_hit is not None:
        return "T4/T5", t45_hit
    if any(keyword in low for keyword in _T0_KW):
        return "T0", None
    if any(keyword in low for keyword in _T1_KW):
        return "T1", None
    if any(keyword in low for keyword in _T2_KW):
        return "T2", None
    return "T3", None


def arbitrate(
    claim: str,
    scorer: KanScorer,
    log: KanInferenceLog,
    *,
    evidence: EvidenceBinding | None = None,
) -> dict[str, Any]:
    """Score a claim while keeping epistemic authority external-evidence bound."""
    requested_tier, t45_hit = _requested_tier(claim)
    features = quantise_claim(claim)
    record = log.append_scored(scorer, features)
    score_pass = record.score >= ADMISSION_THRESHOLD

    if requested_tier == "T4/T5":
        effective_tier = "T4/T5"
        admitted = False
        evidence_status = "QUARANTINED"
        reason = f"T4/T5 contamination keyword: '{t45_hit}'"
    elif requested_tier in {"T0", "T1"}:
        if evidence is None or not evidence.satisfies(requested_tier):
            effective_tier = "T3"
            admitted = False
            evidence_status = "UNVERIFIED"
            reason = f"{requested_tier} wording has no sufficient bound external evidence"
        else:
            effective_tier = requested_tier
            admitted = score_pass
            evidence_status = "BOUND"
            reason = f"{requested_tier} external evidence bound; local scoring gate {'passed' if score_pass else 'failed'}"
    elif requested_tier == "T2":
        effective_tier = "T2"
        admitted = score_pass
        evidence_status = "HYPOTHESIS"
        reason = "T2 engineering-hypothesis marker; no truth authority implied"
    else:
        effective_tier = "T3"
        admitted = False
        evidence_status = "UNVERIFIED"
        reason = "no sufficient external evidence; conjecture remains unverified"

    return {
        "claim": claim,
        "features": features,
        "kan_score": record.score,
        "requested_tier": requested_tier,
        "tier": effective_tier,
        "admitted": admitted,
        "evidence_status": evidence_status,
        "evidence_reference": evidence.reference if evidence is not None else None,
        "evidence_digest": evidence.artifact_digest if evidence is not None else None,
        "reason": reason,
        "record_hash": record.record_hash.hex(),
        "sequence": record.sequence,
        "hash_scope": "LOCAL_SCORING_LOG_INTEGRITY_ONLY",
        "hash_proves_claim_truth": False,
    }


async def _research_claims(topic: str, api_key: str) -> list[str]:
    """Run live research with no synthetic success fallback."""
    from agents.tool_runner import run_with_tools

    task = (
        f"You are the DEEP RESEARCHER. Produce 6-10 concrete, falsifiable claims about '{topic}'.\n"
        "Use web_search and fetch_url. Output only a numbered list of claims. "
        "Do not label a claim T0/T1 unless the provider result itself includes a source that can be bound separately."
    )
    result = await run_with_tools(
        role="deep_researcher",
        task=task,
        api_key=api_key,
        namespace=f"research:{topic[:32]}",
        max_tool_rounds=6,
    )
    claims: list[str] = []
    for line in result.output.strip().splitlines():
        cleaned = re.sub(r"^[\d]+[.)]\s*|^[-•*]\s*", "", line.strip()).strip()
        if len(cleaned) > 20:
            claims.append(cleaned)
    return claims[:10]


async def run_pipeline(
    topic: str,
    claims: list[str] | None = None,
    *,
    evidence_by_claim: dict[str, EvidenceBinding] | None = None,
    live: bool = False,
    api_key: str | None = None,
) -> PipelineResult:
    """Run audit-bound research/arbitration without fabricated offline results."""
    result = PipelineResult(pipeline_id=str(uuid.uuid4()), topic=topic)
    scorer = constitutional_scorer()
    log = KanInferenceLog()
    evidence_by_claim = evidence_by_claim or {}

    if claims is None and live:
        if not api_key:
            result.stage_results["deep_researcher"] = "live research unavailable: no provider credential supplied"
            claims = []
        else:
            try:
                claims = await _research_claims(topic, api_key)
                result.stage_results["deep_researcher"] = f"live research returned {len(claims)} candidate claims"
            except Exception as exc:  # fail closed: no synthetic replacement claims
                result.stage_results["deep_researcher"] = f"live research failed closed: {type(exc).__name__}"
                claims = []
    elif claims is None:
        claims = []
        result.stage_results["deep_researcher"] = "offline: no supplied claims; no research result emitted"
    else:
        result.stage_results["deep_researcher"] = f"using {len(claims)} caller-supplied claims"

    for claim in claims:
        verdict = arbitrate(
            claim,
            scorer,
            log,
            evidence=evidence_by_claim.get(claim),
        )
        result.arbitration.append(verdict)
        (result.admitted if verdict["admitted"] else result.quarantined).append(verdict)

    valid, _bad_index = log.verify_chain()
    result.chain_valid = valid
    result.kan_terminal_hash = log.terminal_hash().hex()
    result.stage_results["scoring_integrity"] = "local hash-chain verified" if valid else "local hash-chain invalid"
    return result


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="AEGIS-Ω audit-bound cognitive pipeline")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--claim", action="append", default=[])
    args = parser.parse_args()
    result = asyncio.run(run_pipeline(args.topic, claims=args.claim or None, live=False))
    print({
        "topic": result.topic,
        "admitted": len(result.admitted),
        "quarantined": len(result.quarantined),
        "chain_valid": result.chain_valid,
        "kan_terminal_hash": result.kan_terminal_hash,
        "hash_scope": "LOCAL_SCORING_LOG_INTEGRITY_ONLY",
    })


if __name__ == "__main__":
    main()
