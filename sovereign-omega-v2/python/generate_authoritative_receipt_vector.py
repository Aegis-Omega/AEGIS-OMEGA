#!/usr/bin/env python3
"""Generate the deterministic Python cross-runtime receipt golden vector."""
from __future__ import annotations

import argparse
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from authoritative_receipts import (
    AuthoritativeReceiptAuthority,
    ReceiptBindings,
    SQLiteReceiptStore,
    ZERO_HASH,
    create_trust_registry,
)
from canonical_envelope import canon


OPERATOR_KEY_ID = "operator-root-v1"
OPERATOR_PRIVATE = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
OPERATOR_PUBLIC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
SIGNER_KEY_ID = "cross-runtime-witness-v1"
SIGNER_PRIVATE = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
SIGNER_PUBLIC = "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
AUTHORITY_DOMAIN = "repository:mutation"

ALL_RECEIPT_KINDS = tuple(sorted((
    "LEASE_ISSUED",
    "LEASE_ISSUANCE_DENIED",
    "LEASE_RENEWED",
    "LEASE_RENEWAL_DENIED",
    "LEASE_EXPIRED",
    "LEASE_REVOKED",
    "MUTATION_ADMITTED",
    "MUTATION_DENIED",
    "MUTATION_COMPLETED",
    "MUTATION_CANCELLED",
    "MUTATION_FAILED",
), key=lambda item: item.encode("utf-8")))


def _h(character: str) -> str:
    return character * 64


def _bindings() -> ReceiptBindings:
    return ReceiptBindings(
        actor_identity_root=_h("1"),
        session_identity_root=_h("2"),
        workspace_identity_root=_h("3"),
        holon_identity_root=_h("4"),
        authority_domain=AUTHORITY_DOMAIN,
        authority_level="D2",
    )


def _registry() -> dict[str, Any]:
    return create_trust_registry(
        {
            "registry_version": "1",
            "previous_registry_root": ZERO_HASH,
            "issued_at_ms": "90",
            "valid_from_ms": "100",
            "expires_at_ms": "10000",
            "operator_key_id": OPERATOR_KEY_ID,
            "keys": [{
                "key_id": SIGNER_KEY_ID,
                "public_key": SIGNER_PUBLIC,
                "verifier_identity_root": _h("7"),
                "valid_from_ms": "100",
                "expires_at_ms": "9000",
                "status": "ACTIVE",
                "authority_domains": [AUTHORITY_DOMAIN],
                "receipt_kinds": list(ALL_RECEIPT_KINDS),
            }],
        },
        OPERATOR_PRIVATE,
    )


def build_python_cross_runtime_vector() -> dict[str, Any]:
    """Build one valid chain containing every V1 receipt kind."""

    registry = _registry()
    bindings = _bindings()
    with TemporaryDirectory() as temporary:
        store = SQLiteReceiptStore(Path(temporary) / "receipts.sqlite3")
        authority = AuthoritativeReceiptAuthority(
            store=store,
            current_registry=registry,
            pinned_operator_public_key_hex=OPERATOR_PUBLIC,
            expected_operator_key_id=OPERATOR_KEY_ID,
            expected_registry_root=registry["registry_root"],
            signer_key_id=SIGNER_KEY_ID,
            signer_private_key_hex=SIGNER_PRIVATE,
            verification_time_ms="1000",
        )
        receipts: list[dict[str, Any]] = []

        receipts.append(authority.issue_lease(
            bindings=bindings,
            lease_id=_h("4"),
            observed_state_root=_h("f"),
            expected_state_root=_h("f"),
            action_digest=_h("1"),
            timestamp_ms="1000",
            expires_at_ms="900",
            nonce="vector-lease-denied-01",
        ))

        authority.update_observed_time("1100")
        issued = authority.issue_lease(
            bindings=bindings,
            lease_id=_h("5"),
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("b"),
            timestamp_ms="1100",
            expires_at_ms="3000",
            nonce="vector-lease-issued-01",
        )
        receipts.append(issued)

        authority.update_observed_time("1200")
        receipts.append(authority.renew_lease(
            bindings=bindings,
            lease_id=_h("5"),
            lease_generation="0",
            fencing_token=_h("9"),
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("b"),
            timestamp_ms="1200",
            expires_at_ms="4000",
            nonce="vector-renew-denied-01",
        ))

        current = authority.current_lease(bindings)
        assert current is not None
        authority.update_observed_time("1300")
        renewed = authority.renew_lease(
            bindings=bindings,
            lease_id=current["lease_id"],
            lease_generation=current["lease_generation"],
            fencing_token=current["fencing_token"],
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("b"),
            timestamp_ms="1300",
            expires_at_ms="4000",
            nonce="vector-lease-renewed-1",
        )
        receipts.append(renewed)

        current = authority.current_lease(bindings)
        assert current is not None
        authority.update_observed_time("1400")
        receipts.append(authority.deny_mutation(
            bindings=bindings,
            lease_id=current["lease_id"],
            lease_generation=current["lease_generation"],
            fencing_token=current["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=renewed["receipt_id"],
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("d"),
            timestamp_ms="1400",
            expires_at_ms="4000",
            nonce="vector-mutation-deny-01",
            denial_codes=("POLICY_DENIED",),
            result_digest=_h("4"),
        ))

        authority.update_observed_time("1500")
        admitted = authority.admit_mutation(
            bindings=bindings,
            lease_id=current["lease_id"],
            lease_generation=current["lease_generation"],
            fencing_token=current["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=renewed["receipt_id"],
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("b"),
            timestamp_ms="1500",
            nonce="vector-mutation-admit-1",
        )
        receipts.append(admitted)

        authority.update_observed_time("1600")
        completed = authority.complete_mutation(
            bindings=bindings,
            lease_id=current["lease_id"],
            lease_generation=current["lease_generation"],
            fencing_token=current["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=renewed["receipt_id"],
            observed_state_root=_h("a"),
            expected_state_root=_h("a"),
            action_digest=_h("b"),
            timestamp_ms="1600",
            nonce="vector-mutation-done-01",
            result_digest=_h("f"),
            after_state_root=_h("e"),
        )
        receipts.append(completed)

        authority.update_observed_time("1700")
        issued_for_cancel = authority.issue_lease(
            bindings=bindings,
            lease_id=_h("6"),
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("7"),
            timestamp_ms="1700",
            expires_at_ms="2000",
            nonce="vector-cancel-lease-001",
        )
        receipts.append(issued_for_cancel)
        cancel_lease = authority.current_lease(bindings)
        assert cancel_lease is not None

        authority.update_observed_time("1800")
        receipts.append(authority.admit_mutation(
            bindings=bindings,
            lease_id=cancel_lease["lease_id"],
            lease_generation=cancel_lease["lease_generation"],
            fencing_token=cancel_lease["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=issued_for_cancel["receipt_id"],
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("7"),
            timestamp_ms="1800",
            nonce="vector-cancel-admit-01",
        ))

        authority.update_observed_time("2000")
        receipts.append(authority.expire_lease(
            bindings=bindings,
            lease_id=cancel_lease["lease_id"],
            lease_generation=cancel_lease["lease_generation"],
            fencing_token=cancel_lease["fencing_token"],
            observed_state_root=_h("e"),
            action_digest=_h("7"),
            timestamp_ms="2000",
            nonce="vector-lease-expired-1",
        ))

        authority.update_observed_time("2100")
        receipts.append(authority.cancel_mutation(
            bindings=bindings,
            lease_id=cancel_lease["lease_id"],
            lease_generation=cancel_lease["lease_generation"],
            fencing_token=cancel_lease["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=issued_for_cancel["receipt_id"],
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("7"),
            timestamp_ms="2100",
            nonce="vector-mutation-cancel1",
            result_digest=_h("8"),
            denial_code="CANCELLED_AFTER_EXPIRY",
        ))

        authority.update_observed_time("2200")
        issued_for_failure = authority.issue_lease(
            bindings=bindings,
            lease_id=_h("9"),
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("a"),
            timestamp_ms="2200",
            expires_at_ms="4000",
            nonce="vector-failure-lease-1",
        )
        receipts.append(issued_for_failure)
        failure_lease = authority.current_lease(bindings)
        assert failure_lease is not None

        authority.update_observed_time("2300")
        receipts.append(authority.admit_mutation(
            bindings=bindings,
            lease_id=failure_lease["lease_id"],
            lease_generation=failure_lease["lease_generation"],
            fencing_token=failure_lease["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=issued_for_failure["receipt_id"],
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("a"),
            timestamp_ms="2300",
            nonce="vector-failure-admit-1",
        ))

        authority.update_observed_time("2400")
        receipts.append(authority.revoke_lease(
            bindings=bindings,
            lease_id=failure_lease["lease_id"],
            lease_generation=failure_lease["lease_generation"],
            fencing_token=failure_lease["fencing_token"],
            observed_state_root=_h("e"),
            action_digest=_h("a"),
            timestamp_ms="2400",
            nonce="vector-lease-revoked-1",
            reason="OPERATOR_REVOKED",
        ))

        authority.update_observed_time("2500")
        terminal = authority.fail_mutation(
            bindings=bindings,
            lease_id=failure_lease["lease_id"],
            lease_generation=failure_lease["lease_generation"],
            fencing_token=failure_lease["fencing_token"],
            authority_receipt_hash=_h("c"),
            lease_authorization_receipt_hash=issued_for_failure["receipt_id"],
            observed_state_root=_h("e"),
            expected_state_root=_h("e"),
            action_digest=_h("a"),
            timestamp_ms="2500",
            nonce="vector-mutation-fail-01",
            result_digest=_h("b"),
            denial_code="FAILED_AFTER_REVOCATION",
        )
        receipts.append(terminal)
        store.close()

    return {
        "schema_version": "1.0.0",
        "operator_public_key": OPERATOR_PUBLIC,
        "registry": registry,
        "receipts": receipts,
        "terminal_receipt_id": terminal["receipt_id"],
        "context": {
            "operator_key_id": OPERATOR_KEY_ID,
            "accepted_registry_roots": [registry["registry_root"]],
            "observed_at_ms": "3000",
            "max_clock_skew_ms": "0",
            "expected_actor_identity_root": bindings.actor_identity_root,
            "expected_session_identity_root": bindings.session_identity_root,
            "expected_workspace_identity_root": bindings.workspace_identity_root,
            "expected_holon_identity_root": bindings.holon_identity_root,
            "expected_authority_domain": bindings.authority_domain,
            "expected_authority_level": bindings.authority_level,
            "expected_observed_state_root": _h("e"),
            "expected_action_digest": _h("a"),
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canon(build_python_cross_runtime_vector()) + b"\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
