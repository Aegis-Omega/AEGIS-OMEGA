"""Offline contract regressions. No test uses a real Circle credential or network."""
from __future__ import annotations

import contextlib
import hashlib
import importlib
import io
import json
import os
import unittest
from unittest.mock import patch

MODULE = "harness.sdk.tameion_circle_testnet_read"
# Deliberately assembled dummy strings: never an issued API credential.
TEST_KEY = "TEST_" + "API_KEY:" + "a" * 32 + ":" + "b" * 32
LIVE_KEY = TEST_KEY.replace("TEST_", "LIVE_", 1)


class Response:
    def __init__(self, body=b'{"data":{"wallets":[]}}', status=200, content_type="application/json"):
        self.body, self.status, self.content_type = body, status, content_type
        self.reads = []

    def getheader(self, name, default=None):
        return self.content_type if name.lower() == "content-type" else default

    def read(self, size):
        self.reads.append(size)
        return self.body[:size]


class Connection:
    def __init__(self, response=None, error=None):
        self.response, self.error = response or Response(), error
        self.calls, self.closed = [], False

    def request(self, method, path, body=None, headers=None):
        self.calls.append((method, path, body, headers))
        if self.error:
            raise self.error

    def getresponse(self):
        return self.response

    def close(self):
        self.closed = True


class CircleTestnetReadTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(importlib.util.find_spec(MODULE), "Read-only Testnet adapter is absent")
        self.mod = importlib.import_module(MODULE)

    def observe(self, response=None, *, key=TEST_KEY, execute=True, scope=True, error=None):
        conn = Connection(response, error)
        with patch.dict(os.environ, {} if key is None else {"CIRCLE_TESTNET_API_KEY": key}, clear=True):
            with patch.object(self.mod.http.client, "HTTPSConnection", return_value=conn) as factory:
                result = self.mod.observe_testnet_wallet_inventory(execute_read=execute, restricted_read_confirmed=scope)
        return result, conn, factory

    def test_no_opt_in_opens_no_connection(self):
        result, conn, factory = self.observe(execute=False)
        self.assertEqual(result["status"], "NOT_REQUESTED")
        factory.assert_not_called()

    def test_missing_key_opens_no_connection(self):
        result, conn, factory = self.observe(key=None)
        self.assertEqual(result["reason"], "CIRCLE_TESTNET_API_KEY_UNAVAILABLE")
        self.assertEqual(result["requests_attempted"], 0)
        factory.assert_not_called()

    def test_live_key_is_refused_before_connection(self):
        result, conn, factory = self.observe(key=LIVE_KEY)
        self.assertEqual(result["reason"], "TESTNET_KEY_REQUIRED")
        factory.assert_not_called()

    def test_malformed_and_header_injection_keys_are_refused(self):
        for key in ("", "Bearer " + TEST_KEY, TEST_KEY + "\r\nX-Evil: yes", TEST_KEY + " ", "TEST_API_KEY:x:y"):
            with self.subTest(case=len(key)):
                result, conn, factory = self.observe(key=key)
                self.assertNotEqual(result["status"], "OBSERVED")
                factory.assert_not_called()

    def test_scope_requires_explicit_confirmation(self):
        result, conn, factory = self.observe(scope=False)
        self.assertEqual(result["reason"], "RESTRICTED_WALLETS_READ_NOT_CONFIRMED")
        factory.assert_not_called()

    def test_opt_in_flags_must_be_actual_booleans(self):
        for execute, scope in (("yes", True), (True, "yes"), (1, True), (True, 1)):
            result, conn, factory = self.observe(execute=execute, scope=scope)
            self.assertEqual(result["reason"], "INVALID_OPT_IN_FLAGS")
            factory.assert_not_called()

    def test_one_fixed_https_get_and_bearer_header(self):
        result, conn, factory = self.observe()
        self.assertEqual(result["status"], "OBSERVED")
        self.assertEqual(factory.call_args.args, ("api.circle.com",))
        self.assertEqual(factory.call_args.kwargs["timeout"], 10)
        self.assertEqual(len(conn.calls), 1)
        method, path, body, headers = conn.calls[0]
        self.assertEqual((method, path, body), ("GET", "/v1/w3s/wallets", None))
        self.assertEqual(headers["Authorization"], "Bearer " + TEST_KEY)
        self.assertTrue(conn.closed)

    def test_response_is_bounded_and_digest_only(self):
        body = b'{"data":{"wallets":[{"id":"private-account-id","address":"private-address"}]}}'
        response = Response(body)
        result, conn, factory = self.observe(response)
        self.assertEqual(response.reads, [65537])
        self.assertEqual(result["response_sha256"], hashlib.sha256(body).hexdigest())
        self.assertEqual(result["wallets_in_response"], 1)
        text = json.dumps(result)
        for private in ("private-account-id", "private-address", TEST_KEY):
            self.assertNotIn(private, text)
        self.assertEqual(result["inventory_scope"], "RETURNED_PAGE_ONLY")

    def test_empty_inventory_is_a_successful_read_not_wallet_creation(self):
        result, conn, factory = self.observe()
        self.assertEqual(result["wallets_in_response"], 0)
        self.assertFalse(result["wallet_created"])
        self.assertEqual(result["scope_verification"], "OPERATOR_DECLARED_NOT_API_VERIFIED")

    def test_no_authority_or_settlement_can_be_claimed(self):
        result, conn, factory = self.observe()
        self.assertEqual(result["authority_effect"], "NONE")
        self.assertEqual(result["settlement_evidence"], "NONE")
        for key in ("wallet_created", "entity_secret_created", "signer_attached", "broadcast_performed", "mainnet_allowed"):
            self.assertIs(result[key], False)

    def test_redirect_is_not_followed(self):
        result, conn, factory = self.observe(Response(status=302))
        self.assertEqual(result["reason"], "HTTP_STATUS_REJECTED")
        self.assertEqual(result["http_status"], 302)
        self.assertEqual(len(conn.calls), 1)
        self.assertTrue(conn.closed)

    def test_error_http_status_is_not_authentication_success(self):
        for status in (401, 403, 429, 500):
            with self.subTest(status=status):
                result, conn, factory = self.observe(Response(status=status))
                self.assertEqual(result["status"], "FAILED")
                self.assertFalse(result["authenticated_read_observed"])
                self.assertEqual(len(conn.calls), 1)

    def test_network_errors_are_sanitized_without_retries(self):
        result, conn, factory = self.observe(error=OSError("secret " + TEST_KEY))
        self.assertEqual(result["reason"], "TRANSPORT_ERROR_NO_RETRY")
        self.assertEqual(result["requests_attempted"], 1)
        self.assertNotIn(TEST_KEY, json.dumps(result))
        self.assertEqual(len(conn.calls), 1)
        self.assertTrue(conn.closed)

    def test_connection_constructor_error_is_sanitized(self):
        with patch.dict(os.environ, {"CIRCLE_TESTNET_API_KEY": TEST_KEY}, clear=True):
            with patch.object(self.mod.http.client, "HTTPSConnection", side_effect=OSError(TEST_KEY)):
                result = self.mod.observe_testnet_wallet_inventory(execute_read=True, restricted_read_confirmed=True)
        self.assertEqual(result["reason"], "TRANSPORT_ERROR_NO_RETRY")
        self.assertEqual(result["requests_attempted"], 0)
        self.assertNotIn(TEST_KEY, json.dumps(result))

    def test_oversized_response_is_rejected(self):
        result, conn, factory = self.observe(Response(b"x" * 65537))
        self.assertEqual(result["reason"], "RESPONSE_TOO_LARGE")
        self.assertNotIn("response_sha256", result)

    def test_non_json_content_type_is_rejected(self):
        result, conn, factory = self.observe(Response(content_type="text/html"))
        self.assertEqual(result["reason"], "CONTENT_TYPE_REJECTED")

    def test_malformed_json_is_rejected(self):
        result, conn, factory = self.observe(Response(b"not-json"))
        self.assertEqual(result["reason"], "RESPONSE_SCHEMA_REJECTED")

    def test_duplicate_keys_and_nonfinite_values_are_rejected(self):
        for body in (b'{"data":{"wallets":[]},"data":{"wallets":[]}}', b'{"data":{"wallets":[]},"extra":NaN}'):
            result, conn, factory = self.observe(Response(body))
            self.assertEqual(result["reason"], "RESPONSE_SCHEMA_REJECTED")

    def test_wrong_wallets_shape_is_rejected(self):
        for value in ({}, [], {"data": []}, {"data": {"wallets": {}}}, {"data": {"wallets": [1]}}):
            result, conn, factory = self.observe(Response(json.dumps(value).encode()))
            self.assertEqual(result["reason"], "RESPONSE_SCHEMA_REJECTED")

    def test_reflected_credential_is_not_persisted_or_hashed(self):
        body = json.dumps({"data": {"wallets": []}, "message": TEST_KEY}).encode()
        result, conn, factory = self.observe(Response(body))
        self.assertEqual(result["reason"], "CREDENTIAL_REFLECTION_REJECTED")
        self.assertNotIn("response_sha256", result)
        self.assertNotIn(TEST_KEY, json.dumps(result))

    def test_valid_json_charset_is_accepted(self):
        result, conn, factory = self.observe(Response(content_type="application/json; charset=utf-8"))
        self.assertEqual(result["status"], "OBSERVED")

    def test_receipt_binds_module_bytes(self):
        result, conn, factory = self.observe()
        with open(self.mod.__file__, "rb") as source:
            self.assertEqual(result["module_sha256"], hashlib.sha256(source.read()).hexdigest())

    def test_cli_without_key_is_safe_and_nonzero(self):
        output = io.StringIO()
        with patch.dict(os.environ, {}, clear=True), contextlib.redirect_stdout(output):
            code = self.mod.main(["--execute-read", "--confirm-restricted-wallets-read"])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(output.getvalue())["requests_attempted"], 0)

    def test_cli_default_does_not_request_network(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output), patch.object(self.mod.http.client, "HTTPSConnection") as factory:
            code = self.mod.main([])
        self.assertEqual(code, 0)
        factory.assert_not_called()
        self.assertEqual(json.loads(output.getvalue())["status"], "NOT_REQUESTED")


if __name__ == "__main__":
    unittest.main()
