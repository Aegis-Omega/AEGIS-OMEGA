#!/usr/bin/env python3
"""Focused and adversarial tests for cross-runtime authoritative receipts."""
from __future__ import annotations

import copy
import json
import sqlite3
import sys
import threading
from dataclasses import FrozenInstanceError
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase, main

PYTHON_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(PYTHON_ROOT))

from authoritative_receipts import (  # noqa: E402
    AuthoritativeReceiptAuthority,
    AuthoritativeReceiptError,
    ReceiptBindings,
    ReceiptStoreConflict,
    SQLiteReceiptStore,
    ZERO_HASH,
    assert_i_json,
    canonical_receipt_signature_message,
    canonical_registry_signature_message,
    compute_receipt_id,
    compute_registry_root,
    create_trust_registry,
    load_json_strict,
    public_key_hex_from_private,
    sign_receipt,
    verify_receipt,
    verify_registry_rotation,
    verify_trust_registry,
)
from canonical_envelope import canon, sha256_hex  # noqa: E402
from generate_authoritative_receipt_vector import (  # noqa: E402
    build_python_cross_runtime_vector,
)


OPERATOR_KEY_ID = "operator-root-v1"
OPERATOR_PRIVATE = "9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60"
OPERATOR_PUBLIC = "d75a980182b10ab7d54bfed3c964073a0ee172f3daa62325af021a68f707511a"
SIGNER_KEY_ID = "python-witness-v1"
SIGNER_PRIVATE = "4ccd089b28ff96da9db6c346ec114e0f5b8a319f35aba624da8cf6ed4fb8a6fb"
SIGNER_PUBLIC = "3d4017c3e843895a92b70aa74d1b7ebc9c982ccf2ec4968cc0cd55f12af4660c"
ROTATED_KEY_ID = "python-witness-v2"
ROTATED_PRIVATE = "c5aa8df43f9f837bedb7442f31dcb7b166d38535076f094b85ce3a2e0b4458f7"
ROTATED_PUBLIC = "fc51cd8e6218a1a38da47ed00230f0580816ed13ba3303ac5deb911548908025"

ALL_KINDS = tuple(sorted((
    "LEASE_ISSUED", "LEASE_ISSUANCE_DENIED", "LEASE_RENEWED", "LEASE_RENEWAL_DENIED",
    "LEASE_EXPIRED", "LEASE_REVOKED", "MUTATION_ADMITTED", "MUTATION_DENIED",
    "MUTATION_COMPLETED", "MUTATION_CANCELLED", "MUTATION_FAILED",
), key=lambda item: item.encode("utf-8")))


def H(character: str) -> str:
    return character * 64


def build_registry(
    *,
    version: str = "1",
    previous_root: str = ZERO_HASH,
    key_id: str = SIGNER_KEY_ID,
    public_key: str = SIGNER_PUBLIC,
    verifier_root: str = H("7"),
    issued_at_ms: str = "90",
    valid_from_ms: str = "100",
    expires_at_ms: str = "10000",
    key_valid_from_ms: str = "100",
    key_expires_at_ms: str = "9000",
    status: str = "ACTIVE",
    operator_key_id: str = OPERATOR_KEY_ID,
) -> dict:
    body = {
        "registry_version": version,
        "previous_registry_root": previous_root,
        "issued_at_ms": issued_at_ms,
        "valid_from_ms": valid_from_ms,
        "expires_at_ms": expires_at_ms,
        "operator_key_id": operator_key_id,
        "keys": [{
            "key_id": key_id,
            "public_key": public_key,
            "verifier_identity_root": verifier_root,
            "valid_from_ms": key_valid_from_ms,
            "expires_at_ms": key_expires_at_ms,
            "status": status,
            "authority_domains": ["repository:mutation"],
            "receipt_kinds": list(ALL_KINDS),
        }],
    }
    return create_trust_registry(body, OPERATOR_PRIVATE)


def verify_registry(registry: dict, *, now: str = "8000"):
    return verify_trust_registry(
        registry,
        pinned_operator_public_key_hex=OPERATOR_PUBLIC,
        expected_operator_key_id=OPERATOR_KEY_ID,
        expected_registry_root=registry["registry_root"],
        expected_registry_version=registry["registry_body"]["registry_version"],
        verification_time_ms=now,
    )


def bindings() -> ReceiptBindings:
    return ReceiptBindings(
        actor_identity_root=H("1"),
        session_identity_root=H("2"),
        workspace_identity_root=H("3"),
        holon_identity_root=H("4"),
        authority_domain="repository:mutation",
        authority_level="D2",
    )


def create_authority(path: Path, registry: dict | None = None, **changes):
    registry = registry or build_registry()
    values = dict(
        store=SQLiteReceiptStore(path),
        current_registry=registry,
        pinned_operator_public_key_hex=OPERATOR_PUBLIC,
        expected_operator_key_id=OPERATOR_KEY_ID,
        expected_registry_root=registry["registry_root"],
        signer_key_id=SIGNER_KEY_ID,
        signer_private_key_hex=SIGNER_PRIVATE,
        verification_time_ms="1000",
    )
    values.update(changes)
    return AuthoritativeReceiptAuthority(**values)


def issue(authority: AuthoritativeReceiptAuthority, *, nonce="nonce-lease-00001", lease_id=H("5"), expires="3000"):
    return authority.issue_lease(
        bindings=bindings(), lease_id=lease_id, observed_state_root=H("a"),
        expected_state_root=H("a"), action_digest=H("b"), timestamp_ms="1000",
        expires_at_ms=expires, nonce=nonce,
    )


def admit(authority: AuthoritativeReceiptAuthority, lease_receipt: dict, *, action=H("c"), nonce="nonce-admit-00001", fence=None, expected=H("a")):
    authority.update_observed_time("1100")
    lease = authority.current_lease(bindings())
    assert lease is not None
    return authority.admit_mutation(
        bindings=bindings(), lease_id=lease["lease_id"],
        lease_generation=lease["lease_generation"],
        fencing_token=fence or lease["fencing_token"],
        authority_receipt_hash=H("d"),
        lease_authorization_receipt_hash=lease_receipt["receipt_id"],
        observed_state_root=authority.canonical_state_root(bindings()),
        expected_state_root=expected, action_digest=action,
        timestamp_ms="1100", nonce=nonce,
    )


def complete(authority: AuthoritativeReceiptAuthority, lease_receipt: dict, *, action=H("c"), nonce="nonce-complete-001", after=H("e"), result=H("f")):
    authority.update_observed_time("1200")
    lease = authority.current_lease(bindings())
    assert lease is not None
    state = authority.canonical_state_root(bindings())
    return authority.complete_mutation(
        bindings=bindings(), lease_id=lease["lease_id"], lease_generation=lease["lease_generation"],
        fencing_token=lease["fencing_token"], authority_receipt_hash=H("d"),
        lease_authorization_receipt_hash=lease_receipt["receipt_id"],
        observed_state_root=state, expected_state_root=state, action_digest=action,
        timestamp_ms="1200", nonce=nonce, after_state_root=after, result_digest=result,
    )


def build_golden_vector() -> dict:
    """Deterministic Python vector helper consumed by cross-runtime tests."""
    with TemporaryDirectory() as temporary:
        path = Path(temporary) / "receipts.sqlite3"
        registry = build_registry()
        authority = create_authority(path, registry)
        lease_receipt = issue(authority)
        admitted = admit(authority, lease_receipt)
        terminal = complete(authority, lease_receipt)
        authority._store.close()
        return {
            "schema_version": "1.0.0",
            "producer_runtime": "python",
            "operator_public_key": OPERATOR_PUBLIC,
            "registry": registry,
            "receipts": [lease_receipt, admitted, terminal],
            "terminal_receipt_id": terminal["receipt_id"],
            "context": {
                "operator_key_id": OPERATOR_KEY_ID,
                "accepted_registry_roots": [registry["registry_root"]],
                "observed_at_ms": "1200",
                "max_clock_skew_ms": "0",
                "expected_actor_identity_root": H("1"),
                "expected_session_identity_root": H("2"),
                "expected_workspace_identity_root": H("3"),
                "expected_holon_identity_root": H("4"),
                "expected_authority_domain": "repository:mutation",
                "expected_authority_level": "D2",
                "expected_observed_state_root": H("a"),
                "expected_action_digest": H("c"),
            },
        }


class AuthoritativeReceiptTests(TestCase):
    def setUp(self) -> None:
        self.temporary = TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.path = Path(self.temporary.name) / "receipts.sqlite3"

    def test_01_registry_signature_root_and_external_pins(self):
        registry = build_registry()
        verified = verify_registry(registry)
        self.assertEqual(verified.registry_root, compute_registry_root(registry))
        self.assertEqual(public_key_hex_from_private(OPERATOR_PRIVATE), OPERATOR_PUBLIC)
        self.assertEqual(public_key_hex_from_private(SIGNER_PRIVATE), SIGNER_PUBLIC)
        self.assertTrue(canonical_registry_signature_message(registry).startswith(b'{"domain"'))
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_OPERATOR_KEY_ID_MISMATCH"):
            verify_trust_registry(
                registry, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
                expected_operator_key_id="wrong-operator", expected_registry_root=registry["registry_root"],
            )
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_NOT_EXPECTED"):
            verify_trust_registry(
                registry, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
                expected_operator_key_id=OPERATOR_KEY_ID, expected_registry_root=H("9"),
            )

    def test_02_registry_tamper_sort_duplicate_and_intervals_rejected(self):
        registry = build_registry()
        tampered = copy.deepcopy(registry)
        tampered["registry_body"]["keys"][0]["status"] = "REVOKED"
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_ROOT_MISMATCH"):
            verify_registry(tampered)

        body = copy.deepcopy(registry["registry_body"])
        second = copy.deepcopy(body["keys"][0])
        second["key_id"] = "aaa-earlier-key"
        body["keys"].append(second)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_KEYS_NONCANONICAL"):
            create_trust_registry(body, OPERATOR_PRIVATE)

        body = copy.deepcopy(registry["registry_body"])
        second = copy.deepcopy(body["keys"][0])
        second["key_id"] = "zz-second-key"
        body["keys"].append(second)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_PUBLIC_KEYS_DUPLICATE"):
            create_trust_registry(body, OPERATOR_PRIVATE)

        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_TIME_WINDOW_INVALID"):
            build_registry(valid_from_ms="100", expires_at_ms="100")

    def test_03_strict_i_json_and_duplicate_json_keys(self):
        for invalid in ({"x": 1.5}, {"x": 2**60}, {"x": b"bytes"}, {"x": (1, 2)}):
            with self.subTest(invalid=invalid), self.assertRaises(AuthoritativeReceiptError):
                assert_i_json(invalid)
        cyclic: list = []
        cyclic.append(cyclic)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "I_JSON_CYCLE"):
            assert_i_json(cyclic)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "JSON_DUPLICATE_KEY"):
            load_json_strict('{"x":1,"x":2}')

    def test_04_python_golden_vector_matches_schemas_and_derivations(self):
        vector = build_golden_vector()
        self.assertEqual([item["receipt_kind"] for item in vector["receipts"]], [
            "LEASE_ISSUED", "MUTATION_ADMITTED", "MUTATION_COMPLETED",
        ])
        self.assertEqual([item["receipt_body"]["receipt_sequence"] for item in vector["receipts"]], ["0", "1", "2"])
        self.assertEqual(vector["receipts"][0]["receipt_body"]["parent_receipt_hash"], ZERO_HASH)
        self.assertEqual(vector["receipts"][1]["receipt_body"]["parent_receipt_hash"], vector["receipts"][0]["receipt_id"])
        self.assertEqual(vector["receipts"][2]["receipt_body"]["parent_receipt_hash"], vector["receipts"][1]["receipt_id"])
        for receipt in vector["receipts"]:
            self.assertEqual(receipt["receipt_id"], compute_receipt_id(receipt))
            self.assertTrue(canonical_receipt_signature_message(receipt).startswith(b'{"domain"'))
        try:
            import jsonschema
        except ImportError:  # pragma: no cover
            self.skipTest("jsonschema unavailable")
        receipt_schema = json.loads((REPO_ROOT / "schemas/cross-runtime-receipt-envelope.v1.schema.json").read_text(encoding="utf-8"))
        registry_schema = json.loads((REPO_ROOT / "schemas/receipt-trust-registry.v1.schema.json").read_text(encoding="utf-8"))
        jsonschema.validate(vector["registry"], registry_schema)
        for receipt in vector["receipts"]:
            jsonschema.validate(receipt, receipt_schema)

    def test_05_receipt_tamper_unsigned_unknown_root_and_clock_skew_rejected(self):
        registry_document = build_registry()
        registry = verify_registry(registry_document)
        vector = build_golden_vector()["receipts"][0]
        verify_receipt(vector, registry=registry, verification_time_ms="1000")
        tampered = copy.deepcopy(vector)
        tampered["receipt_body"]["nonce"] = "nonce-tampered-0001"
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_ID_MISMATCH"):
            verify_receipt(tampered, registry=registry, verification_time_ms="1000")
        unsigned = copy.deepcopy(vector)
        unsigned["proof"]["signature"] = "0" * 128
        unsigned["receipt_id"] = compute_receipt_id(unsigned)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_SIGNATURE_INVALID"):
            verify_receipt(unsigned, registry=registry, verification_time_ms="1000")
        unknown = copy.deepcopy(vector)
        unknown["proof"]["signer_key_id"] = "unknown-key"
        unknown["receipt_id"] = compute_receipt_id(unknown)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_SIGNER_UNKNOWN"):
            verify_receipt(unknown, registry=registry, verification_time_ms="1000")
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_TIMESTAMP_IN_FUTURE"):
            verify_receipt(vector, registry=registry, verification_time_ms="998", max_clock_skew_ms="1")
        unresolved_fence = copy.deepcopy(vector)
        unresolved_fence["receipt_body"]["fencing_token"] = ZERO_HASH
        with self.assertRaisesRegex(AuthoritativeReceiptError, "fencing_token:UNRESOLVED"):
            verify_receipt(unresolved_fence, registry=registry, verification_time_ms="1000")

    def test_06_success_state_root_and_restart_readback(self):
        registry = build_registry()
        authority = create_authority(self.path, registry)
        lease_receipt = issue(authority)
        admitted = admit(authority, lease_receipt)
        terminal = complete(authority, lease_receipt)
        self.assertEqual(terminal["receipt_body"]["before_state_root"], H("a"))
        self.assertEqual(terminal["receipt_body"]["after_state_root"], H("e"))
        self.assertEqual(terminal["receipt_body"]["result_digest"], H("f"))
        self.assertEqual(authority.canonical_state_root(bindings()), H("e"))
        self.assertEqual(authority.head_receipt_id, terminal["receipt_id"])
        self.assertIsNone(authority.current_lease(bindings()))
        authority._store.close()

        recovered = create_authority(self.path, registry, verification_time_ms="1200")
        self.assertEqual(recovered.canonical_state_root(bindings()), H("e"))
        self.assertEqual(recovered.head_receipt_id, terminal["receipt_id"])
        self.assertEqual(recovered._store.read_receipt(admitted["receipt_id"]), admitted)
        recovered._store.close()

    def test_07_denied_genesis_does_not_initialize_state(self):
        authority = create_authority(self.path)
        first = issue(authority, expires="900")
        self.assertEqual(first["receipt_kind"], "LEASE_ISSUANCE_DENIED")
        self.assertEqual(first["receipt_body"]["before_state_root"], first["receipt_body"]["after_state_root"])
        self.assertIsNone(authority.canonical_state_root(bindings()))
        authority._store.close()

    def test_08_stale_state_fence_and_lease_link_are_signed_denials_with_no_change(self):
        authority = create_authority(self.path)
        lease_receipt = issue(authority)
        baseline = authority.canonical_state_root(bindings())
        stale_state = admit(authority, lease_receipt, action=H("6"), nonce="nonce-stale-state01", expected=H("9"))
        self.assertEqual(stale_state["receipt_kind"], "MUTATION_DENIED")
        self.assertIn("EXPECTED_STATE_STALE", stale_state["receipt_body"]["denial_codes"])
        stale_fence = admit(authority, lease_receipt, action=H("7"), nonce="nonce-stale-fence01", fence=H("8"))
        self.assertIn("STALE_FENCING_TOKEN", stale_fence["receipt_body"]["denial_codes"])
        wrong_link = copy.deepcopy(lease_receipt)
        wrong_link["receipt_id"] = H("9")
        link_denial = admit(authority, wrong_link, action=H("8"), nonce="nonce-wrong-link-01")
        self.assertIn("LEASE_AUTHORIZATION_RECEIPT_MISMATCH", link_denial["receipt_body"]["denial_codes"])
        for denied in (stale_state, stale_fence, link_denial):
            self.assertEqual(denied["receipt_body"]["before_state_root"], baseline)
            self.assertEqual(denied["receipt_body"]["after_state_root"], baseline)
        self.assertEqual(authority.canonical_state_root(bindings()), baseline)
        authority._store.close()

    def test_09_denied_digest_cannot_promote_after_restart(self):
        registry = build_registry()
        authority = create_authority(self.path, registry)
        lease_receipt = issue(authority)
        action = H("6")
        first = admit(authority, lease_receipt, action=action, nonce="nonce-denied-first1", expected=H("9"))
        self.assertEqual(first["receipt_kind"], "MUTATION_DENIED")
        authority._store.close()
        recovered = create_authority(self.path, registry, verification_time_ms="1100")
        replay = admit(recovered, lease_receipt, action=action, nonce="nonce-denied-replay", expected=H("a"))
        self.assertEqual(replay["receipt_kind"], "MUTATION_DENIED")
        self.assertIn("MUTATION_REPLAY", replay["receipt_body"]["denial_codes"])
        self.assertEqual(recovered.canonical_state_root(bindings()), H("a"))
        recovered._store.close()

    def test_10_renewal_expiry_and_revocation_receipts(self):
        authority = create_authority(self.path)
        issued = issue(authority)
        authority.update_observed_time("1500")
        lease = authority.current_lease(bindings())
        renewal = authority.renew_lease(
            bindings=bindings(), lease_id=lease["lease_id"], lease_generation=lease["lease_generation"],
            fencing_token=lease["fencing_token"], observed_state_root=H("a"), expected_state_root=H("a"),
            action_digest=H("b"), timestamp_ms="1500", expires_at_ms="4000", nonce="nonce-renewal-0001",
        )
        self.assertEqual(renewal["receipt_kind"], "LEASE_RENEWED")
        authority.update_observed_time("1600")
        lease = authority.current_lease(bindings())
        denied = authority.renew_lease(
            bindings=bindings(), lease_id=lease["lease_id"], lease_generation="1",
            fencing_token=issued["receipt_body"]["fencing_token"], observed_state_root=H("a"), expected_state_root=H("a"),
            action_digest=H("b"), timestamp_ms="1600", expires_at_ms="5000", nonce="nonce-renew-denied1",
        )
        self.assertEqual(denied["receipt_kind"], "LEASE_RENEWAL_DENIED")
        retained_lease = dict(lease)
        authority.update_observed_time("4000")
        self.assertIsNone(authority.current_lease(bindings()))
        expired = authority.expire_lease(
            bindings=bindings(), lease_id=retained_lease["lease_id"], lease_generation=retained_lease["lease_generation"],
            fencing_token=retained_lease["fencing_token"], observed_state_root=H("a"), action_digest=H("b"),
            timestamp_ms="4000", nonce="nonce-expired-00001",
        )
        self.assertEqual(expired["receipt_kind"], "LEASE_EXPIRED")
        self.assertEqual(expired["receipt_body"]["before_state_root"], expired["receipt_body"]["after_state_root"])
        authority._store.close()

        other = create_authority(Path(self.temporary.name) / "revoke.sqlite3")
        issued = issue(other)
        other.update_observed_time("1300")
        lease = other.current_lease(bindings())
        revoked = other.revoke_lease(
            bindings=bindings(), lease_id=lease["lease_id"], lease_generation=lease["lease_generation"],
            fencing_token=lease["fencing_token"], observed_state_root=H("a"), action_digest=H("b"),
            timestamp_ms="1300", nonce="nonce-revoked-00001",
        )
        self.assertEqual(revoked["receipt_kind"], "LEASE_REVOKED")
        self.assertEqual(revoked["receipt_body"]["before_state_root"], revoked["receipt_body"]["after_state_root"])
        other._store.close()

    def test_11_cancel_and_fail_are_terminal_unchanged_receipts(self):
        for method_name, expected_kind, suffix in (
            ("cancel_mutation", "MUTATION_CANCELLED", "cancel"),
            ("fail_mutation", "MUTATION_FAILED", "failure"),
        ):
            with self.subTest(kind=expected_kind):
                path = Path(self.temporary.name) / f"{suffix}.sqlite3"
                authority = create_authority(path)
                lease_receipt = issue(authority)
                action = H("6" if suffix == "cancel" else "7")
                admit(authority, lease_receipt, action=action, nonce=f"nonce-{suffix}-admit01")
                authority.update_observed_time("1200")
                lease = authority.current_lease(bindings())
                before = authority.canonical_state_root(bindings())
                terminal = getattr(authority, method_name)(
                    bindings=bindings(), lease_id=lease["lease_id"], lease_generation=lease["lease_generation"],
                    fencing_token=lease["fencing_token"], authority_receipt_hash=H("d"),
                    lease_authorization_receipt_hash=lease_receipt["receipt_id"],
                    observed_state_root=before, expected_state_root=before, action_digest=action,
                    timestamp_ms="1200", nonce=f"nonce-{suffix}-term-01", result_digest=H("8"),
                )
                self.assertEqual(terminal["receipt_kind"], expected_kind)
                self.assertEqual(terminal["receipt_body"]["before_state_root"], before)
                self.assertEqual(terminal["receipt_body"]["after_state_root"], before)
                self.assertEqual(authority.canonical_state_root(bindings()), before)
                authority._store.close()

    def test_12_single_authority_concurrency_emits_one_issue_and_signed_denials(self):
        authority = create_authority(self.path)
        barrier = threading.Barrier(12)
        receipts: list[dict] = []
        failures: list[BaseException] = []
        result_lock = threading.Lock()

        def worker(index: int) -> None:
            try:
                barrier.wait()
                receipt = issue(
                    authority,
                    lease_id=f"{index + 1:064x}",
                    nonce=f"nonce-concurrent-{index:03d}",
                )
                with result_lock:
                    receipts.append(receipt)
            except BaseException as exc:  # pragma: no cover - asserted empty
                with result_lock:
                    failures.append(exc)

        threads = [threading.Thread(target=worker, args=(index,)) for index in range(12)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
        self.assertEqual(failures, [])
        self.assertEqual(sum(item["receipt_kind"] == "LEASE_ISSUED" for item in receipts), 1)
        self.assertEqual(sum(item["receipt_kind"] == "LEASE_ISSUANCE_DENIED" for item in receipts), 11)
        self.assertEqual(len({item["receipt_id"] for item in receipts}), 12)
        authority._store.close()

    def test_13_two_store_instances_use_compare_and_append(self):
        registry = verify_registry(build_registry())
        store_a = SQLiteReceiptStore(self.path)
        store_b = SQLiteReceiptStore(self.path)
        base = {
            "receipt_sequence": "0", "actor_identity_root": H("1"), "session_identity_root": H("2"),
            "workspace_identity_root": H("3"), "holon_identity_root": H("4"),
            "authority_domain": "repository:mutation", "authority_level": "D2",
            "authority_receipt_hash": ZERO_HASH, "lease_id": H("5"), "lease_generation": "1",
            "fencing_token": H("6"), "lease_authorization_receipt_hash": ZERO_HASH,
            "parent_receipt_hash": ZERO_HASH, "observed_state_root": H("a"), "expected_state_root": H("a"),
            "action_digest": H("b"), "before_state_root": H("a"), "after_state_root": H("a"),
            "result_digest": H("c"), "timestamp_ms": "1000", "expires_at_ms": "3000",
            "nonce": "nonce-store-cas-001", "outcome": "ADMITTED", "denial_codes": [],
        }
        first = sign_receipt(
            receipt_kind="LEASE_ISSUED", receipt_body=base, registry=registry,
            signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
        )
        competing_body = copy.deepcopy(base)
        competing_body["lease_id"] = H("7")
        competing_body["nonce"] = "nonce-store-cas-002"
        competing = sign_receipt(
            receipt_kind="LEASE_ISSUED", receipt_body=competing_body, registry=registry,
            signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
        )
        store_a.persist_receipt(first, registry=registry, verification_time_ms="1000")
        with self.assertRaises(ReceiptStoreConflict):
            store_b.persist_receipt(competing, registry=registry, verification_time_ms="1000")
        store_a.close(); store_b.close()

    def test_14_readback_failure_rolls_back_without_orphan_promotion(self):
        class ReadbackFailStore(SQLiteReceiptStore):
            def _read_pending_receipt_bytes(self, receipt_id: str):
                return None

        registry = build_registry()
        store = ReadbackFailStore(self.path)
        authority = AuthoritativeReceiptAuthority(
            store=store, current_registry=registry, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
            expected_operator_key_id=OPERATOR_KEY_ID, expected_registry_root=registry["registry_root"],
            signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE, verification_time_ms="1000",
        )
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_READBACK_MISMATCH"):
            issue(authority)
        self.assertEqual(authority.head_receipt_id, ZERO_HASH)
        self.assertIsNone(authority.canonical_state_root(bindings()))
        store.close()
        recovered = create_authority(self.path, registry)
        self.assertIsNone(recovered.canonical_state_root(bindings()))
        self.assertEqual(recovered.head_receipt_id, ZERO_HASH)
        self.assertEqual(recovered._store.read_all_receipts(), ())
        recovered._store.close()

    def test_15_key_rotation_and_historical_restart_verification(self):
        first_registry = build_registry(expires_at_ms="20000", key_expires_at_ms="15000")
        authority = create_authority(self.path, first_registry, verification_time_ms="1000")
        issued = issue(authority)
        second_registry = build_registry(
            version="2", previous_root=first_registry["registry_root"], key_id=ROTATED_KEY_ID,
            public_key=ROTATED_PUBLIC, verifier_root=H("8"), issued_at_ms="1300",
            valid_from_ms="1300", expires_at_ms="20000", key_valid_from_ms="1300",
            key_expires_at_ms="19000",
        )
        verified_second = verify_trust_registry(
            second_registry, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
            expected_operator_key_id=OPERATOR_KEY_ID, expected_registry_root=second_registry["registry_root"],
            verification_time_ms="1400",
        )
        verify_registry_rotation(verify_registry(first_registry, now="1000"), verified_second)
        authority.rotate_registry(
            second_registry, expected_registry_root=second_registry["registry_root"], verification_time_ms="1400",
            signer_key_id=ROTATED_KEY_ID, signer_private_key_hex=ROTATED_PRIVATE,
        )
        authority._store.close()
        recovered = create_authority(
            self.path, second_registry, expected_registry_root=second_registry["registry_root"],
            signer_key_id=ROTATED_KEY_ID, signer_private_key_hex=ROTATED_PRIVATE, verification_time_ms="1400",
        )
        self.assertEqual(recovered.head_receipt_id, issued["receipt_id"])
        self.assertEqual(recovered.current_lease(bindings())["lease_id"], H("5"))
        recovered._store.close()

    def test_16_raw_sqlite_tamper_fails_restart(self):
        registry = build_registry()
        authority = create_authority(self.path, registry)
        receipt = issue(authority)
        authority._store.close()
        connection = sqlite3.connect(self.path)
        document = copy.deepcopy(receipt)
        document["receipt_body"]["nonce"] = "nonce-database-tamper"
        connection.execute(
            "UPDATE receipts SET canonical = ? WHERE receipt_id = ?",
            (sqlite3.Binary(canon(document)), receipt["receipt_id"]),
        )
        connection.commit(); connection.close()
        store = SQLiteReceiptStore(self.path)
        try:
            with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_STORED_BYTES_INVALID"):
                AuthoritativeReceiptAuthority(
                    store=store, current_registry=registry, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
                    expected_operator_key_id=OPERATOR_KEY_ID, expected_registry_root=registry["registry_root"],
                    signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
                    verification_time_ms="8000",
                )
        finally:
            store.close()

    def test_17_trusted_time_is_explicit_monotonic_and_expires_lease_views(self):
        authority = create_authority(self.path)
        issue(authority, expires="1500")
        authority.update_observed_time("1499")
        self.assertIsNotNone(authority.current_lease(bindings()))
        authority.update_observed_time("1500")
        self.assertIsNone(authority.current_lease(bindings()))
        with self.assertRaisesRegex(AuthoritativeReceiptError, "OBSERVED_TIME_REGRESSION"):
            authority.update_observed_time("1499")
        self.assertEqual(authority._verification_time_ms, "1500")
        authority._store.close()

    def test_18_failed_rotation_rolls_back_key_registry_and_observed_time(self):
        first = build_registry(expires_at_ms="20000", key_expires_at_ms="15000")
        authority = create_authority(self.path, first)
        second = build_registry(
            version="2", previous_root=first["registry_root"], key_id=ROTATED_KEY_ID,
            public_key=ROTATED_PUBLIC, verifier_root=H("8"), issued_at_ms="1300",
            valid_from_ms="1300", expires_at_ms="20000", key_valid_from_ms="1300",
            key_expires_at_ms="19000",
        )
        with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_SIGNING_KEY_MISMATCH"):
            authority.rotate_registry(
                second, expected_registry_root=second["registry_root"], verification_time_ms="1400",
                signer_key_id=ROTATED_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
            )
        self.assertEqual(authority._current_registry.registry_root, first["registry_root"])
        self.assertEqual(authority._signer_key_id, SIGNER_KEY_ID)
        self.assertEqual(authority._verification_time_ms, "1000")
        authority.update_observed_time("1400")
        receipt = issue(authority, lease_id=H("6"), nonce="nonce-after-rollback")
        self.assertEqual(receipt["proof"]["trust_registry_root"], first["registry_root"])
        authority._store.close()

    def test_19_cancel_and_failure_resolve_admission_after_lease_closure(self):
        cases = (("expire", "cancel_mutation"), ("revoke", "fail_mutation"))
        for index, (closure, terminal_method) in enumerate(cases):
            with self.subTest(closure=closure, terminal=terminal_method):
                path = Path(self.temporary.name) / f"closed-{index}.sqlite3"
                authority = create_authority(path)
                lease_receipt = issue(authority)
                action = H("6" if index == 0 else "7")
                admit(authority, lease_receipt, action=action, nonce=f"nonce-closed-admit-{index}")
                retained = dict(authority.current_lease(bindings()))
                if closure == "expire":
                    authority.update_observed_time("3000")
                    authority.expire_lease(
                        bindings=bindings(), lease_id=retained["lease_id"],
                        lease_generation=retained["lease_generation"], fencing_token=retained["fencing_token"],
                        observed_state_root=H("a"), action_digest=H("b"), timestamp_ms="3000",
                        nonce=f"nonce-closed-expire-{index}",
                    )
                    terminal_time = "3100"
                else:
                    authority.update_observed_time("1200")
                    authority.revoke_lease(
                        bindings=bindings(), lease_id=retained["lease_id"],
                        lease_generation=retained["lease_generation"], fencing_token=retained["fencing_token"],
                        observed_state_root=H("a"), action_digest=H("b"), timestamp_ms="1200",
                        nonce=f"nonce-closed-revoke-{index}",
                    )
                    terminal_time = "1300"
                authority.update_observed_time(terminal_time)
                terminal = getattr(authority, terminal_method)(
                    bindings=bindings(), lease_id=retained["lease_id"],
                    lease_generation=retained["lease_generation"], fencing_token=retained["fencing_token"],
                    authority_receipt_hash=H("d"), lease_authorization_receipt_hash=lease_receipt["receipt_id"],
                    observed_state_root=H("a"), expected_state_root=H("a"), action_digest=action,
                    timestamp_ms=terminal_time, nonce=f"nonce-closed-terminal-{index}", result_digest=H("8"),
                )
                self.assertIn(terminal["receipt_kind"], ("MUTATION_CANCELLED", "MUTATION_FAILED"))
                self.assertEqual(terminal["receipt_body"]["before_state_root"], H("a"))
                self.assertEqual(terminal["receipt_body"]["after_state_root"], H("a"))
                self.assertEqual(authority.canonical_state_root(bindings()), H("a"))
                authority._store.close()

    def test_20_registry_downgrade_receipt_is_rejected_during_restart(self):
        first = build_registry(expires_at_ms="20000", key_expires_at_ms="15000")
        authority = create_authority(self.path, first)
        issue(authority)
        second = build_registry(
            version="2", previous_root=first["registry_root"], key_id=ROTATED_KEY_ID,
            public_key=ROTATED_PUBLIC, verifier_root=H("8"), issued_at_ms="1300",
            valid_from_ms="1300", expires_at_ms="20000", key_valid_from_ms="1300",
            key_expires_at_ms="19000",
        )
        authority.rotate_registry(
            second, expected_registry_root=second["registry_root"], verification_time_ms="1400",
            signer_key_id=ROTATED_KEY_ID, signer_private_key_hex=ROTATED_PRIVATE,
        )
        authority.update_observed_time("1500")
        current = authority.issue_lease(
            bindings=bindings(), lease_id=H("6"), observed_state_root=H("a"), expected_state_root=H("a"),
            action_digest=H("7"), timestamp_ms="1500", expires_at_ms="4000", nonce="nonce-v2-receipt-001",
        )
        old_body = copy.deepcopy(current["receipt_body"])
        old_body.update({
            "receipt_sequence": "2", "parent_receipt_hash": current["receipt_id"],
            "lease_id": H("8"), "action_digest": H("9"), "timestamp_ms": "1600",
            "nonce": "nonce-downgrade-001",
        })
        old_registry = verify_registry(first, now="1600")
        downgrade = sign_receipt(
            receipt_kind="LEASE_ISSUANCE_DENIED", receipt_body=old_body, registry=old_registry,
            signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
        )
        authority._store.persist_receipt(downgrade, registry=old_registry, verification_time_ms="1600")
        authority._store.close()
        store = SQLiteReceiptStore(self.path)
        try:
            with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_TRUST_REGISTRY_DOWNGRADE"):
                AuthoritativeReceiptAuthority(
                    store=store, current_registry=second, pinned_operator_public_key_hex=OPERATOR_PUBLIC,
                    expected_operator_key_id=OPERATOR_KEY_ID, expected_registry_root=second["registry_root"],
                    signer_key_id=ROTATED_KEY_ID, signer_private_key_hex=ROTATED_PRIVATE,
                    verification_time_ms="1600",
                )
        finally:
            store.close()

    def test_21_workspace_holon_scope_isolation_and_registry_capability_immutability(self):
        authority = create_authority(self.path)
        issue(authority)
        other = ReceiptBindings(
            actor_identity_root=H("1"), session_identity_root=H("2"), workspace_identity_root=H("8"),
            holon_identity_root=H("9"), authority_domain="repository:mutation", authority_level="D2",
        )
        second = authority.issue_lease(
            bindings=other, lease_id=H("6"), observed_state_root=H("e"), expected_state_root=H("e"),
            action_digest=H("7"), timestamp_ms="1000", expires_at_ms="3000", nonce="nonce-other-scope-01",
        )
        self.assertEqual(second["receipt_kind"], "LEASE_ISSUED")
        self.assertEqual(authority.canonical_state_root(bindings()), H("a"))
        self.assertEqual(authority.canonical_state_root(other), H("e"))
        self.assertIsNotNone(authority.current_lease(bindings()))
        self.assertIsNotNone(authority.current_lease(other))
        verified = verify_registry(build_registry())
        mutable_copy = verified.document
        mutable_copy["registry_body"]["keys"][0]["status"] = "REVOKED"
        self.assertEqual(verified.entries[SIGNER_KEY_ID]["status"], "ACTIVE")
        with self.assertRaises(FrozenInstanceError):
            verified.registry_root = H("9")
        authority._store.close()

    def test_22_unresolved_roots_and_unsigned_store_appends_are_rejected(self):
        registry = verify_registry(build_registry(), now="1000")
        vector = build_golden_vector()["receipts"][0]
        unresolved = copy.deepcopy(vector)
        unresolved["receipt_body"]["expected_state_root"] = ZERO_HASH
        with self.assertRaisesRegex(AuthoritativeReceiptError, "expected_state_root:UNRESOLVED"):
            sign_receipt(
                receipt_kind=unresolved["receipt_kind"], receipt_body=unresolved["receipt_body"],
                registry=registry, signer_key_id=SIGNER_KEY_ID, signer_private_key_hex=SIGNER_PRIVATE,
            )
        unsigned = copy.deepcopy(vector)
        unsigned["proof"]["signature"] = "0" * 128
        unsigned["receipt_id"] = compute_receipt_id(unsigned)
        store = SQLiteReceiptStore(self.path)
        try:
            with self.assertRaisesRegex(AuthoritativeReceiptError, "RECEIPT_SIGNATURE_INVALID"):
                store.persist_receipt(unsigned, registry=registry, verification_time_ms="1000")
            self.assertEqual(store.read_all_receipts(), ())
        finally:
            store.close()

    def test_23_python_independently_verifies_and_replays_typescript_golden_vector(self):
        vector_path = (
            REPO_ROOT
            / "sovereign-omega-v2"
            / "test"
            / "vectors"
            / "typescript-cross-runtime-receipt-v1.json"
        )
        vector = load_json_strict(vector_path.read_bytes())
        registry_document = vector["registry"]
        context = vector["context"]
        registry = verify_trust_registry(
            registry_document,
            pinned_operator_public_key_hex=vector["operator_public_key"],
            expected_operator_key_id=context["operator_key_id"],
            expected_registry_root=registry_document["registry_root"],
            expected_registry_version=registry_document["registry_body"]["registry_version"],
            verification_time_ms=context["observed_at_ms"],
            max_clock_skew_ms=context["max_clock_skew_ms"],
        )
        previous = ZERO_HASH
        for sequence, receipt in enumerate(vector["receipts"]):
            verified = verify_receipt(
                receipt,
                registry=registry,
                verification_time_ms=context["observed_at_ms"],
                max_clock_skew_ms=context["max_clock_skew_ms"],
            )
            self.assertEqual(verified["receipt_id"], compute_receipt_id(verified))
            self.assertEqual(verified["receipt_body"]["receipt_sequence"], str(sequence))
            self.assertEqual(verified["receipt_body"]["parent_receipt_hash"], previous)
            previous = verified["receipt_id"]
        self.assertEqual(previous, vector["terminal_receipt_id"])

        store = SQLiteReceiptStore(self.path)
        store.persist_registry(registry.document)
        for receipt in vector["receipts"]:
            store.persist_receipt(
                receipt,
                registry=registry,
                verification_time_ms=context["observed_at_ms"],
                max_clock_skew_ms=context["max_clock_skew_ms"],
            )
        store.close()

        recovered = AuthoritativeReceiptAuthority(
            store=SQLiteReceiptStore(self.path),
            current_registry=registry_document,
            pinned_operator_public_key_hex=vector["operator_public_key"],
            expected_operator_key_id=context["operator_key_id"],
            expected_registry_root=registry_document["registry_root"],
            signer_key_id=registry_document["registry_body"]["keys"][0]["key_id"],
            signer_private_key_hex=SIGNER_PRIVATE,
            verification_time_ms=context["observed_at_ms"],
            max_clock_skew_ms=context["max_clock_skew_ms"],
        )
        recovered_bindings = ReceiptBindings(
            actor_identity_root=context["expected_actor_identity_root"],
            session_identity_root=context["expected_session_identity_root"],
            workspace_identity_root=context["expected_workspace_identity_root"],
            holon_identity_root=context["expected_holon_identity_root"],
            authority_domain=context["expected_authority_domain"],
            authority_level=context["expected_authority_level"],
        )
        self.assertEqual(recovered.head_receipt_id, vector["terminal_receipt_id"])
        self.assertEqual(
            recovered.canonical_state_root(recovered_bindings),
            context["expected_observed_state_root"],
        )
        self.assertIsNone(recovered.current_lease(recovered_bindings))
        recovered._store.close()

    def test_24_every_receipt_kind_survives_persisted_restart_readback(self):
        observed_kinds: set[str] = set()
        active_after_restart = {
            "LEASE_ISSUED",
            "LEASE_RENEWED",
            "LEASE_RENEWAL_DENIED",
            "MUTATION_ADMITTED",
            "MUTATION_DENIED",
        }
        for index, target_kind in enumerate(ALL_KINDS):
            with self.subTest(receipt_kind=target_kind):
                path = Path(self.temporary.name) / f"all-kinds-{index}.sqlite3"
                registry = build_registry()
                authority = create_authority(path, registry)
                final_time = "1000"

                if target_kind == "LEASE_ISSUANCE_DENIED":
                    target = issue(
                        authority,
                        lease_id=H("6"),
                        expires="900",
                        nonce=f"nonce-all-kind-{index:02d}",
                    )
                else:
                    lease_receipt = issue(
                        authority,
                        nonce=f"nonce-all-lease-{index:02d}",
                    )
                    target = lease_receipt

                    if target_kind in ("LEASE_RENEWED", "LEASE_RENEWAL_DENIED"):
                        authority.update_observed_time("1200")
                        final_time = "1200"
                        lease = authority.current_lease(bindings())
                        assert lease is not None
                        target = authority.renew_lease(
                            bindings=bindings(),
                            lease_id=lease["lease_id"],
                            lease_generation=lease["lease_generation"],
                            fencing_token=(
                                lease["fencing_token"]
                                if target_kind == "LEASE_RENEWED"
                                else H("9")
                            ),
                            observed_state_root=H("a"),
                            expected_state_root=H("a"),
                            action_digest=H("b"),
                            timestamp_ms="1200",
                            expires_at_ms="4000",
                            nonce=f"nonce-all-renew-{index:02d}",
                        )
                    elif target_kind == "LEASE_EXPIRED":
                        lease = authority.current_lease(bindings())
                        assert lease is not None
                        authority.update_observed_time("3000")
                        final_time = "3000"
                        target = authority.expire_lease(
                            bindings=bindings(),
                            lease_id=lease["lease_id"],
                            lease_generation=lease["lease_generation"],
                            fencing_token=lease["fencing_token"],
                            observed_state_root=H("a"),
                            action_digest=H("b"),
                            timestamp_ms="3000",
                            nonce=f"nonce-all-expire-{index:02d}",
                        )
                    elif target_kind == "LEASE_REVOKED":
                        authority.update_observed_time("1200")
                        final_time = "1200"
                        lease = authority.current_lease(bindings())
                        assert lease is not None
                        target = authority.revoke_lease(
                            bindings=bindings(),
                            lease_id=lease["lease_id"],
                            lease_generation=lease["lease_generation"],
                            fencing_token=lease["fencing_token"],
                            observed_state_root=H("a"),
                            action_digest=H("b"),
                            timestamp_ms="1200",
                            nonce=f"nonce-all-revoke-{index:02d}",
                        )
                    elif target_kind == "MUTATION_ADMITTED":
                        final_time = "1100"
                        target = admit(
                            authority,
                            lease_receipt,
                            nonce=f"nonce-all-admit-{index:02d}",
                        )
                    elif target_kind == "MUTATION_DENIED":
                        final_time = "1100"
                        target = admit(
                            authority,
                            lease_receipt,
                            action=H("6"),
                            expected=H("9"),
                            nonce=f"nonce-all-deny-{index:02d}",
                        )
                    elif target_kind == "MUTATION_COMPLETED":
                        final_time = "1200"
                        admit(
                            authority,
                            lease_receipt,
                            nonce=f"nonce-all-complete-admit-{index:02d}",
                        )
                        target = complete(
                            authority,
                            lease_receipt,
                            nonce=f"nonce-all-complete-{index:02d}",
                        )
                    elif target_kind in ("MUTATION_CANCELLED", "MUTATION_FAILED"):
                        action = H("6" if target_kind == "MUTATION_CANCELLED" else "7")
                        admit(
                            authority,
                            lease_receipt,
                            action=action,
                            nonce=f"nonce-all-terminal-admit-{index:02d}",
                        )
                        authority.update_observed_time("1200")
                        final_time = "1200"
                        lease = authority.current_lease(bindings())
                        assert lease is not None
                        method = (
                            authority.cancel_mutation
                            if target_kind == "MUTATION_CANCELLED"
                            else authority.fail_mutation
                        )
                        target = method(
                            bindings=bindings(),
                            lease_id=lease["lease_id"],
                            lease_generation=lease["lease_generation"],
                            fencing_token=lease["fencing_token"],
                            authority_receipt_hash=H("d"),
                            lease_authorization_receipt_hash=lease_receipt["receipt_id"],
                            observed_state_root=H("a"),
                            expected_state_root=H("a"),
                            action_digest=action,
                            timestamp_ms="1200",
                            nonce=f"nonce-all-terminal-{index:02d}",
                            result_digest=H("8"),
                        )

                self.assertEqual(target["receipt_kind"], target_kind)
                observed_kinds.add(target_kind)
                authority._store.close()

                recovered = create_authority(
                    path,
                    registry,
                    verification_time_ms=final_time,
                )
                self.assertEqual(recovered._store.read_receipt(target["receipt_id"]), target)
                self.assertIn(
                    target["receipt_id"],
                    {item["receipt_id"] for item in recovered._store.read_all_receipts()},
                )
                expected_state = (
                    None
                    if target_kind == "LEASE_ISSUANCE_DENIED"
                    else H("e") if target_kind == "MUTATION_COMPLETED" else H("a")
                )
                self.assertEqual(recovered.canonical_state_root(bindings()), expected_state)
                if target_kind in active_after_restart:
                    self.assertIsNotNone(recovered.current_lease(bindings()))
                else:
                    self.assertIsNone(recovered.current_lease(bindings()))
                recovered._store.close()

        self.assertEqual(observed_kinds, set(ALL_KINDS))

    def test_25_python_and_typescript_generators_match_committed_all_kind_vectors(self):
        vector_root = REPO_ROOT / "sovereign-omega-v2" / "test" / "vectors"
        python_bytes = (
            vector_root / "python-cross-runtime-receipt-v1.json"
        ).read_bytes()
        typescript_bytes = (
            vector_root / "typescript-cross-runtime-receipt-v1.json"
        ).read_bytes()
        regenerated_python_bytes = (
            canon(build_python_cross_runtime_vector()) + b"\n"
        )

        self.assertEqual(python_bytes, regenerated_python_bytes)
        self.assertEqual(typescript_bytes, regenerated_python_bytes)
        vector = load_json_strict(regenerated_python_bytes)
        self.assertEqual(
            {receipt["receipt_kind"] for receipt in vector["receipts"]},
            set(ALL_KINDS),
        )

    def test_26_backdated_timestamp_cannot_revive_expired_lease(self):
        authority = create_authority(self.path)
        issued = issue(authority, expires="1500")
        lease = authority.current_lease(bindings())
        assert lease is not None
        before = authority.canonical_state_root(bindings())

        authority.update_observed_time("1500")
        denied = authority.admit_mutation(
            bindings=bindings(),
            lease_id=lease["lease_id"],
            lease_generation=lease["lease_generation"],
            fencing_token=lease["fencing_token"],
            authority_receipt_hash=H("d"),
            lease_authorization_receipt_hash=issued["receipt_id"],
            observed_state_root=H("a"),
            expected_state_root=H("a"),
            action_digest=H("6"),
            timestamp_ms="1100",
            nonce="nonce-backdated-exp1",
        )

        self.assertEqual(denied["receipt_kind"], "MUTATION_DENIED")
        self.assertIn("LEASE_EXPIRED", denied["receipt_body"]["denial_codes"])
        self.assertEqual(denied["receipt_body"]["before_state_root"], before)
        self.assertEqual(denied["receipt_body"]["after_state_root"], before)
        self.assertEqual(authority.canonical_state_root(bindings()), before)
        authority._store.close()

    def test_27_registry_readback_failure_rolls_back_without_partial_persistence(self):
        class MissingRegistryReadbackStore(SQLiteReceiptStore):
            def _read_pending_registry_bytes(self, registry_root):
                del registry_root
                return None

        registry = build_registry()
        store = MissingRegistryReadbackStore(self.path)
        with self.assertRaisesRegex(AuthoritativeReceiptError, "TRUST_REGISTRY_READBACK_MISMATCH"):
            AuthoritativeReceiptAuthority(
                store=store,
                current_registry=registry,
                pinned_operator_public_key_hex=OPERATOR_PUBLIC,
                expected_operator_key_id=OPERATOR_KEY_ID,
                expected_registry_root=registry["registry_root"],
                signer_key_id=SIGNER_KEY_ID,
                signer_private_key_hex=SIGNER_PRIVATE,
                verification_time_ms="1000",
            )
        self.assertIsNone(store.read_registry(registry["registry_root"]))
        store.close()


if __name__ == "__main__":
    main()
