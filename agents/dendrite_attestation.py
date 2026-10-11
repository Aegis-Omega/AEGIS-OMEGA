"""AEGIS dendrite local relay attestation (opt-in, HMAC-SHA256, information only).

Trust boundary: validates which local relay key sealed an existing inert
mailbox packet. Does not authenticate original Git/Lean evidence, confer
agent authority, or dispatch anything. Standard-library only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agents.dendrite_mesh import NAME_RE, DIGEST_RE, canonical
from agents.dendrite_mailbox import (
    _root, _secure_dir, _validated_events, _read_file, publish_local, read_local,
)

SCHEMA = "AEGIS_DENDRITE_RELAY_ATTESTATION_V1"
DOMAIN = b"AEGIS:DENDRITE:RELAY:INFORMATION_ONLY:V1\x00"
MAX_ATTESTATION_BYTES = 2048


def _require_key(key: bytes) -> None:
    if type(key) is not bytes or len(key) < 32:
        raise ValueError("RELAY_KEY_INVALID")


def _require_id(key_id: str) -> None:
    if not isinstance(key_id, str) or not NAME_RE.fullmatch(key_id):
        raise ValueError("RELAY_KEY_ID_INVALID")


def _signed_fields(packet: Mapping[str, Any], key_id: str) -> dict[str, Any]:
    return {
        "schema": SCHEMA,
        "key_id": key_id,
        "recipient": packet["recipient"],
        "packet_hash": packet["packet_hash"],
        "event_hash": packet["envelope"]["event_hash"],
        "route_receipt_hash": packet["route_receipt_hash"],
        "source_head": packet["envelope"]["source_head"],
        "origin": packet["envelope"]["origin"],
        "information_only": True,
        "authority_effect": "NONE",
        "execution_effect": "NONE",
    }


def _mac(body: Mapping[str, Any], key: bytes) -> str:
    return hmac.new(key, DOMAIN + canonical(body), hashlib.sha256).hexdigest()


def _attest(packet: Mapping[str, Any], key_id: str, key: bytes) -> dict[str, Any]:
    data = _signed_fields(packet, key_id)
    return {**data, "hmac_sha256": _mac(data, key)}


def _verify(attestation: Any, packet: Mapping[str, Any],
            keys: Mapping[str, bytes]) -> dict[str, Any]:
    if not isinstance(attestation, dict):
        raise ValueError("RELAY_ATTESTATION_MALFORMED")
    key_id = attestation.get("key_id")
    if not isinstance(key_id, str) or key_id not in keys:
        raise ValueError("RELAY_KEY_NOT_TRUSTED")
    _require_id(key_id)
    key = keys[key_id]
    _require_key(key)
    body = _signed_fields(packet, key_id)
    if set(attestation) != set(body) | {"hmac_sha256"}:
        raise ValueError("RELAY_ATTESTATION_FIELDS_INVALID")
    if any(type(attestation[k]) is not type(v) or attestation[k] != v
           for k, v in body.items()):
        raise ValueError("RELAY_ATTESTATION_BINDING_MISMATCH")
    signature = attestation.get("hmac_sha256")
    if not isinstance(signature, str) or not DIGEST_RE.fullmatch(signature):
        raise ValueError("RELAY_SIGNATURE_MALFORMED")
    if not hmac.compare_digest(signature, _mac(body, key)):
        raise ValueError("RELAY_SIGNATURE_MISMATCH")
    return attestation


def _attestation_path(root: Path, role: str, event_hash: str) -> Path:
    # Sidecars are invisible to the *.json informational inbox reader.
    return root / role / (event_hash + ".attest")


def _load_attestation(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("RELAY_ATTESTATION_SYMLINK")
    try:
        info = path.lstat()
    except FileNotFoundError as e:
        raise ValueError("RELAY_ATTESTATION_MISSING") from e
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or info.st_size > MAX_ATTESTATION_BYTES):
        raise ValueError("RELAY_ATTESTATION_FILE_UNSAFE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as f:
        raw = f.read(MAX_ATTESTATION_BYTES + 1)
    if len(raw) > MAX_ATTESTATION_BYTES:
        raise ValueError("RELAY_ATTESTATION_TOO_LARGE")
    try:
        return json.loads(raw)
    except (UnicodeError, ValueError) as e:
        raise ValueError("RELAY_ATTESTATION_MALFORMED") from e


def publish_attested(receipt: Mapping[str, Any], root: str | Path,
                     *, key_id: str, key: bytes) -> dict[str, Any]:
    """Seal inert relay packets; partial batches are retryable, never authority."""
    _require_id(key_id)
    _require_key(key)
    entries = _validated_events(receipt)
    result = publish_local(receipt, root)
    base = _root(root, create=False)
    signed = 0
    duplicate = 0
    for role, envelope, route_hash in entries:
        folder = _secure_dir(base / role, create=False)
        packet = _read_file(folder / (envelope["event_hash"] + ".json"), role)
        if packet["route_receipt_hash"] != route_hash:
            raise ValueError("RELAY_ROUTE_CONFLICT")
        attestation = _attest(packet, key_id, key)
        dest = _attestation_path(base, role, envelope["event_hash"])
        if dest.exists() or dest.is_symlink():
            if _load_attestation(dest) != attestation:
                raise ValueError("RELAY_ATTESTATION_CONFLICT")
            duplicate += 1
            continue
        encoded = canonical(attestation) + b"\n"
        if len(encoded) > MAX_ATTESTATION_BYTES:
            raise ValueError("RELAY_ATTESTATION_TOO_LARGE")
        handle = tempfile.NamedTemporaryFile(
            "wb", dir=folder, prefix=".dendrite-auth-", suffix=".tmp", delete=False)
        temp = Path(handle.name)
        try:
            os.chmod(temp, 0o600)
            with handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temp, dest, follow_symlinks=False)
                signed += 1
            except FileExistsError:
                if _load_attestation(dest) != attestation:
                    raise ValueError("RELAY_ATTESTATION_CONFLICT")
                duplicate += 1
        finally:
            temp.unlink(missing_ok=True)
    return {
        "schema": "AEGIS_DENDRITE_RELAY_PUBLISH_V1",
        "packet_written": result["written"],
        "attestations_written": signed,
        "attestation_duplicates": duplicate,
        "relay_key_id": key_id,
        "transport_authentication": "HMAC_SHA256_LOCAL_RELAY_ONLY",
        "source_authenticity": "NOT_VERIFIED",
        "authority_effect": "NONE",
        "execution_effect": "NONE",
    }


def read_attested(root: str | Path, role: str, trusted_keys: Mapping[str, bytes],
                  *, limit: int = 64) -> list[dict[str, Any]]:
    """Reject missing/wrong relay MAC; never run the informational payload."""
    if not isinstance(trusted_keys, Mapping) or not trusted_keys:
        raise ValueError("RELAY_TRUST_STORE_REQUIRED")
    base = _root(root, create=False)
    packets = read_local(base, role, limit=limit)
    output = []
    for packet in packets:
        path = _attestation_path(base, role, packet["envelope"]["event_hash"])
        att = _verify(_load_attestation(path), packet, trusted_keys)
        output.append({
            "packet": packet,
            "relay_key_id": att["key_id"],
            "transport_authentication": "HMAC_VERIFIED_LOCAL_RELAY",
            "source_authenticity": "NOT_VERIFIED",
            "authority_effect": "NONE",
            "execution_effect": "NONE",
        })
    return output


def _read_secret(path: Path) -> bytes:
    if not path.is_absolute() or path.is_symlink():
        raise ValueError("RELAY_KEY_PATH_UNSAFE")
    info = path.lstat()
    if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
            or info.st_mode & 0o077 or not 32 <= info.st_size <= 256):
        raise ValueError("RELAY_KEY_FILE_UNSAFE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as f:
        key = f.read(257)
    _require_key(key)
    return key



def publish_for_pipeline(receipt: Mapping[str, Any], root: str | Path,
                         *, key_file: str | Path | None = None,
                         key_id: str | None = None) -> dict[str, Any]:
    """Existing cognitive/revenue opt-in spool with optional relay authentication."""
    if bool(key_file) != bool(key_id):
        raise ValueError("RELAY_KEY_ARGUMENTS_INCOMPLETE")
    if key_file:
        return publish_attested(receipt, root, key_id=key_id,
                                key=_read_secret(Path(key_file)))
    return publish_local(receipt, root)


def main() -> None:
    """Explicit local CLI: neither model calls nor authority decisions."""
    import argparse
    from agents.dendrite_system import from_source_record
    parser = argparse.ArgumentParser(description="AEGIS authenticated local information relay")
    cmds = parser.add_subparsers(dest="cmd", required=True)
    for command in ("publish", "read"):
        cp = cmds.add_parser(command)
        cp.add_argument("--root", type=Path, required=True)
        cp.add_argument("--key-file", type=Path, required=True)
        cp.add_argument("--key-id", required=True)
        if command == "publish":
            cp.add_argument("source_json", type=Path)
        else:
            cp.add_argument("role")
    args = parser.parse_args()
    try:
        secret = _read_secret(args.key_file)
        if args.cmd == "publish":
            with args.source_json.open("rb") as f:
                raw = f.read(8193)
            if len(raw) > 8192:
                raise ValueError("RELAY_SOURCE_TOO_LARGE")
            result = publish_attested(from_source_record(json.loads(raw)), args.root,
                                      key_id=args.key_id, key=secret)
        else:
            result = read_attested(args.root, args.role, {args.key_id: secret})
    except (OSError, ValueError, TypeError, UnicodeError) as exc:
        parser.error(f"{type(exc).__name__}: {exc}")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
