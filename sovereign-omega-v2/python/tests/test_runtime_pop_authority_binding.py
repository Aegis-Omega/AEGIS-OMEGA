#!/usr/bin/env python3
"""Composition falsifiers for cryptographic RuntimePoP -> structural principal binding."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.principal_binding import MTLS_CERT_BOUND, VERIFIED  # noqa: E402
from harness.sdk.runtime_pop_crypto import (  # noqa: E402
    CRYPTO_RECEIPT_KIND,
    CRYPTO_SCHEMA_VERSION,
    CRYPTO_VERIFIER_IDENTITY,
    CryptoVerificationError,
    RuntimePoPCryptoReceipt,
)
from harness.sdk.runtime_pop_authority import (  # noqa: E402
    SQLiteReplayStore,
    bind_execution_principal_from_crypto,
)

RUNTIME = "spiffe://aegis.example/runtime/gateway-7"
AGENT = "spiffe://aegis.example/agent/scheduler-1"


def raw_principal() -> dict:
    return {
        "schema_version": "1.0.0",
        "acting_mode": "SELF_ACTING",
        "user_principal": "NONE",
        "agent_principal": AGENT,
        "runtime_principal": RUNTIME,
        "session_identity": "session-1",
        "requested_capability": "external.calendar.write",
        "action_digest": "1" * 64,
        "target_digest": "2" * 64,
        "task_action_binding": "3" * 64,
        "runtime_pop": {
            "runtime_principal": RUNTIME,
            "binding_mode": MTLS_CERT_BOUND,
            "verification_state": VERIFIED,
            "verifier_identity": "attacker:self-asserted",
            "proof_root": "f" * 64,
            "evidence_ref": "attacker:evidence",
            "generation": 999,
        },
        "delegation": None,
    }


def crypto_receipt(*, runtime: str = RUNTIME, mode: str = MTLS_CERT_BOUND, root: str = "a" * 64) -> RuntimePoPCryptoReceipt:
    return RuntimePoPCryptoReceipt(
        schema_version=CRYPTO_SCHEMA_VERSION,
        receipt_kind=CRYPTO_RECEIPT_KIND,
        cryptographic_verified=True,
        verifier_identity=CRYPTO_VERIFIER_IDENTITY,
        runtime_principal=runtime,
        binding_mode=mode,
        verification_time_epoch=1_787_500_000,
        certificate_thumbprint_s256="thumbprint",
        dpop_jkt="NONE",
        access_token_sha256="b" * 64,
        dpop_proof_sha256="0" * 64,
        request_method="POST",
        request_uri="https://calendar.example.test/v1/events",
        proof_root=root,
    )


class RuntimePoPAuthorityBindingTests(TestCase):
    def test_01_caller_asserted_verified_pop_is_replaced_by_crypto_receipt(self):
        with patch("harness.sdk.runtime_pop_authority.verify_runtime_pop_evidence", return_value=crypto_receipt()):
            binding, receipt = bind_execution_principal_from_crypto(
                raw_principal(),
                {"opaque": "crypto-evidence"},
                generation=12,
            )
        self.assertEqual(receipt.proof_root, "a" * 64)
        self.assertEqual(binding.runtime_pop.proof_root, "a" * 64)
        self.assertEqual(binding.runtime_pop.verifier_identity, CRYPTO_VERIFIER_IDENTITY)
        self.assertEqual(binding.runtime_pop.generation, 12)
        self.assertNotEqual(binding.runtime_pop.proof_root, "f" * 64)
        self.assertNotEqual(binding.runtime_pop.verifier_identity, "attacker:self-asserted")

    def test_02_crypto_runtime_subject_must_match_execution_principal(self):
        with patch(
            "harness.sdk.runtime_pop_authority.verify_runtime_pop_evidence",
            return_value=crypto_receipt(runtime="spiffe://aegis.example/runtime/other"),
        ):
            with self.assertRaisesRegex(CryptoVerificationError, "CRYPTO_RUNTIME_PRINCIPAL_MISMATCH"):
                bind_execution_principal_from_crypto(raw_principal(), {}, generation=1)

    def test_03_crypto_mode_must_match_requested_structural_mode(self):
        with patch(
            "harness.sdk.runtime_pop_authority.verify_runtime_pop_evidence",
            return_value=crypto_receipt(mode="DPOP_CERT_BOUND"),
        ):
            with self.assertRaisesRegex(CryptoVerificationError, "CRYPTO_BINDING_MODE_MISMATCH"):
                bind_execution_principal_from_crypto(raw_principal(), {}, generation=1)

    def test_04_sqlite_replay_store_rejects_duplicate_across_instances(self):
        with tempfile.TemporaryDirectory() as tmp:
            db = Path(tmp) / "dpop-replay.sqlite3"
            first = SQLiteReplayStore(db)
            second = SQLiteReplayStore(db)
            self.assertTrue(first.consume("replay-key", now_epoch=100, expires_at=200))
            self.assertFalse(second.consume("replay-key", now_epoch=101, expires_at=200))
            self.assertTrue(second.consume("replay-key", now_epoch=201, expires_at=300))

    def test_05_environment_authority_requires_crypto_evidence_path_and_shared_binding_helper(self):
        source = (REPO_ROOT / "harness/sdk/authority_client.py").read_text(encoding="utf-8")
        self.assertIn("bind_execution_principal_from_crypto", source)
        self.assertIn("AEGIS_RUNTIME_POP_CRYPTO_EVIDENCE_PATH", source)
        self.assertIn("AEGIS_DPOP_REPLAY_DB", source)
        self.assertNotIn("principal = ExecutionPrincipalBinding.from_mapping(json.loads(raw_principal))", source)

    def test_06_cli_authority_requires_crypto_evidence_and_shared_binding_helper(self):
        source = (REPO_ROOT / "scripts/automaton3-authority.py").read_text(encoding="utf-8")
        self.assertIn("bind_execution_principal_from_crypto", source)
        self.assertIn('payload.get("runtime_pop_crypto_evidence")', source)
        self.assertIn('request_payload.get("dpop_replay_db")', source)
        self.assertNotIn("principal = ExecutionPrincipalBinding.from_mapping(raw_principal)", source)


if __name__ == "__main__":
    main()
