"""AEGIS / MYTHOS Perspective v1.

Observation-only hidden-state probe translating the MYTHOS Perspective reading into
four measurable views over a neural trajectory:

1. categorical/algebraic geometry,
2. formal transition preservation,
3. forensic/auditability hash chaining,
4. information-theoretic projection-energy entropy.

This module never mutates model state and never grants authority.  It proves only
properties of the measured projection/trajectory, not semantic truth or reasoning
correctness.
"""
from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from typing import Sequence

import torch


READINGS = (
    "CATEGORICAL_ALGEBRAIC",
    "FORMAL_TRANSITION_PRESERVATION",
    "FORENSIC_AUDITABILITY",
    "INFORMATION_THEORETIC",
)


def _canonical_bytes(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _domain_hash(domain: str, *parts: bytes) -> str:
    h = hashlib.sha256()
    h.update(domain.encode("ascii"))
    h.update(b"\x00")
    for part in parts:
        h.update(len(part).to_bytes(8, "big"))
        h.update(part)
    return h.hexdigest()


def _quantize(value: float) -> float:
    # Keep receipts stable across harmless floating rendering differences.
    return round(float(value), 12)


def _tensor_digest(label: str, tensor: torch.Tensor) -> str:
    cpu = tensor.detach().to(device="cpu").contiguous()
    shape = _canonical_bytes(list(cpu.shape))
    dtype = str(cpu.dtype).encode("ascii")
    raw = cpu.numpy().tobytes()
    return _domain_hash(
        "AEGIS_PERSPECTIVE_STATE_V1",
        label.encode("utf-8"),
        dtype,
        shape,
        raw,
    )


def _projection_digest(projection: torch.Tensor) -> str:
    cpu = projection.detach().to(device="cpu", dtype=torch.float64).contiguous()
    return _domain_hash(
        "AEGIS_PERSPECTIVE_PROJECTION_V1",
        _canonical_bytes(list(cpu.shape)),
        cpu.numpy().tobytes(),
    )


def _energy_entropy_bits(projection: torch.Tensor) -> float:
    energy = projection.square()
    total = float(energy.sum().item())
    if total <= 0.0:
        return 0.0
    probs = (energy / total).clamp_min(1e-300)
    entropy = -(probs * torch.log2(probs)).sum()
    return _quantize(float(entropy.item()))


def _deterministic_basis(
    perspective_id: str,
    d_model: int,
    projection_dim: int,
) -> torch.Tensor:
    rows = []
    scale = float(2**64 - 1)
    for row in range(projection_dim):
        values = []
        for col in range(d_model):
            payload = (
                f"{perspective_id}\x00{d_model}\x00{projection_dim}\x00{row}\x00{col}"
            ).encode("utf-8")
            digest = hashlib.sha256(
                b"AEGIS_PERSPECTIVE_BASIS_V1\x00" + payload
            ).digest()
            unit = int.from_bytes(digest[:8], "big") / scale
            values.append((2.0 * unit) - 1.0)
        vector = torch.tensor(values, dtype=torch.float64)
        norm = float(vector.norm().item())
        if norm == 0.0:
            raise ValueError("DEGENERATE_PERSPECTIVE_BASIS")
        rows.append(vector / norm)
    return torch.stack(rows, dim=0)


@dataclass(frozen=True)
class PerspectiveFrameV1:
    label: str
    state_digest: str
    projection_digest: str
    projected_l2: float
    energy_entropy_bits: float
    chain_digest: str


@dataclass(frozen=True)
class PerspectiveTransitionV1:
    from_label: str
    to_label: str
    cosine_similarity: float
    angle_radians: float
    delta_l2: float
    commutative_residual_l2: float
    transition_preserved: bool
    transition_digest: str


@dataclass(frozen=True)
class PerspectiveTraceV1:
    trace_kind: str
    perspective_id: str
    epistemic_status: str
    mode: str
    readings: tuple[str, ...]
    d_model: int
    projection_dim: int
    tolerance: float
    frames: tuple[PerspectiveFrameV1, ...]
    transitions: tuple[PerspectiveTransitionV1, ...]
    trace_digest: str


class PerspectiveProbeV1:
    """Deterministic linear probe over a sequence of hidden states.

    The formal reading checks the commutative square for each transition:

        P(h_after - h_before) == P(h_after) - P(h_before)

    within ``tolerance``.  Because P is fixed and linear, a violation indicates a
    measurement/runtime defect, not model semantic failure.
    """

    def __init__(
        self,
        *,
        d_model: int,
        projection_dim: int = 8,
        perspective_id: str = "MYTHOS_PERSPECTIVE_V1",
        tolerance: float = 1e-8,
    ) -> None:
        if isinstance(d_model, bool) or d_model < 1:
            raise ValueError("INVALID_D_MODEL")
        if isinstance(projection_dim, bool) or not (1 <= projection_dim <= d_model):
            raise ValueError("INVALID_PROJECTION_DIMENSION")
        if not perspective_id:
            raise ValueError("PERSPECTIVE_ID_REQUIRED")
        if not math.isfinite(tolerance) or tolerance < 0.0:
            raise ValueError("INVALID_TOLERANCE")

        self.d_model = d_model
        self.projection_dim = projection_dim
        self.perspective_id = perspective_id
        self.tolerance = float(tolerance)
        self._basis = _deterministic_basis(
            perspective_id,
            d_model,
            projection_dim,
        )

    def _select_vector(self, tensor: torch.Tensor) -> torch.Tensor:
        if not isinstance(tensor, torch.Tensor):
            raise TypeError("HIDDEN_STATE_MUST_BE_TENSOR")
        if tensor.ndim < 1 or tensor.shape[-1] != self.d_model:
            raise ValueError("HIDDEN_DIMENSION_MISMATCH")
        if not bool(torch.isfinite(tensor).all().item()):
            raise ValueError("NON_FINITE_HIDDEN_STATE")

        # Perspective v1 observes the active/last token vector.  Full state bytes
        # are still bound by state_digest for forensic provenance.
        selected = tensor.detach().reshape(-1, self.d_model)[-1]
        return selected.to(device="cpu", dtype=torch.float64).clone()

    def _project(self, vector: torch.Tensor) -> torch.Tensor:
        return self._basis @ vector

    def observe(
        self,
        states: Sequence[tuple[str, torch.Tensor]],
    ) -> PerspectiveTraceV1:
        if not states:
            raise ValueError("EMPTY_PERSPECTIVE_TRAJECTORY")

        labels: list[str] = []
        vectors: list[torch.Tensor] = []
        projections: list[torch.Tensor] = []
        state_digests: list[str] = []

        for label, tensor in states:
            if not isinstance(label, str) or not label:
                raise ValueError("STATE_LABEL_REQUIRED")
            if label in labels:
                raise ValueError("DUPLICATE_STATE_LABEL")
            vector = self._select_vector(tensor)
            labels.append(label)
            vectors.append(vector)
            projections.append(self._project(vector))
            state_digests.append(_tensor_digest(label, tensor))

        frames: list[PerspectiveFrameV1] = []
        previous_chain = "0" * 64
        for label, state_digest, projection in zip(
            labels, state_digests, projections
        ):
            projection_digest = _projection_digest(projection)
            body = {
                "label": label,
                "state_digest": state_digest,
                "projection_digest": projection_digest,
                "projected_l2": _quantize(float(projection.norm().item())),
                "energy_entropy_bits": _energy_entropy_bits(projection),
            }
            chain_digest = _domain_hash(
                "AEGIS_PERSPECTIVE_FRAME_CHAIN_V1",
                previous_chain.encode("ascii"),
                _canonical_bytes(body),
            )
            frame = PerspectiveFrameV1(chain_digest=chain_digest, **body)
            frames.append(frame)
            previous_chain = chain_digest

        transitions: list[PerspectiveTransitionV1] = []
        for index in range(1, len(vectors)):
            before = vectors[index - 1]
            after = vectors[index]
            p_before = projections[index - 1]
            p_after = projections[index]

            direct_delta = self._project(after - before)
            composed_delta = p_after - p_before
            residual = float((direct_delta - composed_delta).norm().item())
            delta_l2 = float((after - before).norm().item())

            before_norm = float(p_before.norm().item())
            after_norm = float(p_after.norm().item())
            if before_norm == 0.0 and after_norm == 0.0:
                cosine = 1.0
            elif before_norm == 0.0 or after_norm == 0.0:
                cosine = 0.0
            else:
                cosine = float(
                    torch.dot(p_before, p_after).item()
                    / (before_norm * after_norm)
                )
                cosine = min(1.0, max(-1.0, cosine))
            angle = math.acos(cosine)

            body = {
                "from_label": labels[index - 1],
                "to_label": labels[index],
                "cosine_similarity": _quantize(cosine),
                "angle_radians": _quantize(angle),
                "delta_l2": _quantize(delta_l2),
                "commutative_residual_l2": _quantize(residual),
                "transition_preserved": residual <= self.tolerance,
            }
            transition_digest = _domain_hash(
                "AEGIS_PERSPECTIVE_TRANSITION_V1",
                state_digests[index - 1].encode("ascii"),
                state_digests[index].encode("ascii"),
                _canonical_bytes(body),
            )
            transitions.append(
                PerspectiveTransitionV1(
                    transition_digest=transition_digest,
                    **body,
                )
            )

        trace_body = {
            "trace_kind": "PERSPECTIVE_TRACE_V1",
            "perspective_id": self.perspective_id,
            "epistemic_status": "EVIDENCE_ONLY_NOT_AUTHORITY",
            "mode": "OBSERVATION_ONLY",
            "readings": READINGS,
            "d_model": self.d_model,
            "projection_dim": self.projection_dim,
            "tolerance": self.tolerance,
            "frames": [asdict(frame) for frame in frames],
            "transitions": [asdict(item) for item in transitions],
        }
        trace_digest = _domain_hash(
            "AEGIS_PERSPECTIVE_TRACE_V1",
            _canonical_bytes(trace_body),
        )

        return PerspectiveTraceV1(
            trace_digest=trace_digest,
            frames=tuple(frames),
            transitions=tuple(transitions),
            **trace_body,
        )
