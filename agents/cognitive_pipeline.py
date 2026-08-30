"""
AEGIS-Ω Mythos Cognitive Pipeline
==================================
Orchestrates the four Mythos-level cognitive-substrate agents into one
constitutionally-governed knowledge pipeline:

    deep-research → corpus-ingestion → batch → chronology

Each stage is a tier-0 (Mythos-level) agent. The corpus-ingestion ARBITRATION
gate scores every candidate claim with the INT4 LUT-KAN scorer — a faithful
Python port of `aegis-cl-psi::int4_lut_kan` — and hash-chains the decision into a
KanInferenceLog. The whole pipeline is replay-certifiable:

    AdaptivePower(T) ≤ ReplayVerifiability(T)

The INT4 LUT-KAN port here is byte-for-byte aligned with the Rust reference
(big-endian hashing, power-of-two rescale, saturating i32 arithmetic, 16-entry
LUTs). Determinism is the point: the same claim scores identically in Rust and
Python, so the admission decision is reproducible across the whole substrate.

Usage:
    python -m agents.cognitive_pipeline run --topic "INT4 LUT-KAN viability"
    python -m agents.cognitive_pipeline score --claim "deterministic SHA-256 hash chain"
    python -m agents.cognitive_pipeline demo
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import struct
import uuid
from dataclasses import dataclass, field
from typing import Any

# ── INT4 LUT-KAN — Python port (mirrors aegis-cl-psi/src/int4_lut_kan.rs) ──────

LUT_SIZE = 16
KAN_GENESIS_HASH = b"\x00" * 32
_I32_MAX = (1 << 31) - 1
_I32_MIN = -(1 << 31)


def _sat_i32(v: int) -> int:
    """Saturating clamp to i32 range (mirrors Rust saturating_add semantics)."""
    if v > _I32_MAX:
        return _I32_MAX
    if v < _I32_MIN:
        return _I32_MIN
    return v


def _to_be_i32(v: int) -> bytes:
    """Big-endian 4-byte two's-complement, matching Rust i32::to_be_bytes()."""
    return struct.pack(">i", _sat_i32(v))


def lut_activation(input_val: int, table: list[int]) -> int:
    """INT4 LUT activation: clamp to [0,15], return table entry. O(1), no float."""
    idx = max(0, min(input_val, LUT_SIZE - 1))
    return table[idx]


def quantize_int4(value: int, shift: int) -> int:
    """Fixed-point value → 4-bit index via arithmetic right-shift then clamp."""
    return max(0, min(value >> shift, LUT_SIZE - 1))


@dataclass
class KanLayer:
    n_in: int
    n_out: int
    edges: list[list[int]]  # length n_out * n_in, row-major by output node
    rescale_shift: int = 0

    def forward(self, inputs: list[int]) -> list[int]:
        if len(inputs) != self.n_in:
            raise ValueError("input length must equal n_in")
        out: list[int] = []
        for o in range(self.n_out):
            base = o * self.n_in
            acc = 0
            for i, x in enumerate(inputs):
                acc = _sat_i32(acc + lut_activation(x, self.edges[base + i]))
            out.append(acc >> self.rescale_shift)
        return out


@dataclass
class KanScorer:
    inner: KanLayer
    outer: KanLayer

    def score(self, inputs: list[int]) -> int:
        hidden = self.inner.forward(inputs)
        hidden_q = [quantize_int4(v, 0) for v in hidden]
        return self.outer.forward(hidden_q)[0]


def fingerprint_inputs(inputs: list[int]) -> bytes:
    h = hashlib.sha256()
    h.update(struct.pack(">Q", len(inputs)))
    for x in inputs:
        h.update(_to_be_i32(x))
    return h.digest()


def _compute_record_hash(prev: bytes, sequence: int, fingerprint: bytes, score: int) -> bytes:
    h = hashlib.sha256()
    h.update(prev)
    h.update(struct.pack(">Q", sequence))
    h.update(fingerprint)
    h.update(_to_be_i32(score))
    return h.digest()


@dataclass
class KanInferenceRecord:
    sequence: int
    input_fingerprint: bytes
    score: int
    record_hash: bytes
    prev_hash: bytes


class KanInferenceLog:
    """Append-only hash-chained log of KAN scoring decisions (mirrors Rust)."""

    def __init__(self) -> None:
        self.records: list[KanInferenceRecord] = []

    def terminal_hash(self) -> bytes:
        return self.records[-1].record_hash if self.records else KAN_GENESIS_HASH

    def append_scored(self, scorer: KanScorer, inputs: list[int]) -> KanInferenceRecord:
        score = scorer.score(inputs)
        fp = fingerprint_inputs(inputs)
        prev = self.terminal_hash()
        seq = len(self.records)
        rh = _compute_record_hash(prev, seq, fp, score)
        rec = KanInferenceRecord(seq, fp, score, rh, prev)
        self.records.append(rec)
        return rec

    def verify_chain(self) -> tuple[bool, int | None]:
        prev = KAN_GENESIS_HASH
        for i, r in enumerate(self.records):
            if r.prev_hash != prev or r.sequence != i:
                return (False, i)
            if r.record_hash != _compute_record_hash(prev, r.sequence, r.input_fingerprint, r.score):
                return (False, i)
            prev = r.record_hash
        return (True, None)


def constitutional_scorer() -> KanScorer:
    """
    The canonical constitutional scorer used by the ARBITRATION gate.

    A 4-input → 4-hidden → 1-output INT4 LUT-KAN. The four inputs are the
    constitutional feature quantisation of a claim:
      [evidence_strength, determinism_signal, t45_contamination, citation_quality]
    each quantised to [0,15]. Higher score = stronger admission case.

    Edge LUTs are deterministic ramps/penalties — fixed constants, not learned,
    so the gate is fully reproducible. (T2: weights are an engineering hypothesis;
    promotion to T1 requires benchmarked calibration against labelled corpus.)
    """
    def ramp() -> list[int]:
        return [i * 6 for i in range(LUT_SIZE)]

    def penalty() -> list[int]:
        # Contamination feature: high values DECREASE the score.
        return [(LUT_SIZE - 1 - i) * 6 for i in range(LUT_SIZE)]

    # inner: 4 inputs → 4 hidden. evidence/determinism/citation ramp up; t45 penalises.
    inner_edges = []
    for _hidden in range(4):
        inner_edges.extend([ramp(), ramp(), penalty(), ramp()])
    inner = KanLayer(n_in=4, n_out=4, edges=inner_edges, rescale_shift=2)
    outer = KanLayer(n_in=4, n_out=1, edges=[ramp(), ramp(), ramp(), ramp()], rescale_shift=2)
    return KanScorer(inner, outer)


# ── ARBITRATION keyword features (mirrors corpus-ingestion SKILL.md) ───────────

_T0_KW = ("formally verified", "mechanically proven", "sha-256", "hash chain",
          "byte-identical", "deterministic")
_T1_KW = ("empirically validated", "benchmark", "measurement", "observed across runs",
          "production metric")
_T2_KW = ("engineering hypothesis", "proposed", "stub", "seam", "lut-kan", "rwkv-7",
          "plonky3", "bls", "pbft", "zk-snark", "bernstein", "mersenne")
_T45_KW = ("planetary", "civilizational", "sovereign consciousness", "omnipotent",
           "subquantum", "quantum vacuum", "compute bonds", "autopoietic closure",
           "metabolic computing", "self-improving", "unrestricted agi")
_CITE_KW = ("doi", "arxiv", "peer-reviewed", "et al", "proceedings", "journal")


def quantise_claim(claim: str) -> list[int]:
    """Extract the 4 constitutional features of a claim, each quantised to [0,15]."""
    low = claim.lower()

    def cnt(kws: tuple[str, ...]) -> int:
        return sum(low.count(k) for k in kws)

    evidence = min((cnt(_T0_KW) * 5 + cnt(_T1_KW) * 3 + cnt(_T2_KW) * 2), 15)
    determinism = min(cnt(_T0_KW) * 5, 15)
    contamination = min(cnt(_T45_KW) * 6, 15)
    citation = min(cnt(_CITE_KW) * 4, 15)
    return [evidence, determinism, contamination, citation]


# Admission threshold (fixed-point). Claims scoring below this with high
# contamination are quarantined. T2 hypothesis — calibration pending.
ADMISSION_THRESHOLD = 30


def arbitrate(claim: str, scorer: KanScorer, log: KanInferenceLog) -> dict[str, Any]:
    """
    ARBITRATION gate: score a claim, hash-chain the decision, return the verdict.
    Hard quarantine on any T4/T5 keyword regardless of score (the gate is not
    a vote — T4/T5 contamination is a veto, mirroring the constitutional rule).
    """
    low = claim.lower()
    t45_hit = next((k for k in _T45_KW if k in low), None)
    features = quantise_claim(claim)
    rec = log.append_scored(scorer, features)

    if t45_hit is not None:
        tier, admitted = "T4/T5", False
        reason = f"T4/T5 contamination keyword: '{t45_hit}'"
    elif any(k in low for k in _T0_KW):
        tier, admitted = "T0", rec.score >= ADMISSION_THRESHOLD
        reason = "T0 mechanical keywords present"
    elif any(k in low for k in _T1_KW):
        tier, admitted = "T1", rec.score >= ADMISSION_THRESHOLD
        reason = "T1 empirical keywords present"
    elif any(k in low for k in _T2_KW):
        tier, admitted = "T2", rec.score >= ADMISSION_THRESHOLD
        reason = "T2 engineering-hypothesis keywords present"
    else:
        tier, admitted = "T3", rec.score >= ADMISSION_THRESHOLD
        reason = "no tier keywords — defaulted to T3 conjecture"

    return {
        "claim": claim,
        "features": features,
        "kan_score": rec.score,
        "tier": tier,
        "admitted": admitted,
        "reason": reason,
        "record_hash": rec.record_hash.hex(),
        "sequence": rec.sequence,
    }


# ── Pipeline orchestration ─────────────────────────────────────────────────────

PIPELINE_STAGES = [
    ("deep_researcher", "Stage 1 — exhaustive multi-source research, emit candidate claims"),
    ("corpus_ingestor", "Stage 2 — ARBITRATION: INT4 LUT-KAN score + tier classification"),
    ("batch_processor", "Stage 3 — Fibonacci-cadence batch admission into the lineage"),
    ("chronologist",    "Stage 4 — retrospective: narrate the lineage, close the loop"),
]


@dataclass
class PipelineResult:
    pipeline_id: str
    topic: str
    arbitration: list[dict] = field(default_factory=list)
    admitted: list[dict] = field(default_factory=list)
    quarantined: list[dict] = field(default_factory=list)
    kan_terminal_hash: str = ""
    chain_valid: bool = True
    stage_results: dict[str, str] = field(default_factory=dict)


async def _research_claims(topic: str, api_key: str) -> list[str]:
    """
    Stage 1 live: deep_researcher with real tools.
    Searches the web for the topic, fetches key sources, extracts candidate claims.
    Returns a list of concrete claims suitable for ARBITRATION.
    """
    import os
    from agents.tool_runner import run_with_tools

    task = (
        f"You are the DEEP RESEARCHER. Your mission: produce 6–10 concrete, falsifiable "
        f"claims about this topic: '{topic}'.\n\n"
        "Instructions:\n"
        "1. Use web_search to find relevant research, papers, benchmarks, and news.\n"
        "2. Use fetch_url to read the most relevant sources.\n"
        "3. Extract specific, verifiable claims — not vague opinions.\n"
        "4. Each claim should be one sentence, starting with the topic name.\n"
        "5. Include T0/T1/T2 markers where appropriate: e.g. '(SHA-256 hash-chained, "
        "   deterministic)' for T0, '(empirically benchmarked)' for T1, "
        "   '(engineering hypothesis)' for T2.\n"
        "6. Use write_memory to store your best 3 claims for future cycles.\n\n"
        "Output: a numbered list of claims, one per line. No preamble."
    )
    result = await run_with_tools(
        role="deep_researcher",
        task=task,
        api_key=api_key,
        namespace=f"research:{topic[:32]}",
        max_tool_rounds=6,
    )
    # Parse claims from numbered list output
    lines = result.output.strip().splitlines()
    claims: list[str] = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Strip leading numbering (1. / 1) / • / -)
        import re
        cleaned = re.sub(r"^[\d]+[.)]\s*|^[-•*]\s*", "", line).strip()
        if len(cleaned) > 20:
            claims.append(cleaned)
    return claims[:10] if claims else [
        f"{topic}: deterministic SHA-256 hash chain, byte-identical across platforms",
        f"{topic}: engineering hypothesis — LUT-KAN replaces B-spline activations",
        f"{topic}: empirically validated benchmark observed across production runs",
    ]


async def run_pipeline(topic: str, claims: list[str] | None = None,
                       live: bool = False) -> PipelineResult:
    """
    Run the four-stage Mythos cognitive pipeline over a topic.

    Live mode (ANTHROPIC_API_KEY set):
      Stage 1 — deep_researcher with real web search tools gathers claims
      Stage 2 — ARBITRATION: INT4 LUT-KAN constitutional gate
      Stage 3 — batch_processor synthesizes admitted claims into lineage
      Stage 4 — chronologist narrates the epistemic history

    Offline mode: deterministic ARBITRATION substrate alone (the constitutional
    core that does not depend on any inference backend — always reproducible).
    """
    import os
    pipeline_id = str(uuid.uuid4())
    scorer = constitutional_scorer()
    log = KanInferenceLog()
    result = PipelineResult(pipeline_id=pipeline_id, topic=topic)

    # Stage 1 — deep research
    _api_key = os.environ.get("ANTHROPIC_API_KEY", "") if live else ""

    if live and _api_key and claims is None:
        try:
            claims = await _research_claims(topic, _api_key)
            result.stage_results["deep_researcher"] = (
                f"Researched {len(claims)} claims via web search tools"
            )
        except Exception as exc:  # noqa: BLE001
            result.stage_results["deep_researcher"] = f"research fallback: {exc}"

    if claims is None:
        claims = [
            f"{topic}: deterministic SHA-256 hash chain, byte-identical across platforms",
            f"{topic}: engineering hypothesis — LUT-KAN replaces B-spline activations",
            f"{topic}: empirically validated benchmark observed across runs",
            f"{topic}: planetary civilizational self-improving sovereign consciousness",
        ]

    # Stage 2 — ARBITRATION gate (always runs — this is the constitutional core)
    for claim in claims:
        verdict = arbitrate(claim, scorer, log)
        result.arbitration.append(verdict)
        (result.admitted if verdict["admitted"] else result.quarantined).append(verdict)

    valid, _bad = log.verify_chain()
    result.chain_valid = valid
    result.kan_terminal_hash = log.terminal_hash().hex()

    # Stage 3 + 4 — live synthesis and narration
    if live and _api_key:
        try:
            from agents.tool_runner import run_with_tools

            # Stage 3 — batch_processor: synthesize admitted claims
            admitted_text = "\n".join(
                f"  [{v['tier']}] {v['claim']}" for v in result.admitted[:8]
            )
            batch_task = (
                f"You are the BATCH PROCESSOR. Synthesize these admitted claims about "
                f"'{topic}' into a structured knowledge summary:\n\n{admitted_text}\n\n"
                "Produce: (a) the 3 strongest claims with supporting evidence, "
                "(b) the gaps that need more research, (c) one verified citation "
                "per admitted T0/T1 claim. Use fetch_url if you need to verify a source. "
                "Write the synthesis to memory key 'synthesis'."
            )
            batch_r = await run_with_tools(
                role="batch_processor", task=batch_task,
                api_key=_api_key, namespace=f"pipeline:{topic[:32]}", max_tool_rounds=4,
            )
            result.stage_results["batch_processor"] = batch_r.output[:2000]

            # Stage 4 — chronologist: narrate the lineage
            chron_task = (
                f"You are the CHRONOLOGIST. Narrate the epistemic history of this "
                f"research cycle on '{topic}'.\n\n"
                f"Chain terminal hash: {result.kan_terminal_hash[:32]}…\n"
                f"Admitted: {len(result.admitted)}  Quarantined: {len(result.quarantined)}\n"
                f"Chain valid: {result.chain_valid}\n\n"
                "Produce a retrospective: what was learned, what was rejected and why, "
                "what the temporal sequence reveals about the epistemic quality of the "
                "topic, and what should be researched next. Reference the KAN scores. "
                "Store the retrospective to memory key 'retrospective'."
            )
            chron_r = await run_with_tools(
                role="chronologist", task=chron_task,
                api_key=_api_key, namespace=f"pipeline:{topic[:32]}", max_tool_rounds=3,
            )
            result.stage_results["chronologist"] = chron_r.output[:2000]

        except Exception as exc:  # noqa: BLE001
            result.stage_results["synthesis_error"] = str(exc)

    return result


def _print_result(r: PipelineResult) -> None:
    print(f"\nMythos Cognitive Pipeline — {r.pipeline_id[:8]}")
    print(f"Topic: {r.topic}")
    print("=" * 64)
    for v in r.arbitration:
        flag = "✓ ADMIT " if v["admitted"] else "✗ QUARANTINE"
        print(f"  {flag} [{v['tier']:5s}] score={v['kan_score']:4d}  {v['claim'][:54]}")
        print(f"            reason: {v['reason']}")
    print("─" * 64)
    print(f"  Admitted:    {len(r.admitted)}")
    print(f"  Quarantined: {len(r.quarantined)}")
    print(f"  KAN chain valid: {r.chain_valid}")
    print(f"  KAN terminal hash: {r.kan_terminal_hash[:32]}…")
    if r.stage_results:
        print("\n  LIVE STAGE OUTPUTS:")
        for stage, out in r.stage_results.items():
            print(f"  [{stage}] {out[:200]}")


def main() -> None:
    parser = argparse.ArgumentParser(description="AEGIS Mythos Cognitive Pipeline")
    sub = parser.add_subparsers(dest="command")

    run_p = sub.add_parser("run", help="Run the four-stage pipeline over a topic")
    run_p.add_argument("--topic", required=True)
    run_p.add_argument("--live", action="store_true", help="Dispatch stages to live Mythos agents")

    score_p = sub.add_parser("score", help="Score a single claim through the ARBITRATION gate")
    score_p.add_argument("--claim", required=True)

    sub.add_parser("demo", help="Run the deterministic demo pipeline")

    args = parser.parse_args()

    if args.command == "run":
        r = asyncio.run(run_pipeline(args.topic, live=args.live))
        _print_result(r)
    elif args.command == "score":
        scorer = constitutional_scorer()
        log = KanInferenceLog()
        verdict = arbitrate(args.claim, scorer, log)
        print(json.dumps({k: v for k, v in verdict.items()
                          if k != "record_hash"} | {"record_hash": verdict["record_hash"][:16]},
                         indent=2))
    elif args.command == "demo":
        r = asyncio.run(run_pipeline("INT4 LUT-KAN viability"))
        _print_result(r)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
