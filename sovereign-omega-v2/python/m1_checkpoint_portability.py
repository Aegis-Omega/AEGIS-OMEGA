"""Read-only V2 M1 checkpoint relocation preflight.

A chain continuation anchor is invariant under a change in circular-ring
capacity: the next SHA256 depends on the last chain digest, not on where its
40-byte header was stored. This module NEVER writes an archive or a live
matrix. It does not certify provenance, full event replay, or production
migration. V1 payload-digest checkpoints are deliberately forbidden.

Source contracts: PR #806 (checkpoint 2.0.0) and the stacked PR #810
(checkpoint 2.1.0). Their M1 digest algorithm is identical; calibration
state contracts differ and MUST be handled by a separate authorized loader.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from hmac import compare_digest
import json
import re

HEADER_BYTES = 40
ZERO_HEADER = b"\x00" * HEADER_BYTES
CHAIN_MODE = "sha256-prev-chain-plus-sha256-payload-v2"
STATE_CONTRACT = "m123-calibration-counters-v1"
VERSIONS = frozenset(("2.0.0", "2.1.0"))
U64_LIMIT = 1 << 64
_Q16 = 1 << 16


class PortabilityError(ValueError):
    """Refuse ambiguous, malformed or incompatible chain inputs."""


def _exact_uint(value, name: str, upper: int | None = None) -> int:
    if type(value) is not int or value < 0 or (upper is not None and value >= upper):
        raise PortabilityError("INVALID_" + name.upper())
    return value


def _canonical(obj) -> bytes:
    try:
        return json.dumps(
            obj, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError, OverflowError) as exc:
        raise PortabilityError("NONCANONICAL_CHECKPOINT") from exc


@dataclass(frozen=True)
class ChainRelocationPlan:
    checkpoint_version: str
    sequence: int
    source_slots: int
    target_slots: int
    destination_offset: int | None
    anchor_hex: str
    anchor_digest_hex: str
    # Only the M1 digest can be relocated with this proof.
    runtime_checkpoint_admitted: bool = False
    full_history_reconstructable: bool = False


def validate_chain_checkpoint(body: dict) -> tuple[str, int, int, bytes]:
    """Validate historical V2 source schema, checksum and exact final header.

    An unkeyed checksum protects against accidental corruption only. Even a
    valid checkpoint requires an externally authenticated source/receipt.
    """
    if type(body) is not dict:
        raise PortabilityError("CHECKPOINT_NOT_OBJECT")
    version = body.get("checkpoint_version")
    if version not in VERSIONS or type(version) is not str:
        raise PortabilityError("UNSUPPORTED_CHECKPOINT_VERSION")
    if body.get("chain_mode") != CHAIN_MODE:
        raise PortabilityError("INCOMPATIBLE_CHAIN_MODE")
    if body.get("is_replay_reconstructable") is not False:
        raise PortabilityError("FALSE_HISTORICAL_REPLAY_CLAIM")
    if body.get("is_chain_continuation_supported") is not True:
        raise PortabilityError("MISSING_CHAIN_CONTRACT")

    integrity = body.get("integrity_hash")
    if type(integrity) is not str or re.fullmatch("[0-9a-f]{64}", integrity) is None:
        raise PortabilityError("INVALID_INTEGRITY_FIELD")
    canonical_fields = {key: val for key, val in body.items() if key != "integrity_hash"}
    expected = sha256(_canonical(canonical_fields)).hexdigest()
    if not compare_digest(integrity, expected):
        raise PortabilityError("CHECKPOINT_CHECKSUM_MISMATCH")

    sequence = _exact_uint(body.get("sequence"), "sequence", U64_LIMIT - 1)
    source_slots = _exact_uint(body.get("m1_capacity_slots"), "source_slots")
    if not source_slots:
        raise PortabilityError("SOURCE_CAPACITY_ZERO")
    _exact_uint(body.get("epoch"), "epoch")
    _exact_uint(body.get("era"), "era")
    raw_hex = body.get("last_m1_entry_hex")
    if type(raw_hex) is not str or re.fullmatch("[0-9a-f]{80}", raw_hex) is None:
        raise PortabilityError("INVALID_ANCHOR_HEX")
    header = bytes.fromhex(raw_hex)
    if sequence == 0:
        if header != ZERO_HEADER:
            raise PortabilityError("NONZERO_GENESIS_HEADER")
    else:
        if int.from_bytes(header[:8], "little") != sequence - 1:
            raise PortabilityError("ANCHOR_SEQUENCE_MISMATCH")
        if header[8:] == b"\x00" * 32:
            raise PortabilityError("MISSING_CHAIN_DIGEST")

    if version == "2.1.0":
        if body.get("state_contract") != STATE_CONTRACT:
            raise PortabilityError("UNKNOWN_CALIBRATION_CONTRACT")
        processed = _exact_uint(body.get("total_processed"), "total_processed")
        verified = _exact_uint(body.get("total_verified"), "total_verified")
        error = _exact_uint(body.get("total_vcg_error_fixed"), "total_vcg_error_fixed")
        if processed != sequence or verified > processed or error > verified * _Q16:
            raise PortabilityError("CALIBRATION_COUNTERS_INCONSISTENT")
        last = body.get("last_gate_signal_sequence")
        accepted = body.get("last_gate_signal_accepted")
        if type(last) is not int or last < -1:
            raise PortabilityError("INVALID_GATE_SEQUENCE")
        if accepted is not None and type(accepted) is not bool:
            raise PortabilityError("INVALID_GATE_OUTCOME")
    return version, sequence, source_slots, header


def plan_chain_relocation(checkpoint: dict, target_slots: int) -> ChainRelocationPlan:
    """Return a pure verified header-placement plan, never execute it.

    target_slots > 0 is the destination's real number of whole 40-byte slots.
    The plan does NOT permit rewriting checkpoint capacity or automatic
    checkpoint admission. It deliberately preserves the source capacity.
    """
    _exact_uint(target_slots, "target_slots")
    if target_slots == 0:
        raise PortabilityError("DESTINATION_CAPACITY_ZERO")
    version, seq, slots, header = validate_chain_checkpoint(checkpoint)
    return ChainRelocationPlan(
        checkpoint_version=version,
        sequence=seq,
        source_slots=slots,
        target_slots=target_slots,
        destination_offset=((seq - 1) % target_slots) * HEADER_BYTES if seq else None,
        anchor_hex=header.hex(),
        anchor_digest_hex=header[8:].hex() if seq else (b"\x00" * 32).hex(),
    )


def next_digest_from_anchor(plan: ChainRelocationPlan, payload: bytes) -> str:
    """Algebraic M1 formula used identically by PR #806 / #810."""
    if type(payload) is not bytes:
        raise PortabilityError("PAYLOAD_MUST_BE_BYTES")
    if type(plan) is not ChainRelocationPlan or plan.sequence >= U64_LIMIT - 1:
        raise PortabilityError("INVALID_PLAN")
    previous = bytes.fromhex(plan.anchor_digest_hex)
    return sha256(previous + sha256(payload).digest()).hexdigest()
