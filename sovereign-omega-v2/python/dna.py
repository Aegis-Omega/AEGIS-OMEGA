"""
SOVEREIGN OMEGA — DNA: Genome and Schema
EPISTEMIC TIER: T0 (constitutional — frozen after creation)

The canonical source of truth for all Python-layer type definitions.
Immutable after import. All other Python modules import shared types from here.

Role: genome/schema — every data structure, constant, and invariant declaration
      for Layer B lives here. Analogous to src/core/types.ts in Layer A.

Non-equivalence (from CLAUDE.md):
  Replayability is not Correctness.
  Calibration is not Truthfulness.
  Governance is not Alignment.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Final, Optional, Tuple


# ── Version ───────────────────────────────────────────────────────────────────

VERSION: Final[str] = "0.5.3"
LAYER: Final[str] = "B"          # Python hardware inference layer
EPISTEMIC_TIER: Final[str] = "T0"


# ── Event Classification ──────────────────────────────────────────────────────

class EventClass(Enum):
    """
    Four canonical event classes for the Python routing layer.
    Verifier byte 0x00–0x03 maps to these classes in router.py.
    """
    GOVERNANCE  = "governance"   # 0x00 — E3 substrate mutations, gate signals
    CALIBRATION = "calibration"  # 0x01 — VCG / AFSE / TGCS calibration events
    TELEMETRY   = "telemetry"    # 0x02 — read-only telemetry queries
    EPOCH       = "epoch"        # 0x03 — epoch snapshot and failsafe signals


# ── Mutation Verdicts ─────────────────────────────────────────────────────────

class MutationVerdict(Enum):
    """Verdict issued by MutationGate in gate.py."""
    PENDING  = "pending"   # not enough signals to decide
    APPROVED = "approved"  # acceptance rate >= threshold
    REJECTED = "rejected"  # acceptance rate < threshold
    EXPIRED  = "expired"   # proposal_id exceeded retention window


# ── Immutable Data Structures ─────────────────────────────────────────────────

@dataclass(frozen=True)
class GateSignal:
    """
    A single gate signal from the TypeScript Bernstein gate (via bridge.py /gate_signal).
    sequence must be strictly monotonically increasing across all signals.
    lcb is the lower confidence bound from the anytime-valid Bernstein sequence.
    Gate accepts when lcb > 0.
    """
    proposal_id: str
    sequence: int
    accepted: bool
    lcb: float              # lower confidence bound — informational, not re-validated here


@dataclass(frozen=True)
class EventSchema:
    """
    Declared size bounds for each event class.
    Payloads exceeding these bounds are rejected at the routing layer.
    """
    event_class: EventClass
    payload_size_max: int   # bytes
    verifier_size_max: int  # bytes
    context_size_max: int   # bytes


@dataclass(frozen=True)
class RouteRecord:
    """Immutable record of a single routing decision — used for audit trail."""
    sequence: int
    event_class: EventClass
    verifier_byte: int
    payload_size: int
    outcome: str            # "ROUTED" | "REJECTED" | "ERROR"
    reason: Optional[str]   # set only on REJECTED or ERROR


# ── Event Schema Registry (sealed at module load) ─────────────────────────────

SCHEMAS: Final[dict] = {
    EventClass.GOVERNANCE:  EventSchema(EventClass.GOVERNANCE,  65536, 256, 4096),
    EventClass.CALIBRATION: EventSchema(EventClass.CALIBRATION,  4096,  64,  512),
    EventClass.TELEMETRY:   EventSchema(EventClass.TELEMETRY,    1024,   8,    0),
    EventClass.EPOCH:       EventSchema(EventClass.EPOCH,         512,  32,  128),
}

# Verifier-byte → EventClass mapping (fail-closed: unknown byte → None → REJECTED)
VERIFIER_MAP: Final[dict] = {
    0x00: EventClass.GOVERNANCE,
    0x01: EventClass.CALIBRATION,
    0x02: EventClass.TELEMETRY,
    0x03: EventClass.EPOCH,
}


# ── Invariant Declarations ────────────────────────────────────────────────────

INVARIANTS: Final[Tuple[str, ...]] = (
    "no_wall_clock_in_determinism_paths",
    "bit_shifted_arithmetic_throughout",
    "pgcs_must_pass_before_tgcs",
    "epoch_corruption_count_equals_zero",
    "gate_signals_strictly_monotonically_increasing",
    "router_sealed_before_first_route",
    "mutation_gate_rejects_out_of_order_signals",
)


# ── Telemetry Schema (emitted by CoreMatrix.emit_vcg_telemetry) ───────────────

TELEMETRY_FIELDS: Final[Tuple[str, ...]] = (
    "pgcs_disk_swap_bytes_in",
    "pgcs_disk_swap_bytes_out",
    "pgcs_passes",
    "tgcs_variance",
    "tgcs_cycles",
    "afse_r2",
    "afse_samples",
    "epoch_state",
    "epoch_id",
    "corruption_count",
    "drift_index",
    "sequence",
    "era",
)
