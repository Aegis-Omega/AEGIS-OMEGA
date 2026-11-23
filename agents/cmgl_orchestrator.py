"""
CMGL-SHOS orchestrator — multi-model agents with adversarial cross-critique and a
consensus graph. EPISTEMIC TIER: T2 (engineering hypothesis, not proven optimal).

Loop: broadcast → parallel generate → cross-critique → merge graph → arbitrate →
stability gate (iterate on failure). No model is authoritative; only the merged graph is.
Models never talk to each other: every payload passes through this module as JSON.

Run:  python -m agents.cmgl_orchestrator "why did the deploy fail?" --agents claude,qwen,gemini
Keys: ANTHROPIC_API_KEY, DASHSCOPE_API_KEY, GEMINI_API_KEY (agents without a key are skipped).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass, field
from typing import Awaitable, Callable

Provider = Callable[[str, str], Awaitable[str]]  # (system, user) -> raw text

EDGE_THRESHOLD = 0.5       # merged edge weight needed to enter the consensus graph
CONTRADICTION_PENALTY = 0.25
MAX_CONTRADICTION_DENSITY = 0.34
CALL_TIMEOUT_S = 120

GENERATE_SCHEMA = (
    '{"hypotheses":[str],"edges":[{"src":str,"dst":str,"strength":0..1}],'
    '"assumptions":[str],"confidence":0..1}'
)
CRITIQUE_SCHEMA = '{"contradictions":[{"target":str,"edge":"src->dst","reason":str}],"missing":[str]}'
CRITIC_FOCUS = {
    "claude": "causal validity: reversed or spurious causation, missing confounders",
    "qwen": "structure and efficiency: redundant, circular or over-complex reasoning",
    "gemini": "completeness and coverage: missing causes, ignored alternatives",
}
SYSTEM = (
    "You are one independent agent in a multi-model reasoning system. Answer ONLY with a "
    "single JSON object matching the schema. No prose, no markdown. State assumptions "
    "explicitly; never hide uncertainty."
)


def _json_object(text: str) -> dict:
    start = text.find("{")
    if start < 0:
        raise ValueError("no JSON object in response")
    obj, _ = json.JSONDecoder().raw_decode(text[start:])
    if not isinstance(obj, dict):
        raise ValueError("response JSON is not an object")
    return obj


def _edge_key(src: object, dst: object) -> str:
    return f"{str(src).strip().lower()}->{str(dst).strip().lower()}"


def parse_generation(text: str) -> dict:
    obj = _json_object(text)
    edges: dict[str, float] = {}
    for e in obj.get("edges", []):
        s = float(e.get("strength", 0.5))
        edges[_edge_key(e["src"], e["dst"])] = min(1.0, max(0.0, s))
    return {
        "hypotheses": [str(h) for h in obj.get("hypotheses", [])],
        "edges": edges,
        "assumptions": [str(a) for a in obj.get("assumptions", [])],
        "confidence": min(1.0, max(0.0, float(obj.get("confidence", 0.0)))),
    }


def parse_critique(text: str) -> dict:
    obj = _json_object(text)
    return {
        "contradictions": [
            {"target": str(c["target"]).strip().lower(), "edge": str(c["edge"]).strip().lower(),
             "reason": str(c.get("reason", ""))}
            for c in obj.get("contradictions", [])
        ],
        "missing": [str(m) for m in obj.get("missing", [])],
    }


def _find_cycle(edges: set[tuple[str, str]]) -> list[tuple[str, str]] | None:
    graph: dict[str, list[str]] = {}
    for s, d in edges:
        graph.setdefault(s, []).append(d)
    state: dict[str, int] = {}
    stack: list[str] = []

    def visit(n: str) -> list[str] | None:
        state[n] = 1
        stack.append(n)
        for m in sorted(graph.get(n, [])):
            if state.get(m) == 1:
                return stack[stack.index(m):] + [m]
            if state.get(m, 0) == 0:
                found = visit(m)
                if found:
                    return found
        stack.pop()
        state[n] = 2
        return None

    for node in sorted(graph):
        if state.get(node, 0) == 0:
            path = visit(node)
            if path:
                return list(zip(path, path[1:]))
    return None


@dataclass
class Result:
    task: str
    mode: str                                  # MERGE | PARTIAL_CONSENSUS | DEFER
    gate_passed: bool
    iterations: int
    graph: dict[str, dict] = field(default_factory=dict)       # edge -> {weight, uncertainty, supporters}
    dropped: dict[str, float] = field(default_factory=dict)    # edge -> weight (below threshold)
    cycles_resolved: list[str] = field(default_factory=list)
    scores: dict[str, float] = field(default_factory=dict)
    confidence: dict[str, float] = field(default_factory=dict)
    contradiction_density: float = 0.0
    stability: float | None = None             # Jaccard vs previous iteration; None if 1 iteration
    unresolved: list[str] = field(default_factory=list)
    contradictions: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_text(self) -> str:
        lines = ["FINAL CONSENSUS RESULT", f"MODE: {self.mode}  GATE: {'PASS' if self.gate_passed else 'FAIL'}",
                 "CAUSAL GRAPH:"]
        for k, v in sorted(self.graph.items(), key=lambda kv: -kv[1]["weight"]):
            lines.append(f"  {k}  w={v['weight']:.2f} u={v['uncertainty']:.2f} by={','.join(v['supporters'])}")
        if not self.graph:
            lines.append("  (empty — no edge reached consensus)")
        lines.append("CONTRADICTIONS:")
        lines += [f"  {c['critic']} -> {c['target']} {c['edge']}: {c['reason']}" for c in self.contradictions] or ["  none"]
        lines.append("UNRESOLVED UNCERTAINTY:")
        lines += [f"  {u}" for u in self.unresolved] or ["  none"]
        lines.append("CONFIDENCE VECTOR: " + ", ".join(f"{m}={c:.2f}" for m, c in sorted(self.confidence.items())))
        lines.append("MODEL SCORES: " + ", ".join(f"{m}={s:.2f}" for m, s in sorted(self.scores.items())))
        stab = "n/a (single iteration)" if self.stability is None else f"{self.stability:.2f}"
        lines.append(f"STABILITY: {stab}  CONTRADICTION DENSITY: {self.contradiction_density:.2f}")
        if self.cycles_resolved:
            lines.append("CYCLES RESOLVED: " + "; ".join(self.cycles_resolved))
        if self.errors:
            lines.append("ERRORS: " + "; ".join(self.errors))
        return "\n".join(lines)


async def _call(name: str, provider: Provider, user: str, errors: list[str], parse) -> dict | None:
    try:
        text = await asyncio.wait_for(provider(SYSTEM, user), CALL_TIMEOUT_S)
        return parse(text)
    except Exception as exc:  # a failed agent is data, not a crash
        errors.append(f"{name}: {type(exc).__name__}: {exc}")
        return None


def _merge(gens: dict[str, dict], crits: dict[str, dict]):
    n_ok = len(gens)
    keys = {k for g in gens.values() for k in g["edges"]}
    against: dict[str, list[dict]] = {k: [] for k in keys}
    for critic, c in crits.items():
        for item in c["contradictions"]:
            if item["edge"] in against and item["target"] in gens and item["target"] != critic:
                against[item["edge"]].append({"critic": critic, **item})
    weights, supporters = {}, {}
    for k in keys:
        sup = {m: g["edges"][k] for m, g in gens.items() if k in g["edges"]}
        penalty = CONTRADICTION_PENALTY * len({c["critic"] for c in against[k]})
        weights[k] = min(1.0, max(0.0, sum(sup.values()) / n_ok - penalty))
        supporters[k] = sorted(sup)
    kept = {k for k, w in weights.items() if w >= EDGE_THRESHOLD}
    resolved: list[str] = []
    while True:
        cycle = _find_cycle({tuple(k.split("->", 1)) for k in kept})  # type: ignore[arg-type]
        if not cycle:
            break
        weakest = min((f"{s}->{d}" for s, d in cycle), key=lambda k: (weights[k], k))
        kept.discard(weakest)
        resolved.append(f"dropped {weakest} (w={weights[weakest]:.2f})")
    return weights, supporters, against, kept, resolved


def _arbitrate(gens, against, kept, n_ok):
    scores: dict[str, float] = {}
    contributors = []
    for m, g in gens.items():
        own = set(g["edges"])
        surviving = own & kept
        if surviving:
            contributors.append(m)
        integrity = len(surviving) / len(own) if own else 0.0
        cross = (sum((len([o for o in gens if o != m and k in gens[o]["edges"]]) / (n_ok - 1)) for k in own) / len(own)
                 if own and n_ok > 1 else 0.0)
        density = min(1.0, sum(len([c for c in against[k] if c["target"] == m]) for k in own) / max(len(own), 1))
        load = min(1.0, len(g["assumptions"]) / (len(g["hypotheses"]) + len(own) + 1))
        scores[m] = integrity + cross - density - load
    mode = "DEFER" if not contributors else "PARTIAL_CONSENSUS" if len(contributors) == 1 else "MERGE"
    return scores, mode


async def run(task: str, providers: dict[str, Provider], max_iterations: int = 3) -> Result:
    if not providers:
        raise ValueError("no agents available")
    errors: list[str] = []
    previous_note = ""
    prev_kept: set[str] | None = None
    result: Result | None = None

    for it in range(1, max_iterations + 1):
        gen_prompt = f"TASK: {task}\nSchema: {GENERATE_SCHEMA}{previous_note}"
        outs = await asyncio.gather(*[_call(n, p, gen_prompt, errors, parse_generation) for n, p in providers.items()])
        gens = {n: o for n, o in zip(providers, outs) if o is not None}
        if not gens:
            return Result(task, "DEFER", False, it, errors=errors, unresolved=["all agents failed"])

        crit_outs = await asyncio.gather(*[
            _call(n, providers[n], _critique_prompt(n, task, gens), errors, parse_critique)
            for n in gens if len(gens) > 1
        ])
        crits = {n: c for n, c in zip([n for n in gens if len(gens) > 1], crit_outs) if c is not None}

        weights, supporters, against, kept, resolved = _merge(gens, crits)
        scores, mode = _arbitrate(gens, against, kept, len(gens))
        all_contr = [c for k in against for c in against[k]]
        density = len(all_contr) / max(len(weights), 1)
        density = min(1.0, density)
        stability = None if prev_kept is None else (
            len(kept & prev_kept) / len(kept | prev_kept) if (kept | prev_kept) else 1.0)
        assumptions = sorted({a for g in gens.values() for a in g["assumptions"]})
        missing = sorted({m for c in crits.values() for m in c["missing"]})
        gate = mode != "DEFER" and density <= MAX_CONTRADICTION_DENSITY and len(gens) > 1
        result = Result(
            task=task, mode=mode, gate_passed=gate, iterations=it,
            graph={k: {"weight": weights[k], "uncertainty": 1 - weights[k], "supporters": supporters[k]} for k in sorted(kept)},
            dropped={k: weights[k] for k in sorted(set(weights) - kept)},
            cycles_resolved=resolved, scores=scores,
            confidence={m: g["confidence"] for m, g in gens.items()},
            contradiction_density=density, stability=stability,
            unresolved=[f"assumption: {a}" for a in assumptions] + [f"missing: {m}" for m in missing],
            contradictions=all_contr, errors=list(errors),
        )
        if gate:
            return result
        prev_kept = kept
        previous_note = ("\nPREVIOUS ROUND (revise; fix or defend contradicted edges):\n"
                         + json.dumps({"consensus_edges": sorted(kept), "contradictions": all_contr}))
    assert result is not None
    return result


def _critique_prompt(me: str, task: str, gens: dict[str, dict]) -> str:
    others = {m: {"edges": g["edges"], "assumptions": g["assumptions"], "hypotheses": g["hypotheses"]}
              for m, g in gens.items() if m != me}
    focus = CRITIC_FOCUS.get(me, "any weakness you can substantiate")
    return (f"TASK: {task}\nYou are {me}. Attack the other agents' outputs, focus: {focus}.\n"
            f"Only contradict an edge you can give a concrete reason against; 'edge' must be an exact "
            f"'src->dst' key and 'target' the agent name.\nSchema: {CRITIQUE_SCHEMA}\n"
            f"OTHERS: {json.dumps(others)}")


def _claude(model: str) -> Provider:
    async def call(system: str, user: str) -> str:
        import anthropic
        r = await anthropic.AsyncAnthropic().messages.create(
            model=model, max_tokens=2000, system=system, messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in r.content if getattr(b, "type", "") == "text")
    return call


def _qwen(model: str) -> Provider:
    base = os.environ.get("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")

    async def call(system: str, user: str) -> str:
        import httpx
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as c:
            r = await c.post(f"{base}/chat/completions",
                             headers={"Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"},
                             json={"model": model, "messages": [{"role": "system", "content": system},
                                                                {"role": "user", "content": user}]})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"]
    return call


def _gemini(model: str) -> Provider:
    async def call(system: str, user: str) -> str:
        import httpx
        key = os.environ.get("GEMINI_API_KEY") or os.environ["GOOGLE_API_KEY"]
        async with httpx.AsyncClient(timeout=CALL_TIMEOUT_S) as c:
            r = await c.post(
                f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                headers={"x-goog-api-key": key},
                json={"systemInstruction": {"parts": [{"text": system}]},
                      "contents": [{"role": "user", "parts": [{"text": user}]}],
                      "generationConfig": {"responseMimeType": "application/json"}})
            r.raise_for_status()
            return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    return call


def available_providers(names: list[str]) -> tuple[dict[str, Provider], list[str]]:
    env = os.environ
    table = {
        "claude": (lambda: bool(env.get("ANTHROPIC_API_KEY")), lambda: _claude(env.get("CLAUDE_MODEL", "claude-sonnet-5-5"))),
        "qwen": (lambda: bool(env.get("DASHSCOPE_API_KEY")), lambda: _qwen(env.get("QWEN_MODEL", "qwen3.7-plus"))),
        "gemini": (lambda: bool(env.get("GEMINI_API_KEY") or env.get("GOOGLE_API_KEY")), lambda: _gemini(env.get("GEMINI_MODEL", "gemini-2.5-pro"))),
    }
    found: dict[str, Provider] = {}
    skipped: list[str] = []
    for n in names:
        if n in table and table[n][0]():
            found[n] = table[n][1]()
        else:
            skipped.append(n)
    return found, skipped


def main() -> int:
    ap = argparse.ArgumentParser(description="CMGL-SHOS multi-model consensus")
    ap.add_argument("task")
    ap.add_argument("--agents", default="claude,qwen,gemini")
    ap.add_argument("--iterations", type=int, default=3)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    providers, skipped = available_providers([n.strip() for n in a.agents.split(",") if n.strip()])
    if skipped:
        print(f"skipped (no key or unknown): {', '.join(skipped)}", file=sys.stderr)
    if not providers:
        print("no agents available: set ANTHROPIC_API_KEY, DASHSCOPE_API_KEY and/or GEMINI_API_KEY", file=sys.stderr)
        return 1
    res = asyncio.run(run(a.task, providers, a.iterations))
    print(json.dumps(res.__dict__, indent=2) if a.json else res.to_text())
    return 0 if res.gate_passed else 2


if __name__ == "__main__":
    sys.exit(main())
