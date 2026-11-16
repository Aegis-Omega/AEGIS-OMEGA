"""V15 V2.0 / V2.1 M1 capacity relocation: executable independent checks.

These tests do not update a checkpoint or run product migration. They check
the mathematical digest-transfer invariant against a second reference ring
implementation and reject incompatible or forged-by-accident checkpoints.
The unkeyed SHA256 checksum cannot authenticate a checkpoint's author.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
import unittest
from copy import deepcopy
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from m1_checkpoint_portability import (
    CHAIN_MODE, HEADER_BYTES, PortabilityError, STATE_CONTRACT,
    U64_LIMIT, ZERO_HEADER, MAX_CHECKPOINT_JSON_BYTES, next_digest_from_anchor,
    parse_checkpoint_json, plan_chain_relocation, validate_chain_checkpoint,
    _canonical,
)


def reference_append(ring: bytearray, sequence: int, payload: bytes):
    """Independent on-wire form matching PR #806 and #810's M1 protocol."""
    slots = len(ring) // HEADER_BYTES
    assert slots > 0
    if sequence:
        pos = ((sequence - 1) % slots) * HEADER_BYTES
        previous = bytes(ring[pos:pos + HEADER_BYTES])
        assert int.from_bytes(previous[:8], "little") == sequence - 1
        digest = previous[8:]
    else:
        digest = b"\x00" * 32
    candidate = hashlib.sha256(digest + hashlib.sha256(payload).digest()).digest()
    pos = (sequence % slots) * HEADER_BYTES
    ring[pos:pos + HEADER_BYTES] = sequence.to_bytes(8, "little") + candidate
    return candidate


def make_body(sequence: int, slots: int, header: bytes, version="2.0.0"):
    body = {
        "checkpoint_version": version,
        "chain_mode": CHAIN_MODE,
        "sequence": sequence,
        "epoch": sequence // 100,
        "era": sequence // slots,
        "m1_capacity_slots": slots,
        "last_m1_entry_hex": header.hex(),
        "is_replay_reconstructable": False,
        "is_chain_continuation_supported": True,
    }
    if version == "2.1.0":
        body.update(
            state_contract=STATE_CONTRACT,
            total_processed=sequence,
            total_verified=min(sequence, 10),
            total_vcg_error_fixed=0,
            last_gate_signal_sequence=-1,
            last_gate_signal_accepted=None,
        )
    return signed(body)


def signed(body):
    body = deepcopy(body)
    body.pop("integrity_hash", None)
    body["integrity_hash"] = hashlib.sha256(json.dumps(
        body, sort_keys=True, ensure_ascii=False, separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")).hexdigest()
    return body


def checkpoint_after(messages: list[bytes], slots: int, version: str):
    ring = bytearray(slots * HEADER_BYTES)
    last = ZERO_HEADER
    for sequence, payload in enumerate(messages):
        reference_append(ring, sequence, payload)
        at = ((sequence % slots) * HEADER_BYTES)
        last = bytes(ring[at:at + HEADER_BYTES])
    return make_body(len(messages), slots, last, version), ring


class RelocationProtocolTests(unittest.TestCase):
    def test_cross_geometry_chain_hash_is_exact(self):
        rng = random.Random(10072026)
        for source_slots in (1, 2, 3, 5, 17):
            for length in (0, 1, 2, 3, 12, 29, 130):
                messages = [bytes(rng.randrange(256) for _ in range(i%19))
                            for i in range(length)]
                for version in ("2.0.0", "2.1.0"):
                    cp, ring = checkpoint_after(messages, source_slots, version)
                    if messages:
                        previous = hashlib.sha256(messages[0]).digest()
                    else:
                        previous = bytes(32)
                    _ = ring
                    for target_slots in (1, 2, 4, 11, 43):
                        plan = plan_chain_relocation(cp, target_slots)
                        self.assertEqual(plan.sequence, length)
                        self.assertEqual(plan.source_slots, source_slots)
                        self.assertEqual(plan.target_slots, target_slots)
                        self.assertFalse(plan.runtime_checkpoint_admitted)
                        self.assertFalse(plan.full_history_reconstructable)
                        relocated = bytearray(target_slots * HEADER_BYTES)
                        if plan.destination_offset is not None:
                            relocated[plan.destination_offset:
                                      plan.destination_offset + HEADER_BYTES] = bytes.fromhex(plan.anchor_hex)
                        payload = ("next:" + str(length)).encode()
                        predicted = next_digest_from_anchor(plan, payload)
                        observed = reference_append(relocated, length, payload)
                        self.assertEqual(predicted, observed.hex())
                        # Independently reconstruct the full chain from history.
                        control = bytearray(source_slots * HEADER_BYTES)
                        for seq, msg in enumerate(messages):
                            reference_append(control, seq, msg)
                        continuous = reference_append(control, length, payload)
                        self.assertEqual(observed, continuous)

    def test_genesis_and_last_sequence_no_further_append(self):
        for version in ("2.0.0", "2.1.0"):
            cp = make_body(0, 1, ZERO_HEADER, version)
            p = plan_chain_relocation(cp, 4)
            self.assertIsNone(p.destination_offset)
            self.assertEqual(next_digest_from_anchor(p, b"alpha"), hashlib.sha256(
                bytes(32) + hashlib.sha256(b"alpha").digest()
            ).hexdigest())
            last_header = (U64_LIMIT - 2).to_bytes(8, "little") + bytes([1])*32
            final = make_body(U64_LIMIT - 1, 3, last_header, version)
            final_plan = plan_chain_relocation(final, 1)
            self.assertEqual(final_plan.sequence, U64_LIMIT - 1)
            with self.assertRaises(PortabilityError):
                next_digest_from_anchor(final_plan, b"not-allowed")
            too_large = make_body(U64_LIMIT, 3, last_header, version)
            with self.assertRaises(PortabilityError):
                validate_chain_checkpoint(too_large)

    def test_tampered_or_wrong_provenance_fails_closed(self):
        cp, _ = checkpoint_after([b"one", b"two", b"three"], 3, "2.0.0")
        for key, value in (
            ("sequence", 100), ("last_m1_entry_hex", "0"*80),
            ("m1_capacity_slots", 10), ("checkpoint_version", "1.0.0"),
            ("chain_mode", "unsupported"), ("is_replay_reconstructable", True),
            ("is_chain_continuation_supported", False),
        ):
            mutated = deepcopy(cp)
            mutated[key] = value
            with self.assertRaises(PortabilityError, msg=key):
                plan_chain_relocation(mutated, 2)

        for key, value in (
            ("checkpoint_version", "1.0.0"), ("chain_mode", "unsupported"),
            ("last_m1_entry_hex", (123).to_bytes(40, "little").hex()),
            ("sequence", -1), ("epoch", -1), ("era", True),
            ("m1_capacity_slots", 0), ("is_replay_reconstructable", True),
        ):
            mutated = signed({**cp, key:value})
            with self.assertRaises(PortabilityError, msg=key):
                plan_chain_relocation(mutated, 2)

    def test_v21_calibration_contract_is_not_reconstructed(self):
        cp, _ = checkpoint_after([b"a", b"b"], 3, "2.1.0")
        for key, value in (
            ("state_contract", "invalid"),
            ("total_processed", 10), ("total_verified", 100),
            ("total_vcg_error_fixed", 20000000),
            ("last_gate_signal_sequence", False),
            ("last_gate_signal_accepted", "true"),
        ):
            bad = signed({**cp, key:value})
            with self.assertRaises(PortabilityError, msg=key):
                validate_chain_checkpoint(bad)
        with self.assertRaises(PortabilityError):
            plan_chain_relocation(cp, 0)
        with self.assertRaises(PortabilityError):
            plan_chain_relocation(cp, True)
        with self.assertRaises(PortabilityError):
            plan_chain_relocation(cp, -2)

    def test_unkeyed_checksum_is_not_authentication(self):
        cp, _ = checkpoint_after([b"alpha", b"beta"], 4, "2.0.0")
        # Attacker with write access can replace a valid digest and recompute
        # unkeyed SHA256; schema consistency is not actor/source authentication.
        forged = signed({
            **cp,
            "last_m1_entry_hex": (1).to_bytes(8, "little").hex() + "34"*32,
        })
        p = plan_chain_relocation(forged, 4)
        self.assertNotEqual(p.anchor_digest_hex, cp["last_m1_entry_hex"][16:])
        self.assertFalse(p.runtime_checkpoint_admitted)

    def test_strict_reader_accepts_exact_v20_and_v21_bytes(self):
        for version in ("2.0.0", "2.1.0"):
            cp, _ = checkpoint_after([b"alpha", b"beta"], 3, version)
            raw = json.dumps(cp, sort_keys=True, ensure_ascii=False,
                             separators=(",", ":"), allow_nan=False).encode("utf-8")
            loaded = parse_checkpoint_json(raw)
            self.assertEqual(loaded, cp)
            self.assertEqual(plan_chain_relocation(loaded, 7).target_slots, 7)

    def test_strict_reader_rejects_duplicate_keys_including_escaped_alias(self):
        cp, _ = checkpoint_after([b"alpha"], 2, "2.0.0")
        raw = json.dumps(cp, sort_keys=True, separators=(",", ":")).encode("utf-8")
        for duplicate in (
            b'{"sequence":1,' + raw[1:],
            b'{"\\u0073equence":1,' + raw[1:],
            b'{"x":{"nested":1,"nested":2}}',
        ):
            with self.assertRaises(PortabilityError):
                parse_checkpoint_json(duplicate)

    def test_strict_reader_rejects_noncanonical_shapes_and_numeric_domains(self):
        cp, _ = checkpoint_after([b"alpha"], 2, "2.0.0")
        for invalid in (
            b'{"checkpoint_version":[]}', b'{"checkpoint_version":{}}',
            b'{"checkpoint_version":null}', b'{"x":1.25}',
            b'{"x":1e100}', b'{"x":NaN}', b'{"x":Infinity}',
            b'{"x":-Infinity}', b'{"x":123456789012345678901}',
            b"[]", b"null", b"\\xff", b"\\xef\\xbb\\xbf{}",
            b" " * (MAX_CHECKPOINT_JSON_BYTES + 1),
            b"[" * 1030 + b"0" + b"]" * 1030,
        ):
            with self.assertRaises(PortabilityError, msg=repr(invalid[:90])):
                parse_checkpoint_json(invalid)
        with self.assertRaises(PortabilityError):
            parse_checkpoint_json("not-bytes")
        # A valid hash does not authorize unknown fields or foreign versions.
        for bad in (
            signed({**cp, "unexpected": 7}),
            signed({**cp, "checkpoint_version": []}),
            signed({**cp, "checkpoint_version": {}}),
        ):
            raw = json.dumps(bad, separators=(",", ":"), ensure_ascii=False).encode()
            with self.assertRaises(PortabilityError):
                parse_checkpoint_json(raw)

    def test_unicode_and_non_string_field_types_are_fail_closed(self):
        # Non-UTF8 and unpaired surrogates do not become uncaught exceptions.
        with self.assertRaises(PortabilityError):
            _canonical({"x": "\ud800"})
        cp, _ = checkpoint_after([b"x"], 2, "2.0.0")
        with self.assertRaises(PortabilityError):
            validate_chain_checkpoint(signed({**cp, "checkpoint_version": []}))
        with self.assertRaises(PortabilityError):
            validate_chain_checkpoint(signed({**cp, "checkpoint_version": {}}))

    def test_canonical_hash_rejects_duplicate_or_malformed_fields(self):
        cp, _ = checkpoint_after([b"x"], 1, "2.0.0")
        for bad in [True, "", 3.0, None]:
            damaged = signed({**cp, "sequence":bad})
            with self.assertRaises(PortabilityError):
                validate_chain_checkpoint(damaged)
        with self.assertRaises(PortabilityError):
            next_digest_from_anchor(plan_chain_relocation(cp,1), "not-bytes")


if __name__ == "__main__":
    unittest.main()
