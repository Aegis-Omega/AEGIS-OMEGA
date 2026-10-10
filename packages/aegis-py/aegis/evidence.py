"""Evidence-checked LLM answers: integrity is not truth.

A valid receipt chain proves what the model said and that nobody edited it.
It does not prove that what the model said matches the data it was given.
This module checks that second part mechanically, with no model as judge:

    from anthropic import Anthropic
    from aegis.receipts import Recorder
    from aegis.evidence import verified_answer

    result = verified_answer(
        Anthropic(), Recorder("receipts.json"),
        question="Summarise these variants for a clinician.",
        evidence=[{"position": 5, "reference": "C", "alternate": "T",
                   "read_support": 2, "classification": "uncertain_significance"}],
        key="position",
    )
    result["verdict"]["status"]   # "consistent" | "contradicted"

The model must return its prose answer plus one structured claim per record it
relies on (enforced by a JSON schema). Each claim is compared field by field
with the evidence record that has the same key. A claim about a record that
does not exist is "fabricated"; any differing field is a "mismatch". The
verdict is written into the receipt, so the chain binds what was said *and*
whether it held up.

Scope, stated plainly: this checks structured claims against structured
evidence. It does not check prose that the model chose not to express as a
claim, and it does not judge whether the evidence itself is right.
"""
from __future__ import annotations

import json
from typing import Any

from .receipts import Recorder

DEFAULT_MODEL = "claude-opus-5-5"

_JSON_TYPES = {bool: "boolean", int: "integer", str: "string"}


def check_claims(evidence: list[dict], claims: list[dict], key: str,
                 fields: list[str] | None = None) -> dict:
    """Compare claims with evidence records matched on `key`."""
    by_key = {rec[key]: rec for rec in evidence}
    fields = fields or ([f for f in evidence[0] if f != key] if evidence else [])
    findings = []
    for i, claim in enumerate(claims):
        rec = by_key.get(claim.get(key))
        if rec is None:
            findings.append({"claim": i, "kind": "fabricated", key: claim.get(key)})
            continue
        for f in fields:
            if f in claim and claim[f] != rec[f]:
                findings.append({"claim": i, "kind": "mismatch", key: rec[key], "field": f,
                                 "evidence": rec[f], "claimed": claim[f]})
    return {"status": "contradicted" if findings else "consistent",
            "claims_checked": len(claims), "findings": findings}


def claims_schema(evidence: list[dict], key: str) -> dict:
    """JSON schema for {answer, claims[]} with claim fields typed from the evidence."""
    props = {}
    for f, v in evidence[0].items():
        t = _JSON_TYPES.get(type(v))
        if t is None:
            raise TypeError(f"evidence field {f!r} must be str, int or bool (no floats)")
        props[f] = {"type": t}
    return {
        "type": "object",
        "properties": {
            "answer": {"type": "string"},
            "claims": {"type": "array", "items": {
                "type": "object", "properties": props,
                "required": list(props), "additionalProperties": False}},
        },
        "required": ["answer", "claims"],
        "additionalProperties": False,
    }


def verified_answer(client: Any, recorder: Recorder, *, question: str, evidence: list[dict],
                    key: str, model: str = DEFAULT_MODEL, max_tokens: int = 16000) -> dict:
    """Ask the model, check its claims against `evidence`, record a receipt with the verdict."""
    request = {
        "model": model,
        "max_tokens": max_tokens,
        "system": ("Answer using only the evidence records provided. For every record your "
                   "answer relies on, add one entry to `claims` copying that record's fields "
                   "exactly as you understand them."),
        "messages": [{"role": "user", "content":
                      f"{question}\n\nEvidence records (JSON):\n{json.dumps(evidence, ensure_ascii=False)}"}],
        "output_config": {"format": {"type": "json_schema", "schema": claims_schema(evidence, key)}},
        # Server-side fallback when a safety classifier declines the request.
        "betas": ["server-side-fallback-2026-07-01"],
        "fallbacks": "default",
    }
    response = client.beta.messages.create(**request)
    if getattr(response, "stop_reason", None) == "refusal":
        verdict = {"status": "refused", "claims_checked": 0, "findings": []}
        output = {"answer": None, "claims": []}
    else:
        text = next(b.text for b in response.content if b.type == "text")
        output = json.loads(text)
        verdict = check_claims(evidence, output["claims"], key)
    receipt = recorder.record(request, {"output": output, "verdict": verdict},
                              model_id=model, provider="anthropic")
    return {"answer": output["answer"], "claims": output["claims"], "verdict": verdict,
            "receipt": receipt}
