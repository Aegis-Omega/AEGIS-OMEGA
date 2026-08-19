from __future__ import annotations

from dataclasses import asdict, dataclass
from decimal import Decimal, localcontext
from hashlib import sha256
import json
from math import exp, sqrt
from typing import Any


class MathInvariantError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class QuorumVerification:
    schema_version: str
    threshold_milli: int
    threshold: str
    golden_ratio: str
    golden_conjugate: str
    absolute_error: str
    equals_inverse_of_defined_phi: bool
    verified_relation: str
    grants_authority: bool
    evidence_digest: str


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")


def verify_golden_quorum(threshold_milli: int = 618) -> QuorumVerification:
    if not isinstance(threshold_milli, int) or isinstance(threshold_milli, bool):
        raise MathInvariantError("threshold_milli must be an integer")
    if not 0 <= threshold_milli <= 1000:
        raise MathInvariantError("threshold_milli must be in [0, 1000]")

    with localcontext() as context:
        context.prec = 50
        golden_ratio = (Decimal(1) + Decimal(5).sqrt()) / Decimal(2)
        golden_conjugate = Decimal(1) / golden_ratio
        threshold = Decimal(threshold_milli) / Decimal(1000)
        absolute_error = abs(threshold - golden_conjugate)
        inverse_of_defined_phi = Decimal(1) / golden_conjugate

        unsigned = {
            "schema_version": "1.0.0",
            "threshold_milli": threshold_milli,
            "threshold": str(threshold),
            "golden_ratio": str(golden_ratio),
            "golden_conjugate": str(golden_conjugate),
            "absolute_error": str(absolute_error),
            "equals_inverse_of_defined_phi": threshold == inverse_of_defined_phi,
            "verified_relation": "golden_conjugate = 1 / golden_ratio = golden_ratio - 1",
            "grants_authority": False,
        }
        digest = sha256(_canonical(unsigned)).hexdigest()
        return QuorumVerification(**unsigned, evidence_digest=digest)


def attention_score(*, sigma_one: float, d_k: float, atp: float, stress_norm: float) -> float:
    values = {
        "sigma_one": sigma_one,
        "d_k": d_k,
        "atp": atp,
        "stress_norm": stress_norm,
    }
    for name, value in values.items():
        if not isinstance(value, (int, float)) or isinstance(value, bool):
            raise MathInvariantError(f"{name} must be numeric")
    if sigma_one < 0:
        raise MathInvariantError("sigma_one must be non-negative")
    if d_k <= 0:
        raise MathInvariantError("d_k must be positive")
    if atp <= 0:
        raise MathInvariantError("atp must be positive")
    if stress_norm < 0:
        raise MathInvariantError("stress_norm must be non-negative")

    tau_bio = sqrt(d_k) * (atp / 2500.0) * exp(-stress_norm)
    if tau_bio <= 0:
        raise MathInvariantError("tau_bio must remain positive")
    return sigma_one / tau_bio


def to_evidence(verification: QuorumVerification) -> dict[str, Any]:
    return {
        "evidence_kind": "SOL_WOLFRAM_QUORUM_VERIFICATION_V1",
        "evidence_tier": "T0",
        "grants_authority": False,
        "verification": asdict(verification),
    }
