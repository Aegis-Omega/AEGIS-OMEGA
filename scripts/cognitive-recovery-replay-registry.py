#!/usr/bin/env python3
"""Authority-neutral single-use replay registry for cognitive recovery.

This primitive provides deterministic file-backed compare-and-swap semantics for
one replay-state record. It can reserve and consume a record, but it cannot grant
recovery admission, sign receipts, mutate Git refs, or establish execution trust.

The store path is supplied explicitly by the caller. Repository mutation is not
part of this module.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator, Mapping

SCHEMA_VERSION = "1.0.0"
REPLAY_DOMAIN = "AEGIS_COGNITIVE_RECOVERY_REPLAY_STATE_V1"
RESERVATION_KIND = "AEGIS_COGNITIVE_RECOVERY_REPLAY_RESERVATION_V1"
CONSUMPTION_KIND = "AEGIS_COGNITIVE_RECOVERY_REPLAY_CONSUMPTION_V1"
AUTHORITY = "NONE"
MUTATION_AUTHORITY = "NONE"
EXECUTION_TRUST = "NOT_ESTABLISHED"


class ReplayRegistryError(RuntimeError):
    """Base error carrying a deterministic machine-readable code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


class ReplayConflictError(ReplayRegistryError):
    """The requested state transition conflicts with current state."""


class ReplayIntegrityError(ReplayRegistryError):
    """Stored state or digest evidence is malformed or inconsistent."""


class ReplayBindingError(ReplayRegistryError):
    """A transition receipt is not bound to the exact stored record."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _domain_digest(*, domain: str, key: str, body: Mapping[str, Any]) -> str:
    return _sha256({"domain": domain, key: dict(body)})


def _replay_state_digest(state: Mapping[str, Any]) -> str:
    body = {key: value for key, value in state.items() if key != "replay_state_digest"}
    return _domain_digest(domain=REPLAY_DOMAIN, key="replay_state", body=body)


def build_state(
    *,
    repository_id: str,
    request_digest: str,
    candidate_sha: str,
    operator_approval_digest: str,
    state: str,
    generation: int,
    reservation_digest: str | None,
) -> dict[str, Any]:
    body: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "repository_id": repository_id,
        "request_digest": request_digest,
        "candidate_sha": candidate_sha,
        "operator_approval_digest": operator_approval_digest,
        "state": state,
        "generation": generation,
        "reservation_digest": reservation_digest,
    }
    return {**body, "replay_state_digest": _replay_state_digest(body)}


def _is_hex(value: Any, length: int) -> bool:
    if not isinstance(value, str) or len(value) != length:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return value == value.lower()


def _validate_state(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ReplayIntegrityError("STATE_NOT_OBJECT")

    if value.get("schema_version") != SCHEMA_VERSION:
        raise ReplayIntegrityError("STATE_SCHEMA_VERSION_INVALID")
    if not isinstance(value.get("repository_id"), str) or not value["repository_id"]:
        raise ReplayIntegrityError("STATE_REPOSITORY_ID_INVALID")
    if not _is_hex(value.get("request_digest"), 64):
        raise ReplayIntegrityError("STATE_REQUEST_DIGEST_INVALID")
    if not _is_hex(value.get("candidate_sha"), 40):
        raise ReplayIntegrityError("STATE_CANDIDATE_SHA_INVALID")
    if not _is_hex(value.get("operator_approval_digest"), 64):
        raise ReplayIntegrityError("STATE_APPROVAL_DIGEST_INVALID")
    if value.get("state") not in {"UNUSED", "RESERVED", "CONSUMED", "UNKNOWN"}:
        raise ReplayIntegrityError("STATE_VALUE_INVALID")

    generation = value.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise ReplayIntegrityError("STATE_GENERATION_INVALID")

    reservation_digest = value.get("reservation_digest")
    if reservation_digest is not None and not _is_hex(reservation_digest, 64):
        raise ReplayIntegrityError("STATE_RESERVATION_DIGEST_INVALID")

    supplied_digest = value.get("replay_state_digest")
    if not _is_hex(supplied_digest, 64) or supplied_digest != _replay_state_digest(value):
        raise ReplayIntegrityError("STATE_DIGEST_MISMATCH")

    return value


def _load_state_unlocked(store: Path) -> dict[str, Any]:
    try:
        raw = store.read_text(encoding="utf-8")
        value = json.loads(raw)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayIntegrityError("STATE_UNREADABLE_OR_INVALID") from exc
    return _validate_state(value)


def _fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _write_state_unlocked(store: Path, state: Mapping[str, Any]) -> None:
    store.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_bytes(state) + b"\n"
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{store.name}.", suffix=".tmp", dir=store.parent
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, store)
        _fsync_directory(store.parent)
    finally:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass


@contextmanager
def _exclusive_store_lock(store: Path) -> Iterator[None]:
    store.parent.mkdir(parents=True, exist_ok=True)
    lock_path = store.with_name(store.name + ".lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        with os.fdopen(descriptor, "a+b", closefd=True) as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    except Exception:
        raise


def _receipt_hash(receipt_kind: str, body: Mapping[str, Any]) -> str:
    return _domain_digest(domain=receipt_kind, key="receipt", body=body)


def _reservation_digest(state: Mapping[str, Any]) -> str:
    body = {
        "repository_id": state["repository_id"],
        "request_digest": state["request_digest"],
        "candidate_sha": state["candidate_sha"],
        "operator_approval_digest": state["operator_approval_digest"],
        "previous_state_digest": state["replay_state_digest"],
        "previous_generation": state["generation"],
    }
    return _domain_digest(domain=RESERVATION_KIND, key="reservation", body=body)


def reserve(store: Path, *, expected_state_digest: str) -> dict[str, Any]:
    store = Path(store)
    with _exclusive_store_lock(store):
        current = _load_state_unlocked(store)

        # State is checked before the caller's expected digest so two contenders
        # for the same UNUSED state deterministically classify the loser as a
        # replay conflict rather than as an integrity failure.
        if current["state"] != "UNUSED":
            raise ReplayConflictError("STATE_NOT_UNUSED")
        if not _is_hex(expected_state_digest, 64):
            raise ReplayIntegrityError("EXPECTED_STATE_DIGEST_INVALID")
        if current["replay_state_digest"] != expected_state_digest:
            raise ReplayIntegrityError("EXPECTED_STATE_DIGEST_MISMATCH")
        if current.get("reservation_digest") is not None:
            raise ReplayIntegrityError("UNUSED_STATE_HAS_RESERVATION")

        reservation_digest = _reservation_digest(current)
        next_state = build_state(
            repository_id=current["repository_id"],
            request_digest=current["request_digest"],
            candidate_sha=current["candidate_sha"],
            operator_approval_digest=current["operator_approval_digest"],
            state="RESERVED",
            generation=current["generation"] + 1,
            reservation_digest=reservation_digest,
        )

        body: dict[str, Any] = {
            "receipt_kind": RESERVATION_KIND,
            "schema_version": SCHEMA_VERSION,
            "repository_id": current["repository_id"],
            "request_digest": current["request_digest"],
            "candidate_sha": current["candidate_sha"],
            "operator_approval_digest": current["operator_approval_digest"],
            "transition": "UNUSED_TO_RESERVED",
            "previous_state_digest": current["replay_state_digest"],
            "new_state_digest": next_state["replay_state_digest"],
            "previous_generation": current["generation"],
            "new_generation": next_state["generation"],
            "reservation_digest": reservation_digest,
            "authority": AUTHORITY,
            "mutation_authority": MUTATION_AUTHORITY,
            "execution_trust": EXECUTION_TRUST,
        }
        receipt = {**body, "receipt_hash": _receipt_hash(RESERVATION_KIND, body)}
        _write_state_unlocked(store, next_state)
        return receipt


def _reservation_receipt_matches_state(
    current: Mapping[str, Any], receipt: Mapping[str, Any]
) -> bool:
    expected = {
        "receipt_kind": RESERVATION_KIND,
        "schema_version": SCHEMA_VERSION,
        "repository_id": current["repository_id"],
        "request_digest": current["request_digest"],
        "candidate_sha": current["candidate_sha"],
        "operator_approval_digest": current["operator_approval_digest"],
        "transition": "UNUSED_TO_RESERVED",
        "new_state_digest": current["replay_state_digest"],
        "new_generation": current["generation"],
        "reservation_digest": current["reservation_digest"],
        "authority": AUTHORITY,
        "mutation_authority": MUTATION_AUTHORITY,
        "execution_trust": EXECUTION_TRUST,
    }
    if any(receipt.get(key) != value for key, value in expected.items()):
        return False

    receipt_hash = receipt.get("receipt_hash")
    if not _is_hex(receipt_hash, 64):
        return False
    body = {key: value for key, value in receipt.items() if key != "receipt_hash"}
    return receipt_hash == _receipt_hash(RESERVATION_KIND, body)


def consume(store: Path, *, reservation_receipt: Mapping[str, Any]) -> dict[str, Any]:
    store = Path(store)
    with _exclusive_store_lock(store):
        current = _load_state_unlocked(store)
        if current["state"] != "RESERVED":
            raise ReplayConflictError("STATE_NOT_RESERVED")
        if not isinstance(reservation_receipt, Mapping) or not _reservation_receipt_matches_state(
            current, reservation_receipt
        ):
            raise ReplayBindingError("RESERVATION_RECEIPT_BINDING_MISMATCH")

        next_state = build_state(
            repository_id=current["repository_id"],
            request_digest=current["request_digest"],
            candidate_sha=current["candidate_sha"],
            operator_approval_digest=current["operator_approval_digest"],
            state="CONSUMED",
            generation=current["generation"] + 1,
            reservation_digest=current["reservation_digest"],
        )
        body: dict[str, Any] = {
            "receipt_kind": CONSUMPTION_KIND,
            "schema_version": SCHEMA_VERSION,
            "repository_id": current["repository_id"],
            "request_digest": current["request_digest"],
            "candidate_sha": current["candidate_sha"],
            "operator_approval_digest": current["operator_approval_digest"],
            "transition": "RESERVED_TO_CONSUMED",
            "reservation_digest": current["reservation_digest"],
            "reservation_receipt_hash": reservation_receipt["receipt_hash"],
            "previous_state_digest": current["replay_state_digest"],
            "new_state_digest": next_state["replay_state_digest"],
            "previous_generation": current["generation"],
            "new_generation": next_state["generation"],
            "authority": AUTHORITY,
            "mutation_authority": MUTATION_AUTHORITY,
            "execution_trust": EXECUTION_TRUST,
        }
        receipt = {**body, "receipt_hash": _receipt_hash(CONSUMPTION_KIND, body)}
        _write_state_unlocked(store, next_state)
        return receipt


def _load_json_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ReplayIntegrityError("INPUT_UNREADABLE_OR_INVALID") from exc
    if not isinstance(value, dict):
        raise ReplayIntegrityError("INPUT_NOT_OBJECT")
    return value


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Operate one authority-neutral replay-state store.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    reserve_parser = subparsers.add_parser("reserve")
    reserve_parser.add_argument("--store", required=True)
    reserve_parser.add_argument("--expected-state-digest", required=True)

    consume_parser = subparsers.add_parser("consume")
    consume_parser.add_argument("--store", required=True)
    consume_parser.add_argument("--reservation-receipt", required=True)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if args.command == "reserve":
            receipt = reserve(
                Path(args.store), expected_state_digest=args.expected_state_digest
            )
        else:
            reservation_receipt = _load_json_object(Path(args.reservation_receipt))
            receipt = consume(Path(args.store), reservation_receipt=reservation_receipt)
    except ReplayConflictError as exc:
        sys.stderr.write(f"REPLAY_CONFLICT: {exc.code}\n")
        return 4
    except ReplayBindingError as exc:
        sys.stderr.write(f"REPLAY_BINDING: {exc.code}\n")
        return 5
    except ReplayIntegrityError as exc:
        sys.stderr.write(f"REPLAY_INTEGRITY: {exc.code}\n")
        return 3
    except (OSError, TypeError, ValueError):
        sys.stderr.write("REPLAY_INTEGRITY: INTERNAL_ERROR\n")
        return 3

    sys.stdout.write(canonical_bytes(receipt).decode("utf-8") + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
