"""Opt-in, single authenticated Circle Testnet inventory read; never a wallet write.

Contract checked 2026-10-06:
https://developers.circle.com/api-reference/keys
https://developers.circle.com/contracts/create-api-key

Circle documents GET /v1/w3s/wallets as an authentication check. A Testnet
Restricted Access key should grant Wallets: Read and no other product access.
The operator must confirm that scope: this endpoint cannot attest key scopes.
CCTP itself is permissionless and does not need this credential.

Only CIRCLE_TESTNET_API_KEY is read, in memory. Never pass the key as a CLI
argument. Provision it in a secret store/environment, not in source control.
The receipt contains only status, a response digest, a returned-page count and
fixed provenance/boundary fields. No raw body, IDs, addresses, keys, request
headers or transport exception messages are logged or persisted.

No request occurs on import or without BOTH explicit CLI opt-ins. The one fixed
HTTPS GET has no body, no redirects, no retries and no automatic pagination.
This module creates no wallet, entity secret, signer, transfer or authority.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import ssl
from typing import Any

HOST = "api.circle.com"
PATH = "/v1/w3s/wallets"
MAX_RESPONSE_BYTES = 65_536
TIMEOUT_SECONDS = 10
TEST_KEY_PATTERN = re.compile(r"TEST_API_KEY:[A-Za-z0-9_-]{16,128}:[A-Za-z0-9_-]{16,256}\Z")


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for name, value in pairs:
        if name in result:
            raise ValueError("duplicate JSON key")
        result[name] = value
    return result


def _reject_constant(value: str) -> None:
    raise ValueError("non-finite JSON value")


def observe_testnet_wallet_inventory(
    *, execute_read: bool = False, restricted_read_confirmed: bool = False
) -> dict[str, Any]:
    """Return a sanitized local observation, not a signed Circle attestation.

    A request attempt is counted just before the HTTP request boundary; a
    transport error cannot establish whether the remote server received it.
    ``wallets_in_response`` is never claimed to be a complete inventory.
    ``restricted_read_confirmed`` is an operator declaration, not API evidence.
    """
    receipt: dict[str, Any] = {
        "kind": "AEGIS_CIRCLE_TESTNET_INVENTORY_READ_V1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(),
        "module_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "endpoint": f"https://{HOST}{PATH}",
        "method": "GET",
        "environment": "TESTNET_KEY_SELECTED",
        "status": "NOT_REQUESTED",
        "reason": "EXPLICIT_OPT_IN_REQUIRED",
        "requests_attempted": 0,
        "retries": 0,
        "redirects_followed": 0,
        "pages_requested": 0,
        "authorization_header_attempted": False,
        "authenticated_read_observed": False,
        "scope_verification": "OPERATOR_DECLARED_NOT_API_VERIFIED",
        "raw_response_persisted": False,
        "credentials_persisted": False,
        "wallet_created": False,
        "entity_secret_created": False,
        "signer_attached": False,
        "broadcast_performed": False,
        "mainnet_allowed": False,
        "authority_effect": "NONE",
        "settlement_evidence": "NONE",
    }

    def reject(reason: str, status: str = "BLOCKED") -> dict[str, Any]:
        receipt.update(status=status, reason=reason)
        return receipt

    if type(execute_read) is not bool or type(restricted_read_confirmed) is not bool:
        return reject("INVALID_OPT_IN_FLAGS")
    if not execute_read:
        return receipt
    key = os.environ.get("CIRCLE_TESTNET_API_KEY", "")
    if not key:
        return reject("CIRCLE_TESTNET_API_KEY_UNAVAILABLE")
    if TEST_KEY_PATTERN.fullmatch(key) is None:
        return reject("TESTNET_KEY_REQUIRED")
    if not restricted_read_confirmed:
        return reject("RESTRICTED_WALLETS_READ_NOT_CONFIRMED")

    connection = None
    try:
        # http.client performs no automatic redirects, retries or proxy-env
        # forwarding. Default SSL context enforces certificate/hostname checks.
        connection = http.client.HTTPSConnection(
            HOST, timeout=TIMEOUT_SECONDS, context=ssl.create_default_context()
        )
        receipt.update(requests_attempted=1, pages_requested=1,
                       authorization_header_attempted=True)
        connection.request("GET", PATH, body=None, headers={
            "Accept": "application/json",
            "Authorization": "Bearer " + key,
            "User-Agent": "AEGIS-Tameion-ReadOnly/1.0",
        })
        response = connection.getresponse()
        receipt["http_status"] = response.status
        if response.status != 200:
            return reject("HTTP_STATUS_REJECTED", "FAILED")
        content_type = response.getheader("Content-Type", "").split(";", 1)[0].strip().lower()
        if content_type != "application/json":
            return reject("CONTENT_TYPE_REJECTED", "FAILED")
        body = response.read(MAX_RESPONSE_BYTES + 1)
        if len(body) > MAX_RESPONSE_BYTES:
            return reject("RESPONSE_TOO_LARGE", "FAILED")
        if key.encode("ascii") in body:
            return reject("CREDENTIAL_REFLECTION_REJECTED", "FAILED")
        try:
            payload = json.loads(body.decode("utf-8"), object_pairs_hook=_unique_object,
                                 parse_constant=_reject_constant)
            if not isinstance(payload, dict) or not isinstance(payload.get("data"), dict):
                return reject("RESPONSE_SCHEMA_REJECTED", "FAILED")
            wallets = payload["data"].get("wallets")
            if not isinstance(wallets, list) or not all(isinstance(item, dict) for item in wallets):
                return reject("RESPONSE_SCHEMA_REJECTED", "FAILED")
        except (ValueError, UnicodeError, RecursionError, TypeError):
            return reject("RESPONSE_SCHEMA_REJECTED", "FAILED")
        receipt.update(
            status="OBSERVED", reason="AUTHENTICATED_TESTNET_INVENTORY_READ",
            authenticated_read_observed=True,
            response_sha256=hashlib.sha256(body).hexdigest(),
            response_bytes=len(body), wallets_in_response=len(wallets),
            inventory_scope="RETURNED_PAGE_ONLY",
        )
        return receipt
    except Exception:
        # Provider/transport exception text may contain credentials. Never echo it.
        return reject("TRANSPORT_ERROR_NO_RETRY", "FAILED")
    finally:
        if connection is not None:
            try:
                connection.close()
            except Exception:
                pass


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute-read", action="store_true",
                        help="Opt in to one fixed authenticated Testnet GET.")
    parser.add_argument("--confirm-restricted-wallets-read", action="store_true",
                        help="Declare the key is Testnet Restricted Access: Wallets Read only.")
    args = parser.parse_args(argv)
    receipt = observe_testnet_wallet_inventory(
        execute_read=args.execute_read,
        restricted_read_confirmed=args.confirm_restricted_wallets_read,
    )
    print(json.dumps(receipt, sort_keys=True, indent=2))
    return 0 if receipt["status"] in ("NOT_REQUESTED", "OBSERVED") else 2


if __name__ == "__main__":
    raise SystemExit(main())
