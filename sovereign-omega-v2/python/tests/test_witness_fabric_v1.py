#!/usr/bin/env python3
"""AEGIS always-on witness fabric v1 contract tests."""
from __future__ import annotations

import hashlib
import json
import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main

PYTHON_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PYTHON_ROOT))

from witness_fabric import (  # noqa: E402
    AUTHORITY_EFFECT,
    CLASSICAL_ABJAD_WEIGHTS,
    FIELD_MODULUS,
    WitnessFabric,
    abjad_projection,
    affine_combine,
    affine_state,
    build_receipt,
    canonical_payload_bytes,
    decode_bytes_field101,
    encode_bytes_field101,
    field101_eval,
    structure_commitment,
)


class WitnessFabricV1Tests(TestCase):
    def test_canonical_json_encoding_is_order_independent(self) -> None:
        left = {"b": [2, 3], "a": {"x": True}}
        right = {"a": {"x": True}, "b": [2, 3]}
        l_bytes, l_profile = canonical_payload_bytes(left)
        r_bytes, r_profile = canonical_payload_bytes(right)
        self.assertEqual(l_profile, "AEGIS_WITNESS_JSON_V1")
        self.assertEqual(l_profile, r_profile)
        self.assertEqual(l_bytes, r_bytes)

    def test_field101_byte_pair_encoding_is_lossless_for_all_bytes(self) -> None:
        payload = bytes(range(256))
        coeffs = encode_bytes_field101(payload)
        self.assertEqual(len(coeffs), 512)
        self.assertTrue(all(0 <= c < FIELD_MODULUS for c in coeffs))
        self.assertEqual(decode_bytes_field101(coeffs), payload)

    def test_affine_state_is_partition_invariant(self) -> None:
        coeffs = encode_bytes_field101(b"AEGIS witness fabric / sequence")
        for point in (0, 1, 35, 100):
            whole = affine_state(coeffs, point)
            for cut in (0, 1, 7, len(coeffs) // 2, len(coeffs)):
                left = affine_state(coeffs[:cut], point)
                right = affine_state(coeffs[cut:], point)
                self.assertEqual(affine_combine(left, right), whole)

    def test_field101_eval_at_one_is_additive_sum(self) -> None:
        coeffs = [1, 2, 3, 100]
        self.assertEqual(field101_eval(coeffs, 1), sum(coeffs) % FIELD_MODULUS)

    def test_classical_abjad_symbols_are_injective_mod101(self) -> None:
        residues = [w % FIELD_MODULUS for w in CLASSICAL_ABJAD_WEIGHTS]
        self.assertEqual(len(residues), 28)
        self.assertEqual(len(set(residues)), 28)
        self.assertNotIn(0, residues)

    def test_abjad_projection_preserves_cross_profile_z10(self) -> None:
        ys = abjad_projection("يس")
        kn = abjad_projection("كن")
        self.assertIsNotNone(ys)
        self.assertIsNotNone(kn)
        assert ys is not None and kn is not None
        self.assertEqual(ys["mashriqi_sum"], 70)
        self.assertEqual(ys["maghribi_sum"], 310)
        self.assertEqual(kn["mashriqi_sum"], 70)
        self.assertEqual(kn["maghribi_sum"], 70)
        self.assertEqual(ys["common_z10"], 0)
        self.assertEqual(kn["common_z10"], 0)
        self.assertEqual(
            ys["field101"]["evaluation_at_1"],
            ys["mashriqi_sum"] % FIELD_MODULUS,
        )
        # Same coarse sum/quotient must not collapse the stronger sequence witness.
        self.assertNotEqual(
            ys["field101"]["coefficients"],
            kn["field101"]["coefficients"],
        )

    def test_abjad_projection_refuses_mixed_or_normalized_input(self) -> None:
        self.assertIsNone(abjad_projection("abc"))
        self.assertIsNone(abjad_projection("ابج!"))
        # Whitespace is the only ignored separator in V1.
        self.assertEqual(
            abjad_projection("ي س")["canonical_letters"],
            ["ي", "س"],
        )

    def test_structure_commitment_tracks_shape_not_scalar_values(self) -> None:
        left = {"a": 1, "b": ["x", "y"], "c": {"ok": True}}
        right = {"a": 999, "b": ["u", "v"], "c": {"ok": False}}
        different = {"a": 999, "b": ["u"], "c": {"ok": False}}
        self.assertEqual(
            structure_commitment(left)["sha256"],
            structure_commitment(right)["sha256"],
        )
        self.assertNotEqual(
            structure_commitment(left)["sha256"],
            structure_commitment(different)["sha256"],
        )

    def test_receipt_binds_coding_structure_meaning_and_lineage_without_authority(self) -> None:
        payload = {"message": "سلام", "values": [1, 2, 3]}
        first = build_receipt(
            kind="model_message",
            payload=payload,
            sequence=0,
            prev_receipt_hash="0" * 64,
            timestamp_ns=123,
            meaning={
                "ontology": "AEGIS_TEST_ONTOLOGY_V1",
                "claim": "typed test meaning",
                "context_refs": ["ctx:1"],
            },
            provenance={"source": "unit-test"},
        )
        second = build_receipt(
            kind="model_message",
            payload=payload,
            sequence=1,
            prev_receipt_hash=first["receipt_sha256"],
            timestamp_ns=124,
            meaning={
                "ontology": "AEGIS_TEST_ONTOLOGY_V1",
                "claim": "typed test meaning",
                "context_refs": ["ctx:2"],
            },
            provenance={"source": "unit-test"},
        )
        self.assertEqual(first["authority_effect"], AUTHORITY_EFFECT)
        self.assertEqual(first["authority_effect"], "NONE")
        self.assertEqual(second["prev_receipt_hash"], first["receipt_sha256"])
        self.assertNotEqual(
            first["meaning"]["commitment_sha256"],
            second["meaning"]["commitment_sha256"],
        )
        self.assertNotEqual(first["receipt_sha256"], second["receipt_sha256"])

    def test_receipt_does_not_embed_raw_payload(self) -> None:
        secret = "raw-payload-must-not-be-persisted"
        receipt = build_receipt(
            kind="privacy_probe",
            payload={"secret": secret},
            sequence=0,
            prev_receipt_hash="0" * 64,
            timestamp_ns=1,
        )
        self.assertNotIn(secret, json.dumps(receipt, ensure_ascii=False))

    def test_background_worker_persists_hash_chain_and_resolves_short_carrier(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "witness.jsonl"
            fabric = WitnessFabric(path=path, max_queue=8, recent_limit=8)
            fabric.start()
            try:
                self.assertTrue(fabric.submit("alpha", {"x": 1}))
                self.assertTrue(fabric.submit("beta", {"x": 2}))
                self.assertTrue(fabric.wait_idle(timeout=2.0))
                status = fabric.status()
                self.assertEqual(status["processed"], 2)
                self.assertEqual(status["dropped"], 0)
                self.assertTrue(status["continuity_intact"])

                lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
                self.assertEqual(len(lines), 2)
                self.assertEqual(lines[1]["prev_receipt_hash"], lines[0]["receipt_sha256"])

                carrier = lines[0]["coding"]["short_carrier"]
                self.assertGreaterEqual(len(carrier), 12)
                self.assertIn("compact_fingerprint", lines[0]["coding"]["field101"])
                resolution = fabric.resolve_carrier(carrier)
                self.assertEqual(resolution["status"], "RESOLVED")
                self.assertEqual(resolution["receipt_hashes"], [lines[0]["receipt_sha256"]])
            finally:
                fabric.stop(timeout=2.0)

    def test_short_carrier_is_cryptographic_locator_not_field101_fingerprint(self) -> None:
        receipt = build_receipt(
            kind="carrier_probe",
            payload={"x": 1, "y": [2, 3]},
            sequence=0,
            prev_receipt_hash="0" * 64,
            timestamp_ns=1,
        )
        carrier = receipt["coding"]["short_carrier"]
        fingerprint = receipt["coding"]["field101"]["compact_fingerprint"]
        self.assertGreaterEqual(len(carrier), 12)
        self.assertNotEqual(carrier, fingerprint)
        self.assertEqual(receipt["coding"]["carrier_role"], "LOOKUP_ONLY_NOT_PROOF")
        self.assertEqual(receipt["coding"]["collision_policy"], "AMBIGUOUS_FAIL_CLOSED")

    def test_short_carrier_collision_is_ambiguous_not_silently_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fabric = WitnessFabric(path=Path(td) / "witness.jsonl", max_queue=2, recent_limit=2)
            fabric._carrier_index["COLLIDE"] = ["a" * 64, "b" * 64]
            resolution = fabric.resolve_carrier("COLLIDE")
            self.assertEqual(resolution["status"], "AMBIGUOUS")
            self.assertEqual(len(resolution["receipt_hashes"]), 2)

    def test_background_worker_recovers_persisted_tail_across_restart(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "witness.jsonl"
            first = WitnessFabric(path=path, max_queue=8, recent_limit=8)
            first.start()
            try:
                self.assertTrue(first.submit("one", {"n": 1}))
                self.assertTrue(first.submit("two", {"n": 2}))
                self.assertTrue(first.wait_idle(timeout=2.0))
            finally:
                first.stop(timeout=2.0)

            before = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            second = WitnessFabric(path=path, max_queue=8, recent_limit=8)
            second.start()
            try:
                status = second.status()
                self.assertTrue(status["tail_recovered"])
                self.assertTrue(status["history_replay_verified"])
                self.assertEqual(status["recovered_receipts"], 2)
                self.assertEqual(status["next_sequence"], 2)
                self.assertEqual(status["terminal_hash"], before[-1]["receipt_sha256"])
                old_carrier = before[0]["coding"]["short_carrier"]
                self.assertEqual(
                    second.resolve_carrier(old_carrier)["receipt_hashes"],
                    [before[0]["receipt_sha256"]],
                )
                self.assertTrue(second.submit("three", {"n": 3}))
                self.assertTrue(second.wait_idle(timeout=2.0))
            finally:
                second.stop(timeout=2.0)

            after = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len(after), 3)
            self.assertEqual(after[2]["sequence"], 2)
            self.assertEqual(after[2]["prev_receipt_hash"], before[-1]["receipt_sha256"])

    def test_restart_replay_rejects_rehashed_but_broken_prev_link(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "witness.jsonl"
            fabric = WitnessFabric(path=path, max_queue=8, recent_limit=8)
            fabric.start()
            try:
                for n in range(3):
                    self.assertTrue(fabric.submit("chain", {"n": n}))
                self.assertTrue(fabric.wait_idle(timeout=2.0))
            finally:
                fabric.stop(timeout=2.0)

            lines = [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines()]
            lines[1]["prev_receipt_hash"] = "f" * 64
            body = dict(lines[1])
            body.pop("receipt_sha256")
            canonical = json.dumps(
                body,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
                allow_nan=False,
            ).encode("utf-8")
            lines[1]["receipt_sha256"] = hashlib.sha256(canonical).hexdigest()
            path.write_text(
                "\n".join(
                    json.dumps(x, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    for x in lines
                ) + "\n",
                encoding="utf-8",
            )

            replay = WitnessFabric(path=path, max_queue=8, recent_limit=8)
            replay.start()
            try:
                status = replay.status()
                self.assertFalse(status["continuity_intact"])
                self.assertFalse(status["history_replay_verified"])
                self.assertEqual(status["blocked_reason"], "PERSISTED_CHAIN_INVALID")
                self.assertFalse(replay.submit("must-not-append", {"x": 1}))
            finally:
                replay.stop(timeout=2.0)

    def test_structure_commitment_supports_non_string_python_keys(self) -> None:
        receipt = build_receipt(
            kind="python_mapping",
            payload={1: {"nested": True}},
            sequence=0,
            prev_receipt_hash="0" * 64,
            timestamp_ns=1,
        )
        self.assertTrue(receipt["structure"]["complete"])
        self.assertEqual(receipt["structure"]["node_count"], 3)

    def test_bridge_wires_witness_as_default_background_lifecycle(self) -> None:
        bridge = (PYTHON_ROOT / "bridge.py").read_text(encoding="utf-8")
        self.assertIn("from witness_fabric import WitnessFabric", bridge)
        self.assertIn("_witness = WitnessFabric()", bridge)
        self.assertIn("_witness.start()", bridge)
        self.assertIn("_witness.stop(", bridge)
        self.assertIn("_witness_observe('gate_signal'", bridge)
        self.assertIn("_witness_observe('event'", bridge)
        self.assertIn("_witness_observe('claude_response'", bridge)
        self.assertIn("_witness_observe('claude_stream_response'", bridge)
        self.assertIn("_witness_observe('platform_collaboration'", bridge)
        self.assertIn("elif self.path.startswith('/witness'):", bridge)
        self.assertIn("'history_replay_verified': status['history_replay_verified']", bridge)
        self.assertIn("'witness': _witness_public_status()", bridge)


if __name__ == "__main__":
    main()
