"""AEGIS finite epistemic quotient / factorization witness v1.

This module operationalizes the same boundary expressed by
AbjadFactorization.factors_iff_constant_on_fibres:

A target may be read through a projection only when the target is constant on
every observed projection fibre.

This runtime checker is deliberately finite. A PASS proves factorization only
for the supplied observed sample set. It never upgrades a finite check into a
universal mathematical claim or repository authority.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
import hashlib
import json
from typing import Any, Iterable

SCHEMA = "AEGIS_EPISTEMIC_QUOTIENT_RECEIPT_V1"
PASS = "FACTORS_ON_OBSERVED_DOMAIN"
OBSTRUCTION = "FACTORISATION_OBSTRUCTED"
NO_AUTHORITY = "NONE"
FINITE_SCOPE = "OBSERVED_FINITE_DOMAIN_ONLY"
FORMAL_REFERENCE = {
    "repository": "Aegis-Omega/AEGIS-OMEGA",
    "commit": "828270626eb5581078c34ba8ae944a4bbd0a88d1",
    "path": "sovereign-omega-v2/formal/bridges/lean/AbjadFactorizationV1.lean",
    "theorem": "AbjadFactorization.factors_iff_constant_on_fibres",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def canonical_hash(domain: str, value: Any) -> str:
    payload = domain.encode("utf-8") + b"\x00" + canonical_bytes(value)
    return hashlib.sha256(payload).hexdigest()


def _canon_key(value: Any) -> str:
    return canonical_bytes(value).decode("utf-8")


@dataclass(frozen=True)
class FactorizationSampleV1:
    sample_id: str
    projection_value: Any
    target_value: Any

    def __post_init__(self) -> None:
        if not isinstance(self.sample_id, str) or not self.sample_id:
            raise ValueError("sample_id must be a non-empty string")
        # Force canonicalizability now, before any receipt is issued.
        canonical_bytes(self.projection_value)
        canonical_bytes(self.target_value)


@dataclass(frozen=True)
class FibreCollisionWitnessV1:
    projection_value: Any
    left_sample_id: str
    right_sample_id: str
    left_target_value: Any
    right_target_value: Any

    @property
    def root(self) -> str:
        return canonical_hash(
            "AEGIS_FIBRE_COLLISION_WITNESS_V1",
            asdict(self),
        )


@dataclass(frozen=True)
class EpistemicQuotientReceiptV1:
    status: str
    scope: str
    sample_count: int
    fibre_count: int
    source_root: str
    quotient_root: str | None
    quotient_table: tuple[tuple[Any, Any], ...]
    collision_witnesses: tuple[FibreCollisionWitnessV1, ...]
    authority_effect: str = field(default=NO_AUTHORITY, init=False)
    schema: str = field(default=SCHEMA, init=False)

    @property
    def receipt_sha256(self) -> str:
        body = {
            "schema": self.schema,
            "status": self.status,
            "scope": self.scope,
            "sample_count": self.sample_count,
            "fibre_count": self.fibre_count,
            "source_root": self.source_root,
            "quotient_root": self.quotient_root,
            "quotient_table": [
                {"projection_value": p, "target_value": t}
                for p, t in self.quotient_table
            ],
            "collision_witnesses": [
                {**asdict(w), "witness_root": w.root}
                for w in self.collision_witnesses
            ],
            "formal_reference": FORMAL_REFERENCE,
            "authority_effect": self.authority_effect,
        }
        return canonical_hash(SCHEMA, body)


def evaluate_factorization(
    samples: Iterable[FactorizationSampleV1],
) -> EpistemicQuotientReceiptV1:
    ordered = tuple(
        sorted(
            samples,
            key=lambda sample: (
                _canon_key(sample.projection_value),
                sample.sample_id,
                _canon_key(sample.target_value),
            ),
        )
    )
    if len({sample.sample_id for sample in ordered}) != len(ordered):
        raise ValueError("sample_id values must be unique")

    source_root = canonical_hash(
        "AEGIS_EPISTEMIC_FACTORISATION_SOURCE_V1",
        [asdict(sample) for sample in ordered],
    )

    fibres: dict[str, list[FactorizationSampleV1]] = {}
    projection_values: dict[str, Any] = {}
    for sample in ordered:
        key = _canon_key(sample.projection_value)
        fibres.setdefault(key, []).append(sample)
        projection_values[key] = sample.projection_value

    witnesses: list[FibreCollisionWitnessV1] = []
    quotient_entries: list[tuple[Any, Any]] = []

    for key in sorted(fibres):
        fibre = fibres[key]
        by_target: dict[str, list[FactorizationSampleV1]] = {}
        for sample in fibre:
            by_target.setdefault(_canon_key(sample.target_value), []).append(sample)

        if len(by_target) == 1:
            target_key = next(iter(by_target))
            quotient_entries.append(
                (projection_values[key], by_target[target_key][0].target_value)
            )
            continue

        target_keys = sorted(by_target)
        left = by_target[target_keys[0]][0]
        for right_key in target_keys[1:]:
            right = by_target[right_key][0]
            witnesses.append(
                FibreCollisionWitnessV1(
                    projection_value=projection_values[key],
                    left_sample_id=left.sample_id,
                    right_sample_id=right.sample_id,
                    left_target_value=left.target_value,
                    right_target_value=right.target_value,
                )
            )

    witnesses.sort(key=lambda witness: witness.root)

    if witnesses:
        return EpistemicQuotientReceiptV1(
            status=OBSTRUCTION,
            scope=FINITE_SCOPE,
            sample_count=len(ordered),
            fibre_count=len(fibres),
            source_root=source_root,
            quotient_root=None,
            quotient_table=(),
            collision_witnesses=tuple(witnesses),
        )

    quotient_entries.sort(key=lambda pair: _canon_key(pair[0]))
    quotient_payload = [
        {"projection_value": projection, "target_value": target}
        for projection, target in quotient_entries
    ]
    quotient_root = canonical_hash(
        "AEGIS_EPISTEMIC_QUOTIENT_V1",
        quotient_payload,
    )
    return EpistemicQuotientReceiptV1(
        status=PASS,
        scope=FINITE_SCOPE,
        sample_count=len(ordered),
        fibre_count=len(fibres),
        source_root=source_root,
        quotient_root=quotient_root,
        quotient_table=tuple(quotient_entries),
        collision_witnesses=(),
    )


def require_factorization(
    samples: Iterable[FactorizationSampleV1],
) -> EpistemicQuotientReceiptV1:
    receipt = evaluate_factorization(samples)
    if receipt.status != PASS:
        roots = ",".join(witness.root for witness in receipt.collision_witnesses)
        raise ValueError(f"FACTORISATION_OBSTRUCTED:{roots}")
    return receipt
