#!/usr/bin/env python3
"""Tests for read-only Circle CCTP sandbox attestation observation."""
from __future__ import annotations

import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from unittest import TestCase, main

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.sovereign_execution import SCHEMA_VERSION, SovereignExecutionError  # noqa: E402
from harness.sdk.tameion_circle_attestation import (  # noqa: E402
    CIRCLE_CCTP_SANDBOX_BASE,
    build_circle_attestation_request,
    build_circle_v2_messages_request,
    fetch_circle_attestation,
    fetch_circle_v2_messages,
    parse_circle_attestation_response,
    parse_circle_v2_messages_response,
)

MESSAGE_HASH = "0x" + "ab" * 32
ATTESTATION = "0x" + "cd" * 65
TRANSACTION_HASH = "0x" + "12" * 32
V2_MESSAGE = "0x" + "34" * 180


class _FakeResponse:
    def __init__(self, payload: object) -> None:
        self.body = json.dumps(payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False

    def read(self, size: int = -1) -> bytes:
        if size < 0:
            return self.body
        return self.body[:size]


class _FakeOpener:
    def __init__(self, payload: object) -> None:
        self.payload = payload
        self.request = None
        self.timeout = None

    def __call__(self, request, *, timeout: float):
        self.request = request
        self.timeout = timeout
        return _FakeResponse(self.payload)


class CircleAttestationTests(TestCase):
    def test_request_is_exact_sandbox_get_with_no_authority(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH.upper())
        self.assertEqual(request.message_hash, MESSAGE_HASH)
        self.assertEqual(
            request.endpoint,
            f"{CIRCLE_CCTP_SANDBOX_BASE}/v1/attestations/{MESSAGE_HASH}",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.network_effect, "READ_ONLY")
        self.assertFalse(request.signer_attached)
        self.assertFalse(request.broadcast_allowed)
        self.assertEqual(request.custody_effect, "NONE")
        self.assertEqual(request.authority_effect, "NONE")
        self.assertEqual(len(request.root), 64)

    def test_request_rejects_malformed_hash(self) -> None:
        for value in ("", "0x1234", "ab" * 32, "0x" + "gg" * 32):
            with self.subTest(value=value):
                with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_MESSAGE_HASH_INVALID"):
                    build_circle_attestation_request(value)

    def test_request_rejects_endpoint_or_method_escalation(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_ATTESTATION_ENDPOINT_INVALID"):
            replace(request, endpoint="https://iris-api.circle.com/v1/attestations/" + MESSAGE_HASH).validate()
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_ATTESTATION_METHOD_NOT_READ_ONLY"):
            replace(request, method="POST").validate()

    def test_request_cannot_gain_signer_broadcast_custody_or_authority(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        cases = (
            ({"signer_attached": True}, "CIRCLE_ATTESTATION_SIGNER_FORBIDDEN"),
            ({"broadcast_allowed": True}, "CIRCLE_ATTESTATION_BROADCAST_FORBIDDEN"),
            ({"custody_effect": "WRITE"}, "CIRCLE_ATTESTATION_CUSTODY_FORBIDDEN"),
            ({"authority_effect": "GRANT"}, "CIRCLE_ATTESTATION_AUTHORITY_EFFECT_INVALID"),
        )
        for changes, code in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(SovereignExecutionError, code):
                    replace(request, **changes).validate()

    def test_complete_response_is_digest_only_evidence(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        observation = parse_circle_attestation_response(
            request,
            {"status": "complete", "attestation": ATTESTATION},
        )
        expected = hashlib.sha256(bytes.fromhex(ATTESTATION[2:])).hexdigest()
        self.assertEqual(observation.attestation_sha256, expected)
        self.assertEqual(observation.status, "complete")
        self.assertEqual(observation.request_root, request.root)
        self.assertEqual(observation.authority_effect, "NONE")
        self.assertNotIn(ATTESTATION, repr(observation))
        self.assertEqual(len(observation.root), 64)

    def test_pending_response_contains_no_attestation_digest(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        observation = parse_circle_attestation_response(
            request,
            {"status": "pending_confirmations", "attestation": None},
        )
        self.assertIsNone(observation.attestation_sha256)
        self.assertEqual(observation.authority_effect, "NONE")

    def test_fetch_performs_one_get_without_authorization_header(self) -> None:
        opener = _FakeOpener({"status": "complete", "attestation": ATTESTATION})
        request, observation = fetch_circle_attestation(
            MESSAGE_HASH,
            opener=opener,
            timeout=3.0,
        )
        self.assertIsNotNone(opener.request)
        self.assertEqual(opener.request.get_method(), "GET")
        headers = {key.lower(): value for key, value in opener.request.header_items()}
        self.assertNotIn("authorization", headers)
        self.assertEqual(opener.timeout, 3.0)
        self.assertEqual(observation.request_root, request.root)
        self.assertEqual(observation.network_effect, "READ_ONLY")

    def test_response_rejects_malformed_attestation_and_unknown_status(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_ATTESTATION_BYTES_INVALID"):
            parse_circle_attestation_response(
                request,
                {"status": "complete", "attestation": "not-hex"},
            )
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_ATTESTATION_STATUS_INVALID"):
            parse_circle_attestation_response(
                request,
                {"status": "failed", "attestation": None},
            )

    def test_observation_cannot_be_relabelled_as_authority(self) -> None:
        request = build_circle_attestation_request(MESSAGE_HASH)
        observation = parse_circle_attestation_response(
            request,
            {"status": "complete", "attestation": ATTESTATION},
        )
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_OBSERVATION_AUTHORITY_EFFECT_INVALID"):
            replace(observation, authority_effect="GRANT").validate()


    def test_v2_request_is_exact_sandbox_get_with_no_authority(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH.upper())
        self.assertEqual(request.source_domain, 2)
        self.assertEqual(request.transaction_hash, TRANSACTION_HASH)
        self.assertEqual(
            request.endpoint,
            f"{CIRCLE_CCTP_SANDBOX_BASE}/v2/messages/2?transactionHash={TRANSACTION_HASH}",
        )
        self.assertEqual(request.method, "GET")
        self.assertEqual(request.network_effect, "READ_ONLY")
        self.assertFalse(request.signer_attached)
        self.assertFalse(request.broadcast_allowed)
        self.assertEqual(request.custody_effect, "NONE")
        self.assertEqual(request.authority_effect, "NONE")

    def test_v2_request_rejects_bad_domain_hash_and_escalation(self) -> None:
        for domain in (-1, 2**32, True, "2"):
            with self.subTest(domain=domain):
                with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_SOURCE_DOMAIN_INVALID"):
                    build_circle_v2_messages_request(domain, TRANSACTION_HASH)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_TRANSACTION_HASH_INVALID"):
            build_circle_v2_messages_request(2, "0x1234")
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_V2_ENDPOINT_INVALID"):
            replace(request, endpoint=request.endpoint.replace("iris-api-sandbox", "iris-api")).validate()
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_V2_METHOD_NOT_READ_ONLY"):
            replace(request, method="POST").validate()

    def test_v2_complete_response_is_digest_only_evidence(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        observation = parse_circle_v2_messages_response(
            request,
            {"messages": [{"status": "complete", "message": V2_MESSAGE, "attestation": ATTESTATION}]},
        )
        self.assertEqual(observation.statuses, ("complete",))
        self.assertEqual(
            observation.message_sha256[0],
            hashlib.sha256(bytes.fromhex(V2_MESSAGE[2:])).hexdigest(),
        )
        self.assertEqual(
            observation.attestation_sha256[0],
            hashlib.sha256(bytes.fromhex(ATTESTATION[2:])).hexdigest(),
        )
        self.assertEqual(observation.message_bytes, (180,))
        self.assertEqual(observation.attestation_bytes, (65,))
        self.assertNotIn(V2_MESSAGE, repr(observation))
        self.assertNotIn(ATTESTATION, repr(observation))
        self.assertEqual(observation.authority_effect, "NONE")

    def test_v2_pending_response_keeps_missing_attestation_visible(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        observation = parse_circle_v2_messages_response(
            request,
            {"messages": [{"status": "pending_confirmations", "message": None, "attestation": "PENDING"}]},
        )
        self.assertEqual(observation.statuses, ("pending_confirmations",))
        self.assertEqual(observation.message_sha256, (None,))
        self.assertEqual(observation.attestation_sha256, (None,))
        self.assertEqual(observation.attestation_bytes, (None,))

    def test_v2_multi_message_response_is_bounded_and_deterministic(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        payload = {"messages": [
            {"status": "complete", "message": V2_MESSAGE, "attestation": ATTESTATION},
            {"status": "pending_confirmations", "message": V2_MESSAGE, "attestation": None},
        ]}
        first = parse_circle_v2_messages_response(request, payload)
        second = parse_circle_v2_messages_response(request, payload)
        self.assertEqual(first, second)
        self.assertEqual(first.root, second.root)
        self.assertEqual(len(first.statuses), 2)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_V2_MESSAGE_COUNT_INVALID"):
            parse_circle_v2_messages_response(request, {"messages": []})

    def test_v2_fetch_performs_one_get_without_authorization_header(self) -> None:
        opener = _FakeOpener({
            "messages": [{"status": "complete", "message": V2_MESSAGE, "attestation": ATTESTATION}]
        })
        request, observation = fetch_circle_v2_messages(
            2,
            TRANSACTION_HASH,
            opener=opener,
            timeout=3.0,
        )
        self.assertEqual(opener.request.get_method(), "GET")
        headers = {key.lower(): value for key, value in opener.request.header_items()}
        self.assertNotIn("authorization", headers)
        self.assertEqual(opener.timeout, 3.0)
        self.assertEqual(observation.request_root, request.root)
        self.assertEqual(observation.network_effect, "READ_ONLY")

    def test_v2_rejects_malformed_complete_and_unknown_status(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_V2_MESSAGE_BYTES_INVALID"):
            parse_circle_v2_messages_response(
                request,
                {"messages": [{"status": "complete", "message": "bad", "attestation": ATTESTATION}]},
            )
        with self.assertRaisesRegex(SovereignExecutionError, "CIRCLE_V2_STATUS_INVALID"):
            parse_circle_v2_messages_response(
                request,
                {"messages": [{"status": "failed", "message": None, "attestation": None}]},
            )

    def test_v2_observation_cannot_gain_authority_or_side_effects(self) -> None:
        request = build_circle_v2_messages_request(2, TRANSACTION_HASH)
        observation = parse_circle_v2_messages_response(
            request,
            {"messages": [{"status": "complete", "message": V2_MESSAGE, "attestation": ATTESTATION}]},
        )
        cases = (
            ({"authority_effect": "GRANT"}, "CIRCLE_V2_OBSERVATION_AUTHORITY_EFFECT_INVALID"),
            ({"signer_attached": True}, "CIRCLE_V2_OBSERVATION_SIGNER_FORBIDDEN"),
            ({"broadcast_allowed": True}, "CIRCLE_V2_OBSERVATION_BROADCAST_FORBIDDEN"),
            ({"custody_effect": "WRITE"}, "CIRCLE_V2_OBSERVATION_CUSTODY_FORBIDDEN"),
        )
        for changes, code in cases:
            with self.subTest(changes=changes):
                with self.assertRaisesRegex(SovereignExecutionError, code):
                    replace(observation, **changes).validate()


if __name__ == "__main__":
    main()
