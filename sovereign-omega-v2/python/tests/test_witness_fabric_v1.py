#!/usr/bin/env python3
"""AEGIS always-on witness fabric v1 contract tests."""
from __future__ import annotations

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

                carrier = lines[0]["coding"]["field101"]["short_carrier"]
                resolution = fabric.resolve_carrier(carrier)
                self.assertEqual(resolution["status"], "RESOLVED")
                self.assertEqual(resolution["receipt_hashes"], [lines[0]["receipt_sha256"]])
            finally:
                fabric.stop(timeout=2.0)

    def test_short_carrier_collision_is_ambiguous_not_silently_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            fabric = WitnessFabric(path=Path(td) / "witness.jsonl", max_queue=2, recent_limit=2)
            fabric._carrier_index["COLLIDE"] = ["a" * 64, "b" * 64]
            resolution = fabric.resolve_carrier("COLLIDE")
            self.assertEqual(resolution["status"], "AMBIGUOUS")
            self.assertEqual(len(resolution["receipt_hashes"]), 2)


if __name__ == "__main__":
    main()
