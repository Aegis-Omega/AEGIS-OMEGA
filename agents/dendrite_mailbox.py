"""Opt-in local, append-only informational inboxes for the existing AEGIS dendrite mesh.

Each recipient message is an inert, hash-checked packet. No remote delivery,
agent invocation, sender authentication, policy authority, or paid execution.
"""
from __future__ import annotations

import json
import os
import stat
import tempfile
from pathlib import Path
from typing import Any, Mapping

from agents.dendrite_mesh import DendriteEvent, DIGEST_RE, NAME_RE, MAX_EVENTS, digest
from agents.dendrite_system import system_mesh

SCHEMA = "AEGIS_DENDRITE_LOCAL_MAILBOX_V1"
MAX_FILE = 16384


def _secure_dir(path: Path, *, create: bool) -> Path:
    if path.is_symlink():
        raise ValueError("MAILBOX_SYMLINK_DENIED")
    if create:
        path.mkdir(mode=0o700, exist_ok=True)
    meta = path.lstat()
    if not stat.S_ISDIR(meta.st_mode) or meta.st_uid != os.getuid() or meta.st_mode & 0o077:
        raise ValueError("MAILBOX_DIRECTORY_NOT_PRIVATE")
    return path


def _root(path: str | Path, create: bool) -> Path:
    value = Path(path)
    if not value.is_absolute():
        raise ValueError("MAILBOX_ROOT_MUST_BE_ABSOLUTE")
    return _secure_dir(value, create=create)


def _event(envelope: Mapping[str, Any]) -> DendriteEvent:
    fields = ("origin", "topic", "channel", "source_head",
              "source_record", "sequence", "text", "event_hash")
    if not isinstance(envelope, Mapping) or any(k not in envelope for k in fields):
        raise ValueError("INVALID_DENDRITE_ENVELOPE")
    event = DendriteEvent(**{k: envelope[k] for k in fields})
    event.validate()
    return event


def _validated_events(receipt: Mapping[str, Any]) -> list[tuple[str, dict[str, Any], str]]:
    if not isinstance(receipt, Mapping):
        raise ValueError("INVALID_ROUTING_RECEIPT")
    body = {k: v for k, v in receipt.items() if k != "receipt_hash"}
    if (receipt.get("schema") != "AEGIS_DENDRITE_SYSTEM_V1"
            or receipt.get("authority_effect") != "NONE"
            or receipt.get("execution_effect") != "NONE"
            or receipt.get("source_authenticity") != "NOT_VERIFIED"
            or receipt.get("delivery_kind") != "IN_MEMORY_READ_ONLY"
            or receipt.get("receipt_hash") != digest(body)):
        raise ValueError("UNTRUSTED_ROUTING_RECEIPT")
    events = receipt.get("events")
    if not isinstance(events, list) or not 0 < len(events) <= MAX_EVENTS:
        raise ValueError("INVALID_ROUTING_EVENTS")
    output: list[tuple[str, dict[str, Any], str]] = []
    for routed in events:
        if not isinstance(routed, dict) or not DIGEST_RE.fullmatch(str(routed.get("receipt_hash", ""))):
            raise ValueError("INVALID_ROUTED_EVENT")
        inboxes = routed.get("inboxes")
        if not isinstance(inboxes, dict):
            raise ValueError("INVALID_INBOXES")
        for role, envelope in inboxes.items():
            if not isinstance(role, str) or not NAME_RE.fullmatch(role) or not isinstance(envelope, dict):
                raise ValueError("INVALID_RECIPIENT")
            event = _event(envelope)
            # Recompute routing from the governed role topology, not caller-selected recipients.
            expected = system_mesh().propagate(event, ttl=routed.get("ttl"))
            if expected != routed or expected["inboxes"].get(role) != envelope:
                raise ValueError("ROUTING_TOPOLOGY_MISMATCH")
            output.append((role, envelope, routed["receipt_hash"]))
    return output


def _packet(role: str, envelope: dict[str, Any], route_hash: str) -> dict[str, Any]:
    body = {"schema": SCHEMA, "recipient": role, "envelope": envelope,
            "route_receipt_hash": route_hash, "authority_effect": "NONE",
            "execution_effect": "NONE", "source_authenticity": "NOT_VERIFIED"}
    return {**body, "packet_hash": digest(body)}


def _verify(packet: Any, role: str, filename: str) -> dict[str, Any]:
    allowed = {"schema", "recipient", "envelope", "route_receipt_hash",
               "authority_effect", "execution_effect", "source_authenticity", "packet_hash"}
    if not isinstance(packet, dict) or set(packet) != allowed:
        raise ValueError("MALFORMED_MAILBOX_PACKET")
    body = {k: v for k, v in packet.items() if k != "packet_hash"}
    if (packet["schema"] != SCHEMA or packet["recipient"] != role
            or packet["authority_effect"] != "NONE"
            or packet["execution_effect"] != "NONE"
            or packet["source_authenticity"] != "NOT_VERIFIED"
            or packet["packet_hash"] != digest(body)
            or filename != packet["envelope"].get("event_hash", "") + ".json"):
        raise ValueError("MAILBOX_PACKET_DIGEST_MISMATCH")
    event = _event(packet["envelope"])
    # TTL is intentionally not trusted: enumerate the bounded 0..8 range.
    for ttl in range(9):
        routed = system_mesh().propagate(event, ttl=ttl)
        if (routed["receipt_hash"] == packet["route_receipt_hash"]
                and routed["inboxes"].get(role) == packet["envelope"]):
            return packet
    raise ValueError("MAILBOX_SUBSCRIPTION_OR_ROUTE_MISMATCH")


def _read_file(path: Path, role: str) -> dict[str, Any]:
    if path.is_symlink():
        raise ValueError("MAILBOX_SYMLINK_DENIED")
    meta = path.lstat()
    if (not stat.S_ISREG(meta.st_mode) or meta.st_uid != os.getuid()
            or meta.st_mode & 0o077 or meta.st_size > MAX_FILE):
        raise ValueError("MAILBOX_FILE_UNSAFE")
    fd = os.open(path, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0))
    with os.fdopen(fd, "rb") as f:
        data = f.read(MAX_FILE + 1)
    if len(data) > MAX_FILE:
        raise ValueError("MAILBOX_FILE_TOO_LARGE")
    return _verify(json.loads(data), role, path.name)


def publish_local(receipt: Mapping[str, Any], root: str | Path) -> dict[str, Any]:
    """Atomically place each recipient packet; batches can be partially delivered.

    Replaying the same receipt completes an interrupted batch idempotently.
    This is a local filesystem transport only, NOT an authorized agent dispatch.
    """
    entries = _validated_events(receipt)  # No FS writes if routing fails.
    target = _root(root, create=True)
    created = 0
    duplicates = 0
    for role, envelope, route_hash in entries:
        folder = _secure_dir(target / role, create=True)
        packet = _packet(role, envelope, route_hash)
        data = (json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
                + "\n").encode("utf-8")
        if len(data) > MAX_FILE:
            raise ValueError("MAILBOX_PACKET_TOO_LARGE")
        destination = folder / (envelope["event_hash"] + ".json")
        if destination.exists() or destination.is_symlink():
            if _read_file(destination, role)["packet_hash"] != packet["packet_hash"]:
                raise ValueError("MAILBOX_EXISTING_CONFLICT")
            duplicates += 1
            continue
        handle = tempfile.NamedTemporaryFile(mode="wb", prefix=".dendrite-",
                                             suffix=".tmp", dir=folder, delete=False)
        temporary = Path(handle.name)
        try:
            os.chmod(temporary, 0o600)
            with handle:
                handle.write(data)
                handle.flush()
                os.fsync(handle.fileno())
            try:
                os.link(temporary, destination, follow_symlinks=False)
                created += 1
            except FileExistsError:
                if _read_file(destination, role)["packet_hash"] != packet["packet_hash"]:
                    raise ValueError("MAILBOX_EXISTING_CONFLICT")
                duplicates += 1
        finally:
            temporary.unlink(missing_ok=True)
    return {"schema": "AEGIS_DENDRITE_LOCAL_PUBLISH_V1", "written": created,
            "duplicates": duplicates, "delivery": "FILESYSTEM_ONLY",
            "authority_effect": "NONE", "execution_effect": "NONE",
            "source_authenticity": "NOT_VERIFIED"}


def read_local(root: str | Path, role: str, *, limit: int = 64) -> list[dict[str, Any]]:
    """Read-only local inbox replay by an existing agent-role name."""
    if not isinstance(role, str) or not NAME_RE.fullmatch(role) or role not in system_mesh().nodes:
        raise ValueError("UNKNOWN_MAILBOX_ROLE")
    if type(limit) is not int or not 1 <= limit <= 64:
        raise ValueError("INVALID_READ_LIMIT")
    folder = _secure_dir(_root(root, create=False) / role, create=False)
    paths = sorted(folder.glob("*.json"))
    if len(paths) > limit:
        raise ValueError("MAILBOX_READ_LIMIT_EXCEEDED")
    packets = [_read_file(p, role) for p in paths]
    return sorted(packets, key=lambda p: (p["envelope"]["source_head"],
                                          p["envelope"]["origin"],
                                          p["envelope"]["sequence"],
                                          p["envelope"]["event_hash"]))


def main() -> None:
    """Publish strict external source records or inspect one role's inert inbox."""
    import argparse
    from agents.dendrite_system import from_source_record

    parser = argparse.ArgumentParser(description="AEGIS local dendritic information transport")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("publish")
    p.add_argument("source_json", type=Path)
    p.add_argument("--root", type=Path, required=True)
    p = sub.add_parser("read")
    p.add_argument("role")
    p.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.cmd == "publish":
            with args.source_json.open("rb") as f:
                raw = f.read(8193)
            if len(raw) > 8192:
                raise ValueError("SOURCE_FILE_TOO_LARGE")
            result = publish_local(from_source_record(json.loads(raw)), args.root)
        else:
            result = read_local(args.root, args.role)
    except (ValueError, TypeError, OSError, UnicodeError) as exc:
        parser.error(f"{type(exc).__name__}: {exc}")
    print(json.dumps(result, sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
