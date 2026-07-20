"""Fail-closed adapter for oGemma/MYTHOS advisory verdicts.

This module does not execute a model or mutate AEGIS state. It validates and
normalizes a holon verdict into evidence that can be submitted to the canonical
AEGIS authority path. Automaton-3 remains the only authority evaluator.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from hashlib import sha256
import json
from typing import Any, Final, Literal, Mapping

Gate = Literal["PRE_ORCHESTRATE", "POST_VALIDATE", "POST_REVIEW"]
Verdict = Literal["APPROVED", "FAILED"]

ALLOWED_GATES: Final[frozenset[str]] = frozenset(
    {"PRE_ORCHESTRATE", "POST_VALIDATE", "POST_REVIEW"}
)
ALLOWED_VERDICTS: Final[frozenset[str]] = frozenset({"APPROVED", "FAILED"})


class OgemmaEvidenceError(ValueError):
    """Raised when oGemma evidence is malformed or cannot be admitted."""


@dataclass(frozen=True, slots=True)
class BioState:
    stress: float
    attention: float
    rir: float
    atp: int


@dataclass(frozen=True, slots=True)
class OgemmaEvidence:
    schema_version: str
    evidence_tier: str
    holon_id: str
    gate: Gate
    verdict: Verdict
    confidence: float
    reason_code: str
    task_digest: str
    plan_digest: str
    prompt_digest: str
    model_identity: str
    bio_state: BioState
    bio_state_digest: str
    evidence_digest: str


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _digest_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _require_sha256(name: str, value: str) -> str:
    if len(value) != 64 or any(ch not in "0123456789abcdef" for ch in value):
        raise OgemmaEvidenceError(f"{name} must be a lowercase SHA-256 digest")
    return value


def validate_bio_state(raw: Mapping[str, Any]) -> BioState:
    required = {"stress", "attention", "rir", "atp"}
    if set(raw) != required:
        missing = sorted(required - set(raw))
        extra = sorted(set(raw) - required)
        raise OgemmaEvidenceError(f"invalid bio_state keys: missing={missing}, extra={extra}")

    values: dict[str, float | int] = {}
    for name in ("stress", "attention", "rir"):
        value = raw[name]
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            raise OgemmaEvidenceError(f"bio_state.{name} must be numeric")
        normalized = float(value)
        if not 0.0 <= normalized <= 1.0:
            raise OgemmaEvidenceError(f"bio_state.{name} must be in [0, 1]")
        values[name] = normalized

    atp = raw["atp"]
    if isinstance(atp, bool) or not isinstance(atp, int):
        raise OgemmaEvidenceError("bio_state.atp must be an integer")
    if not 0 <= atp <= 2500:
        raise OgemmaEvidenceError("bio_state.atp must be in [0, 2500]")
    values["atp"] = atp

    return BioState(
        stress=float(values["stress"]),
        attention=float(values["attention"]),
        rir=float(values["rir"]),
        atp=int(values["atp"]),
    )


def normalize_verdict(
    *,
    holon_id: str,
    gate: str,
    verdict: str,
    confidence: float,
    reason_code: str,
    task: str,
    plan_digest: str,
    prompt_digest: str,
    model_identity: str,
    bio_state: Mapping[str, Any],
) -> OgemmaEvidence:
    """Validate and bind an advisory verdict into a replayable evidence envelope."""

    if gate not in ALLOWED_GATES:
        raise OgemmaEvidenceError(f"unknown gate denied: {gate!r}")
    if verdict not in ALLOWED_VERDICTS:
        raise OgemmaEvidenceError(f"unknown verdict denied: {verdict!r}")
    if not holon_id.strip():
        raise OgemmaEvidenceError("holon_id is required")
    if not model_identity.strip():
        raise OgemmaEvidenceError("model_identity is required")
    if not reason_code.strip():
        raise OgemmaEvidenceError("reason_code is required")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)):
        raise OgemmaEvidenceError("confidence must be numeric")
    confidence_value = float(confidence)
    if not 0.0 <= confidence_value <= 1.0:
        raise OgemmaEvidenceError("confidence must be in [0, 1]")

    state = validate_bio_state(bio_state)
    plan_hash = _require_sha256("plan_digest", plan_digest)
    prompt_hash = _require_sha256("prompt_digest", prompt_digest)
    state_payload = asdict(state)
    state_digest = sha256(_canonical_json(state_payload)).hexdigest()

    unsigned: dict[str, Any] = {
        "schema_version": "1.0.0",
        "evidence_tier": "T2",
        "holon_id": holon_id,
        "gate": gate,
        "verdict": verdict,
        "confidence": confidence_value,
        "reason_code": reason_code,
        "task_digest": _digest_text(task),
        "plan_digest": plan_hash,
        "prompt_digest": prompt_hash,
        "model_identity": model_identity,
        "bio_state": state_payload,
        "bio_state_digest": state_digest,
    }
    evidence_digest = sha256(_canonical_json(unsigned)).hexdigest()

    return OgemmaEvidence(
        schema_version="1.0.0",
        evidence_tier="T2",
        holon_id=holon_id,
        gate=gate,  # type: ignore[arg-type]
        verdict=verdict,  # type: ignore[arg-type]
        confidence=confidence_value,
        reason_code=reason_code,
        task_digest=unsigned["task_digest"],
        plan_digest=plan_hash,
        prompt_digest=prompt_hash,
        model_identity=model_identity,
        bio_state=state,
        bio_state_digest=state_digest,
        evidence_digest=evidence_digest,
    )


def to_authority_evidence(evidence: OgemmaEvidence) -> dict[str, Any]:
    """Return the bounded payload Automaton-3 may evaluate as T2 evidence."""

    payload = asdict(evidence)
    return {
        "source": "ogemma-mythos-holon",
        "evidence_tier": "T2",
        "grants_authority": False,
        "payload": payload,
    }
