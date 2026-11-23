"""Scripted-agent tests for agents/cmgl_orchestrator.py (no network, no API keys)."""

import asyncio
import json

from agents.cmgl_orchestrator import run


def gen(edges, assumptions=(), conf=0.8):
    return json.dumps({
        "hypotheses": ["h"],
        "edges": [{"src": s, "dst": d, "strength": w} for s, d, w in edges],
        "assumptions": list(assumptions),
        "confidence": conf,
    })


def crit(*items):
    return json.dumps({"contradictions": [{"target": t, "edge": e, "reason": "r"} for t, e in items], "missing": []})


def agent(generate, critique):
    """generate/critique: str or callable(prompt)->str."""
    async def call(system, user):
        pick = critique if "Attack the other agents" in user else generate
        return pick(user) if callable(pick) else pick
    return call


def run_sync(providers, **kw):
    return asyncio.run(run("task", providers, **kw))


def test_agreement_merges_and_passes_gate():
    g = gen([("a", "b", 0.9)])
    res = run_sync({m: agent(g, crit()) for m in ("claude", "qwen", "gemini")})
    assert res.mode == "MERGE" and res.gate_passed
    assert res.graph["a->b"]["weight"] == 0.9
    assert res.graph["a->b"]["supporters"] == ["claude", "gemini", "qwen"]


def test_single_model_edge_does_not_become_consensus():
    solo = agent(gen([("a", "b", 0.9)]), crit())
    empty = agent(gen([]), crit())
    res = run_sync({"claude": solo, "qwen": empty, "gemini": empty}, max_iterations=1)
    assert "a->b" not in res.graph and "a->b" in res.dropped
    assert res.mode == "DEFER" and not res.gate_passed


def test_two_critics_drop_a_contradicted_edge():
    g = gen([("a", "b", 0.9)])
    attack = crit(("gemini", "a->b"))
    res = run_sync({"claude": agent(g, attack), "qwen": agent(g, attack), "gemini": agent(g, crit())},
                   max_iterations=1)
    assert "a->b" in res.dropped and not res.gate_passed
    assert len(res.contradictions) == 2


def test_cycle_is_resolved_by_dropping_weakest_edge():
    g = gen([("a", "b", 0.9), ("b", "c", 0.9), ("c", "a", 0.6)])
    res = run_sync({m: agent(g, crit()) for m in ("claude", "qwen")})
    assert "c->a" not in res.graph and "a->b" in res.graph and "b->c" in res.graph
    assert res.cycles_resolved == ["dropped c->a (w=0.60)"]


def test_failing_and_garbage_agents_are_recorded_not_fatal():
    g = gen([("a", "b", 0.9)])

    async def boom(system, user):
        raise RuntimeError("down")

    res = run_sync({"claude": agent(g, crit()), "qwen": agent(g, crit()),
                    "gemini": boom, "extra": agent("not json at all", crit())})
    assert res.mode == "MERGE"
    assert any(e.startswith("gemini:") for e in res.errors)
    assert any(e.startswith("extra:") for e in res.errors)


def test_all_agents_failing_defers():
    async def boom(system, user):
        raise RuntimeError("down")

    res = run_sync({"claude": boom, "qwen": boom})
    assert res.mode == "DEFER" and not res.gate_passed


def test_one_surviving_agent_never_passes_gate():
    async def boom(system, user):
        raise RuntimeError("down")

    res = run_sync({"claude": agent(gen([("a", "b", 0.9)]), crit()), "qwen": boom}, max_iterations=1)
    assert not res.gate_passed  # a single model is not a consensus


def test_iteration_revises_after_contradictions():
    calls = {"n": 0}

    def critique(prompt):  # round 1 (first 3 critiques) attacks gemini's edge, later rounds don't
        calls["n"] += 1
        return crit(("gemini", "a->b")) if calls["n"] <= 3 else crit()

    g = gen([("a", "b", 0.9)])
    res = run_sync({m: agent(g, critique) for m in ("claude", "qwen", "gemini")}, max_iterations=3)
    assert res.iterations == 2 and res.gate_passed
    assert res.stability is not None
