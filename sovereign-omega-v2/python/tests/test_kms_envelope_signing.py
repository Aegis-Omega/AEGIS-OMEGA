#!/usr/bin/env python3
from __future__ import annotations

import base64
import copy
import importlib.util
import json
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
PYTHON_DIR = REPO_ROOT / "sovereign-omega-v2/python"
sys.path.insert(0, str(PYTHON_DIR))

import canonical_envelope as ce  # noqa: E402
import kms_envelope_signing as kms  # noqa: E402

KEY_VERSION = (
    "projects/aegis-test/locations/europe-west1/keyRings/aegis/"
    "cryptoKeys/envelope-signing/cryptoKeyVersions/7"
)
PRINCIPAL = kms.ClientPrincipal(
    kind="service_account",
    issuer="https://accounts.google.com",
    subject="runtime@example.iam.gserviceaccount.com",
)


def envelope():
    return ce.EnvelopeChain().emit(
        "a" * 64,
        "b" * 64,
        "model-a",
        "T1",
        "anthropic",
    )


def good_response(statement: bytes, signature: bytes = b"S" * 64):
    return {
        "name": KEY_VERSION,
        "signature": base64.b64encode(signature).decode("ascii"),
        "signatureCrc32c": str(kms.crc32c(signature)),
        "verifiedDataCrc32c": True,
        "protectionLevel": "SOFTWARE",
    }


class RecordingTransport:
    def __init__(self, response_factory=good_response):
        self.response_factory = response_factory
        self.calls = []

    def __call__(self, endpoint, request):
        self.calls.append((endpoint, copy.deepcopy(request)))
        raw = base64.b64decode(request["data"], validate=True)
        return self.response_factory(raw)


class KmsEnvelopeSigningTests(unittest.TestCase):
    def test_crc32c_known_castagnoli_vector(self):
        self.assertEqual(kms.crc32c(b"123456789"), 0xE3069283)

    def test_signature_statement_is_domain_separated_and_deterministic(self):
        env = envelope()
        first = kms.signature_statement_bytes(env["envelope_hash"], PRINCIPAL)
        second = kms.signature_statement_bytes(env["envelope_hash"], PRINCIPAL)
        self.assertEqual(first, second)
        payload = json.loads(first)
        self.assertEqual(payload["domain"], kms.SIGNATURE_DOMAIN)
        self.assertEqual(payload["envelope_hash"], env["envelope_hash"])
        self.assertEqual(payload["client_principal"], PRINCIPAL.as_dict())

    def test_client_principal_changes_signed_statement(self):
        env = envelope()
        other = kms.ClientPrincipal(
            kind="service_account",
            issuer=PRINCIPAL.issuer,
            subject="other@example.iam.gserviceaccount.com",
        )
        self.assertNotEqual(
            kms.signature_statement_bytes(env["envelope_hash"], PRINCIPAL),
            kms.signature_statement_bytes(env["envelope_hash"], other),
        )

    def test_rest_request_uses_raw_data_never_digest(self):
        transport = RecordingTransport()
        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=transport,
        )
        env = envelope()
        record = signer.sign(env["envelope_hash"], PRINCIPAL)
        self.assertEqual(len(transport.calls), 1)
        endpoint, request = transport.calls[0]
        self.assertEqual(endpoint, kms.asymmetric_sign_endpoint(KEY_VERSION))
        self.assertIn("data", request)
        self.assertIn("dataCrc32c", request)
        self.assertNotIn("digest", request)
        self.assertNotIn("digestCrc32c", request)
        raw = base64.b64decode(request["data"], validate=True)
        self.assertEqual(int(request["dataCrc32c"]), kms.crc32c(raw))
        self.assertEqual(record["algorithm"], "EC_SIGN_ED25519")
        self.assertTrue(record["verified_data_crc32c"])

    def test_exact_key_version_resource_is_required(self):
        transport = RecordingTransport()
        for bad in (
            "",
            "projects/p/locations/l/keyRings/r/cryptoKeys/k",
            "projects/p/locations/l/keyRings/r/cryptoKeys/k/cryptoKeyVersions/0",
            "projects/p/locations/l/keyRings/r/cryptoKeys/k/cryptoKeyVersions/latest",
        ):
            with self.subTest(bad=bad):
                with self.assertRaisesRegex(
                    kms.EnvelopeSigningError, "KMS_KEY_VERSION_NAME_INVALID"
                ):
                    kms.GoogleCloudKmsEd25519Signer(
                        key_version_name=bad,
                        transport=transport,
                    )

    def test_non_ed25519_algorithm_is_rejected(self):
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_ALGORITHM_UNSUPPORTED"
        ):
            kms.GoogleCloudKmsEd25519Signer(
                key_version_name=KEY_VERSION,
                transport=RecordingTransport(),
                algorithm="EC_SIGN_P256_SHA256",
            )

    def test_response_key_version_mismatch_is_fail_closed(self):
        def response(statement):
            result = good_response(statement)
            result["name"] = KEY_VERSION[:-1] + "8"
            return result

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(response),
        )
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_KEY_VERSION_MISMATCH"
        ):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)

    def test_server_must_confirm_data_crc32c(self):
        def response(statement):
            result = good_response(statement)
            result["verifiedDataCrc32c"] = False
            return result

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(response),
        )
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_DATA_CRC32C_NOT_VERIFIED"
        ):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)

    def test_signature_crc32c_is_verified(self):
        def response(statement):
            result = good_response(statement)
            result["signatureCrc32c"] = "1"
            return result

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(response),
        )
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_SIGNATURE_CRC32C_MISMATCH"
        ):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)

    def test_ed25519_signature_must_be_exactly_64_bytes(self):
        def response(statement):
            return good_response(statement, signature=b"x" * 63)

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(response),
        )
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_ED25519_SIGNATURE_LENGTH_INVALID"
        ):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)

    def test_invalid_base64_signature_is_rejected(self):
        def response(statement):
            result = good_response(statement)
            result["signature"] = "!!!"
            return result

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(response),
        )
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "KMS_SIGNATURE_BASE64_INVALID"
        ):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)

    def test_transport_failure_has_no_hidden_retry(self):
        calls = []

        def transport(endpoint, request):
            calls.append((endpoint, request))
            raise RuntimeError("network unavailable")

        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=transport,
        )
        with self.assertRaisesRegex(kms.EnvelopeSigningError, "KMS_SIGN_UNAVAILABLE"):
            signer.sign(envelope()["envelope_hash"], PRINCIPAL)
        self.assertEqual(len(calls), 1)

    def test_attach_signature_preserves_hash_and_does_not_mutate_input(self):
        env = envelope()
        before = copy.deepcopy(env)
        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=RecordingTransport(),
        )
        signed = kms.attach_kms_signature(
            env,
            client_principal=PRINCIPAL,
            signer=signer,
        )
        self.assertEqual(env, before)
        self.assertIsNone(env["signature"])
        self.assertEqual(signed["envelope_hash"], env["envelope_hash"])
        self.assertEqual(signed["signature"]["key_version"], KEY_VERSION)
        self.assertEqual(
            signed["signature"]["client_principal"],
            PRINCIPAL.as_dict(),
        )
        self.assertRegex(signed["signature"]["statement_sha256"], r"^[0-9a-f]{64}$")

    def test_tampered_envelope_is_refused_before_transport(self):
        transport = RecordingTransport()
        signer = kms.GoogleCloudKmsEd25519Signer(
            key_version_name=KEY_VERSION,
            transport=transport,
        )
        env = envelope()
        env["provider"] = "other"
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "ENVELOPE_HASH_MISMATCH"
        ):
            kms.attach_kms_signature(
                env,
                client_principal=PRINCIPAL,
                signer=signer,
            )
        self.assertEqual(transport.calls, [])

    def test_already_signed_envelope_is_refused(self):
        env = envelope()
        env["signature"] = {"forged": True}
        with self.assertRaisesRegex(
            kms.EnvelopeSigningError, "ENVELOPE_ALREADY_SIGNED"
        ):
            kms.attach_kms_signature(
                env,
                client_principal=PRINCIPAL,
                signer=kms.GoogleCloudKmsEd25519Signer(
                    key_version_name=KEY_VERSION,
                    transport=RecordingTransport(),
                ),
            )

    def test_principal_unicode_and_control_ambiguity_are_rejected(self):
        for subject in ("e\u0301@example.com", "agent\x1b[31m"):
            with self.subTest(subject=subject):
                principal = kms.ClientPrincipal(
                    kind="service_account",
                    issuer=PRINCIPAL.issuer,
                    subject=subject,
                )
                with self.assertRaises(kms.EnvelopeSigningError):
                    principal.validate()


if __name__ == "__main__":
    unittest.main(verbosity=2)
