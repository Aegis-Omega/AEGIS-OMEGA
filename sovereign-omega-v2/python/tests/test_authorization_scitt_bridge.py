#!/usr/bin/env python3
"""Falsifiers for binding verified current-transition authorization into SCITT."""
from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase, main
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
TEST_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TEST_ROOT))

from harness.sdk.authorization_scitt_bridge import (  # noqa: E402
    AuthorizationSCITTBridgeError,
    verify_scitt_for_verified_current_authorization,
)
from test_authorization_transition_bridge import NOW, verify as verify_transition  # noqa: E402


def scitt_result(*, authorization_root: str, now: int = NOW, authority: bool = False):
    return SimpleNamespace(
        registration_verified=True,
        authorization_time_evidence_root=authorization_root,
        verification_time_epoch=now,
        authority_granted=authority,
        receipt_root="f" * 64,
    )


class AuthorizationSCITTBridgeTests(TestCase):
    def test_01_scitt_root_must_equal_verified_current_transition_authorization_receipt(self):
        current = verify_transition()
        expected = current.authorization_evidence.receipt_root
        captured = {}

        def verifier(**kwargs):
            captured.update(kwargs)
            return scitt_result(authorization_root=expected)

        with patch(
            "harness.sdk.authorization_scitt_bridge.verify_scitt_authorization_for_current_runtime",
            side_effect=verifier,
        ):
            result = verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement",
                receipt=b"receipt",
                scitt_trust_policy=object(),
                runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(),
                attested_runtime_trust_policy=object(),
                current_authorization=current,
                verification_time_epoch=NOW,
            )
        self.assertEqual(result.authorization_time_evidence_root, expected)
        self.assertEqual(captured["verification_time_epoch"], NOW)
        self.assertNotIn("authorization_time_evidence_root", captured)

    def test_02_signed_scitt_root_mismatch_denies_even_when_scitt_crypto_passes(self):
        current = verify_transition()
        with patch(
            "harness.sdk.authorization_scitt_bridge.verify_scitt_authorization_for_current_runtime",
            return_value=scitt_result(authorization_root="a" * 64),
        ):
            with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_EVIDENCE_ROOT_MISMATCH"):
                verify_scitt_for_verified_current_authorization(
                    signed_statement=b"statement", receipt=b"receipt",
                    scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                    eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                    current_authorization=current, verification_time_epoch=NOW,
                )

    def test_03_authorization_evidence_must_be_verified_evidence_only_and_current(self):
        current = verify_transition()
        bad = replace(current.authorization_evidence, authorization_time_verified=False)
        with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_AUTHORIZATION_EVIDENCE_INVALID"):
            verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                current_authorization=replace(current, authorization_evidence=bad),
                verification_time_epoch=NOW,
            )
        bad = replace(current.authorization_evidence, authority_granted=True)
        with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_AUTHORIZATION_EVIDENCE_INVALID"):
            verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                current_authorization=replace(current, authorization_evidence=bad),
                verification_time_epoch=NOW,
            )

    def test_04_transition_decision_and_authorization_roots_must_remain_internally_bound(self):
        current = verify_transition()
        bad_evidence = replace(current.authorization_evidence, transition_id="b" * 64)
        with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_CURRENT_TRANSITION_INVALID"):
            verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                current_authorization=replace(current, authorization_evidence=bad_evidence),
                verification_time_epoch=NOW,
            )
        bad_evidence = replace(current.authorization_evidence, decision_receipt_root="c" * 64)
        with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_CURRENT_TRANSITION_INVALID"):
            verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                current_authorization=replace(current, authorization_evidence=bad_evidence),
                verification_time_epoch=NOW,
            )

    def test_05_verifier_time_is_single_load_bearing_clock(self):
        current = verify_transition()
        with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_VERIFICATION_TIME_MISMATCH"):
            verify_scitt_for_verified_current_authorization(
                signed_statement=b"statement", receipt=b"receipt",
                scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                current_authorization=current, verification_time_epoch=NOW + 1,
            )
        with patch(
            "harness.sdk.authorization_scitt_bridge.verify_scitt_authorization_for_current_runtime",
            return_value=scitt_result(
                authorization_root=current.authorization_evidence.receipt_root,
                now=NOW + 1,
            ),
        ):
            with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_SCITT_TIME_MISMATCH"):
                verify_scitt_for_verified_current_authorization(
                    signed_statement=b"statement", receipt=b"receipt",
                    scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                    eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                    current_authorization=current, verification_time_epoch=NOW,
                )

    def test_06_bridge_never_upgrades_evidence_into_authority(self):
        current = verify_transition()
        with patch(
            "harness.sdk.authorization_scitt_bridge.verify_scitt_authorization_for_current_runtime",
            return_value=scitt_result(
                authorization_root=current.authorization_evidence.receipt_root,
                authority=True,
            ),
        ):
            with self.assertRaisesRegex(AuthorizationSCITTBridgeError, "AUTHZ_SCITT_SCITT_AUTHORITY_FORBIDDEN"):
                verify_scitt_for_verified_current_authorization(
                    signed_statement=b"statement", receipt=b"receipt",
                    scitt_trust_policy=object(), runtime_pop_crypto_receipt=object(),
                    eat_trust_policy=object(), attested_runtime_trust_policy=object(),
                    current_authorization=current, verification_time_epoch=NOW,
                )


if __name__ == "__main__":
    main()
