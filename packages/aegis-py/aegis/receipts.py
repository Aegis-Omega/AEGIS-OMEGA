"""AEGIS Receipts — a verifiable, hash-chained trail of LLM calls.

    from anthropic import Anthropic
    from aegis.receipts import Recorder, wrap_anthropic

    client = wrap_anthropic(Anthropic(), Recorder("receipts.json"))
    client.messages.create(model="claude-opus-5-5", max_tokens=256,
                           messages=[{"role": "user", "content": "hi"}])

    $ aegis receipts verify receipts.json

Each call appends one envelope to an AEGIS_EXECUTION_ENVELOPE_CHAIN_V1 file:
digests of the exact request and response, the model, the provider, a
sequence number and the previous envelope's hash. Changing any byte of any
past envelope breaks verification from that point on. The format is the one
the bridge emits (sovereign-omega-v2/python/canonical_envelope.py) and the
independent offline verifier checks (scripts/aegis-envelope-verify.py, #708).

What a VALID chain proves: integrity and ordering of the recorded digests.
It does not prove who recorded them (signatures are Phase 2) or that the
provider really served the response.

Stdlib only; canonicalization is byte-identical to the TypeScript path
(asserted against sovereign-omega-v2/test/vectors/canon-vectors.json).
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
CHAIN_KIND = "AEGIS_EXECUTION_ENVELOPE_CHAIN_V1"
CANON_VERSION = "JCS-1"
GENESIS = "0" * 64
BODY_FIELDS = ("canon_version", "seq", "prev_hash", "request_digest",
               "response_digest", "model_id", "epistemic_tier", "provider")


def canon(value: Any) -> bytes:
    """Canonical bytes: sorted keys, no whitespace, UTF-8, no Unicode
    normalization. Floats are rejected; digest inputs pass encode_floats first."""
    def check(v: Any) -> None:
        if isinstance(v, float):
            raise TypeError("float in hashed state is forbidden (non-deterministic)")
        if isinstance(v, dict):
            for x in v.values():
                check(x)
        elif isinstance(v, (list, tuple)):
            for x in v:
                check(x)
    check(value)
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def encode_floats(obj: Any) -> Any:
    """Floats become their shortest round-trip decimal string (ADR 0001)."""
    if isinstance(obj, float):
        return repr(obj)
    if isinstance(obj, dict):
        return {k: encode_floats(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [encode_floats(x) for x in obj]
    return obj


def digest(payload: Any) -> str:
    return hashlib.sha256(canon(encode_floats(payload))).hexdigest()


def _envelope_hash(env: dict) -> str:
    return hashlib.sha256(canon({k: env[k] for k in BODY_FIELDS})).hexdigest()


class Recorder:
    """Appends envelopes to a chain file, resuming an existing chain."""

    def __init__(self, path: str | os.PathLike):
        self.path = Path(path)
        self._lock = threading.Lock()
        self._envelopes: list[dict] = []
        if self.path.exists():
            result = verify(self.path)
            if not result["valid"]:
                raise ValueError(f"refusing to extend an invalid chain: {result['error']}")
            self._envelopes = json.loads(self.path.read_text(encoding="utf-8"))["envelopes"]

    def record(self, request: Any, response: Any, *, model_id: str, provider: str,
               epistemic_tier: str = "T2") -> dict:
        with self._lock:
            prev = self._envelopes[-1]["envelope_hash"] if self._envelopes else GENESIS
            env = {
                "canon_version": CANON_VERSION,
                "seq": len(self._envelopes),
                "prev_hash": prev,
                "request_digest": digest(request),
                "response_digest": digest(response),
                "model_id": model_id,
                "epistemic_tier": epistemic_tier,
                "provider": provider,
            }
            env["envelope_hash"] = _envelope_hash(env)
            env["signature"] = None
            self._envelopes.append(env)
            package = {"schema_version": SCHEMA_VERSION, "kind": CHAIN_KIND,
                       "envelopes": self._envelopes,
                       "expected_terminal_hash": env["envelope_hash"]}
            tmp = self.path.with_suffix(self.path.suffix + ".tmp")
            tmp.write_text(json.dumps(package, indent=1, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp, self.path)
            return env


def verify(path: str | os.PathLike) -> dict:
    """Recompute every envelope hash and link. Returns {valid, count, terminal_hash, error}."""
    try:
        pkg = json.loads(Path(path).read_text(encoding="utf-8"))
        if pkg.get("kind") != CHAIN_KIND:
            raise ValueError("WRONG_KIND")
        prev = GENESIS
        for i, env in enumerate(pkg["envelopes"]):
            if env.get("seq") != i:
                raise ValueError(f"SEQ_MISMATCH at {i}")
            if env.get("prev_hash") != prev:
                raise ValueError(f"BROKEN_LINK at {i}")
            if env.get("signature") is not None:
                raise ValueError(f"UNVERIFIABLE_SIGNATURE at {i}")
            if _envelope_hash(env) != env.get("envelope_hash"):
                raise ValueError(f"HASH_MISMATCH at {i}")
            prev = env["envelope_hash"]
        if pkg.get("expected_terminal_hash") not in (None, prev):
            raise ValueError("TERMINAL_MISMATCH")
        return {"valid": True, "count": len(pkg["envelopes"]), "terminal_hash": prev, "error": None}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"valid": False, "count": None, "terminal_hash": None, "error": str(exc)}


def _plain(obj: Any) -> Any:
    """SDK response objects → plain JSON (pydantic model_dump when present)."""
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    return obj


def wrap_anthropic(client: Any, recorder: Recorder, *, epistemic_tier: str = "T2") -> Any:
    """Return `client` with messages.create recorded. Everything else passes through."""
    create = client.messages.create

    def recorded_create(**kwargs: Any) -> Any:
        response = create(**kwargs)
        recorder.record(kwargs, _plain(response), model_id=str(kwargs.get("model", "")),
                        provider="anthropic", epistemic_tier=epistemic_tier)
        return response

    client.messages.create = recorded_create
    return client
