"""Fail-closed local Git/Lean source binding for informational dendrite packets.

Checks that an untrusted Formal Conjectures source excerpt matches bytes in a
locally selected exact-HEAD checkout. Does not prove a theorem, authenticate a
GitHub author, authorize a tool or invoke an agent. Stdlib only.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from typing import Any, Mapping

from agents.dendrite_system import from_source_record
from agents.dendrite_attestation import (
    _read_secret, publish_attested, read_attested,
)

SCHEMA = "AEGIS_DENDRITE_FORMAL_SOURCE_GATE_V1"
DEFAULT_PATH = "FormalConjectures/Millennium/RiemannHypothesis.lean"
REMOTE = "tarikskalic33/formal-conjectures"
ALLOWED_PREFIXES = ("FormalConjectures/", "FormalConjecturesForMathlib/", "AegisRH/", "AEGISOverlay/")
MAX_SOURCE_BYTES = 1024 * 1024
FIELDS = frozenset({"source", "source_head", "source_record", "sequence", "text", "channel"})


def _git(repo: Path, *args: str) -> bytes:
    return subprocess.run(["git", "-C", str(repo), *args], check=True,
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                          timeout=15).stdout


def _path(path: str) -> str:
    if not isinstance(path, str) or "\\" in path or "\x00" in path:
        raise ValueError("FORMAL_PATH_INVALID")
    p = PurePosixPath(path)
    if (p.is_absolute() or ".." in p.parts or str(p) != path or not path.endswith(".lean")
            or not path.startswith(ALLOWED_PREFIXES)):
        raise ValueError("FORMAL_PATH_INVALID")
    return path


def _validate_checkout(repo: str | Path, expected_head: str) -> Path:
    if not isinstance(expected_head, str) or not re.fullmatch(r"(?:[0-9a-f]{40}|[0-9a-f]{64})", expected_head):
        raise ValueError("FORMAL_HEAD_INVALID")
    candidate = Path(repo).resolve(strict=True)
    root = Path(_git(candidate, "rev-parse", "--show-toplevel").decode().strip()).resolve()
    if candidate != root:
        raise ValueError("FORMAL_REPOSITORY_ROOT_MISMATCH")
    head = _git(root, "rev-parse", "--verify", "HEAD^{commit}").decode().strip()
    if not hmac.compare_digest(head, expected_head):
        raise ValueError("FORMAL_HEAD_MISMATCH")
    # This verifies only configured local remote metadata, NOT GitHub ownership.
    remote = _git(root, "config", "--local", "--get", "remote.origin.url").decode().strip()
    allowed = {
        "https://github.com/" + REMOTE,
        "https://github.com/" + REMOTE + ".git",
        "git@github.com:" + REMOTE,
        "git@github.com:" + REMOTE + ".git",
        "ssh://git@github.com/" + REMOTE,
        "ssh://git@github.com/" + REMOTE + ".git",
    }
    if remote not in allowed:
        raise ValueError("FORMAL_REMOTE_CONFIG_MISMATCH")
    return root


def verify_formal_source(record: Mapping[str, Any], *, repo: str | Path,
                         path: str = DEFAULT_PATH) -> dict[str, Any]:
    """Check the source against the exact local HEAD, with no checkout writes."""
    if not isinstance(record, Mapping) or set(record) != FIELDS or record.get("source") != "formal":
        raise ValueError("FORMAL_RECORD_SCHEMA_INVALID")
    path = _path(path)
    # Validate the exact dendrite event schema before reading untrusted fields.
    from_source_record(record)
    root = _validate_checkout(repo, record["source_head"])
    stat = _git(root, "ls-tree", "HEAD", "--", path).decode().strip()
    if not stat.startswith("100644 blob ") or not stat.endswith("\t" + path):
        raise ValueError("FORMAL_SOURCE_NOT_REGULAR_BLOB")
    length = int(_git(root, "cat-file", "-s", "HEAD:" + path).decode().strip())
    if not 0 < length <= MAX_SOURCE_BYTES:
        raise ValueError("FORMAL_SOURCE_SIZE_INVALID")
    raw = _git(root, "show", "HEAD:" + path)
    if len(raw) != length:
        raise ValueError("FORMAL_SOURCE_LENGTH_MISMATCH")
    digest = hashlib.sha256(raw).hexdigest()
    if not hmac.compare_digest(digest, record["source_record"]):
        raise ValueError("FORMAL_SOURCE_DIGEST_MISMATCH")
    source = raw.decode("utf-8", "strict")
    prefix = (f"LEAN SOURCE ONLY — PROOF NOT VERIFIED; path={path}; "
              f"source_bytes_sha256={digest}; excerpt:\n")
    text = record["text"]
    if not isinstance(text, str) or not text.startswith(prefix):
        raise ValueError("FORMAL_SOURCE_PREFIX_MISMATCH")
    excerpt = text[len(prefix):]
    if not excerpt or not source.startswith(excerpt):
        raise ValueError("FORMAL_SOURCE_EXCERPT_MISMATCH")
    return {
        "schema": SCHEMA,
        "status": "LOCAL_GIT_HEAD_SOURCE_BYTES_MATCHED",
        "source_head": record["source_head"],
        "source_path": path,
        "source_bytes_sha256": digest,
        "remote_config": "MATCHES_EXPECTED_LOCAL_STRING",
        "github_author_verified": False,
        "mathematical_proof_verified": False,
        "source_authenticity": "LOCAL_CHECKOUT_ONLY",
        "authority_effect": "NONE",
        "execution_effect": "NONE",
    }


def publish_formal_verified(record: Mapping[str, Any], root: str | Path, *,
                            repo: str | Path, path: str = DEFAULT_PATH,
                            key_id: str, key: bytes) -> dict[str, Any]:
    verified = verify_formal_source(record, repo=repo, path=path)
    delivery = publish_attested(from_source_record(record), root, key_id=key_id, key=key)
    return {"source_check": verified, "relay": delivery}


def read_formal_verified(root: str | Path, role: str, trusted_keys: Mapping[str, bytes],
                         *, repo: str | Path, path: str = DEFAULT_PATH) -> list[dict[str, Any]]:
    """Independent reader rechecks BOTH relay HMAC and exact-head source bytes."""
    output = []
    for delivered in read_attested(root, role, trusted_keys):
        envelope = delivered["packet"]["envelope"]
        channel = envelope.get("channel")
        allowed_origin = ("applied_science" if channel == "CANDIDATE"
                          else "cybersecurity" if channel == "QUARANTINE" else None)
        if envelope.get("origin") != allowed_origin or envelope.get("topic") != "formal":
            raise ValueError("FORMAL_ONLY_READER")
        record = {
            "source": "formal", "source_head": envelope["source_head"],
            "source_record": envelope["source_record"], "sequence": envelope["sequence"],
            "text": envelope["text"], "channel": envelope["channel"],
        }
        verified = verify_formal_source(record, repo=repo, path=path)
        output.append({"relay": delivered, "source_check": verified})
    return output


def main() -> None:
    import argparse
    parser = argparse.ArgumentParser(description="AEGIS local Git-bound informational formal source gate")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("verify", "publish", "read"):
        p = sub.add_parser(name)
        p.add_argument("--repo", type=Path, required=True)
        p.add_argument("--path", default=DEFAULT_PATH)
        if name in ("verify", "publish"):
            p.add_argument("record", type=Path)
        if name in ("publish", "read"):
            p.add_argument("--root", type=Path, required=True)
            p.add_argument("--key-file", type=Path, required=True)
            p.add_argument("--key-id", required=True)
        if name == "read":
            p.add_argument("role")
    args = parser.parse_args()
    try:
        if args.command in ("verify", "publish"):
            with args.record.open("rb") as stream:
                raw = stream.read(8193)
            if len(raw) > 8192:
                raise ValueError("FORMAL_RECORD_TOO_LARGE")
            record = json.loads(raw)
        if args.command == "verify":
            result = verify_formal_source(record, repo=args.repo, path=args.path)
        elif args.command == "publish":
            result = publish_formal_verified(record, args.root, repo=args.repo, path=args.path,
                                             key_id=args.key_id, key=_read_secret(args.key_file))
        else:
            result = read_formal_verified(args.root, args.role,
                                           {args.key_id: _read_secret(args.key_file)},
                                           repo=args.repo, path=args.path)
    except (ValueError, TypeError, OSError, UnicodeError, subprocess.SubprocessError) as exc:
        parser.error(f"{type(exc).__name__}:{exc}")
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
