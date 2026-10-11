#!/usr/bin/env python3
"""AEGIS UWP read-only research evidence gate.

Checks structural provenance, snapshot integrity, freshness and diversity before
marking proposals READY_FOR_TEST. It cannot authenticate publishers, verify external
claims, or prove an improvement. No HTTP, shell, AI invocation or authority grant.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import ipaddress
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

from research_attestation import verify_capture

SCHEMA = "aegis.research.packet.v1"
SHA = re.compile(r"^[a-f0-9]{64}$")
GIT_OID = re.compile(r"^(?:[a-f0-9]{40}|[a-f0-9]{64})$")
ID = re.compile(r"^[A-Za-z][A-Za-z0-9_.-]{0,63}$")
UTC = re.compile(r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
MAX_BYTES = 300_000
MAX_AGE_DAYS = 30

class ResearchError(ValueError):
    pass


def fail(code: str) -> None:
    raise ResearchError(code)


def parse_json(raw: str):
    def pairs_unique(pairs):
        out = {}
        for key, value in pairs:
            if key in out:
                fail("DUPLICATE_JSON_KEY")
            out[key] = value
        return out

    def no_float(_):
        fail("NON_INTEGER_NUMBER")

    def no_constant(_):
        fail("NON_JSON_CONSTANT")

    if len(raw.encode("utf-8")) > MAX_BYTES:
        fail("INPUT_TOO_LARGE")
    try:
        return json.loads(raw, object_pairs_hook=pairs_unique,
                          parse_float=no_float, parse_constant=no_constant)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ResearchError("INVALID_JSON") from exc


def obj(value, fields: set[str], required: set[str]):
    if type(value) is not dict or set(value) - fields or required - set(value):
        fail("INVALID_OBJECT_FIELDS")
    return value


def nonempty(value, label: str, length: int = 2000) -> str:
    if type(value) is not str or not value.strip() or value != value.strip() or len(value) > length:
        fail(label)
    return value


def ident(value, label="INVALID_ID") -> str:
    v = nonempty(value, label, 64)
    if not ID.fullmatch(v):
        fail(label)
    return v


def timestamp(value) -> dt.datetime:
    if type(value) is not str or not UTC.fullmatch(value):
        fail("INVALID_UTC_TIMESTAMP")
    try:
        return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=dt.timezone.utc)
    except ValueError as exc:
        raise ResearchError("INVALID_UTC_TIMESTAMP") from exc


def publisher(url: str) -> str:
    """Conservative issuer bucket for diversity; not publisher authentication."""
    nonempty(url, "INVALID_URL", 2048)
    try:
        parsed = urlsplit(url)
        host = (parsed.hostname or "").lower()
        if parsed.scheme != "https" or not host or parsed.username or parsed.password or parsed.port is not None:
            fail("INVALID_URL")
        if parsed.query or parsed.fragment or not re.fullmatch(r"[a-z0-9.-]+", host):
            fail("INVALID_URL")
        if host == "localhost" or host.endswith((".local", ".internal", ".localhost")):
            fail("INVALID_URL")
        try:
            ipaddress.ip_address(host)
            fail("INVALID_URL")
        except ValueError as exc:
            if str(exc) == "INVALID_URL":
                raise
        if "." not in host or host.startswith(".") or ".." in host:
            fail("INVALID_URL")
    except ValueError as exc:
        if isinstance(exc, ResearchError):
            raise
        raise ResearchError("INVALID_URL") from exc
    if host == "openai.github.io" or host.endswith(".openai.com") or host == "openai.com":
        return "openai"
    if host.endswith(".anthropic.com") or host == "anthropic.com" or host.endswith(".claude.com") or host == "claude.com":
        return "anthropic"
    if host.endswith(".langchain.com") or host == "langchain.com" or host == "langchain-ai.github.io":
        return "langchain"
    if host == "github.com" or host == "raw.githubusercontent.com":
        return "github-unknown-issuer"
    return "unattributed:" + host


def canonical(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True,
                      separators=(",", ":"), allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def evaluate(packet: dict, *, trusted_keys: dict[str, bytes] | None = None,
             verified_now: dt.datetime | None = None) -> dict:
    o = obj(packet, {"schema", "task_id", "as_of_utc", "repo_head", "sources", "proposals"},
            {"schema", "task_id", "as_of_utc", "repo_head", "sources", "proposals"})
    if o["schema"] != SCHEMA:
        fail("SCHEMA_MISMATCH")
    task_id = ident(o["task_id"])
    declared_now = timestamp(o["as_of_utc"])
    # A signed captured_at is not sufficient: a caller could backdate as_of.
    if trusted_keys is not None:
        now = verified_now if verified_now is not None else dt.datetime.now(dt.timezone.utc)
        if not isinstance(now, dt.datetime) or now.tzinfo is None:
            fail("TRUSTED_CLOCK_REQUIRED")
        now = now.astimezone(dt.timezone.utc)
        if abs((now - declared_now).total_seconds()) > 300:
            fail("UNTRUSTED_AS_OF_CLOCK")
    else:
        now = declared_now
    if not isinstance(o["repo_head"], str) or not GIT_OID.fullmatch(o["repo_head"]):
        fail("INVALID_REPO_HEAD")
    if type(o["sources"]) is not list or len(o["sources"]) > 100:
        fail("INVALID_SOURCES")
    if type(o["proposals"]) is not list or not (1 <= len(o["proposals"]) <= 100):
        fail("INVALID_PROPOSALS")
    sources = {}
    for raw in o["sources"]:
        s = obj(raw, {"id", "url", "captured_at", "content", "sha256", "acquisition", "capture_receipt"},
                {"id", "url", "captured_at", "content", "sha256", "acquisition"})
        sid = ident(s["id"])
        if sid in sources:
            fail("DUPLICATE_SOURCE_ID")
        group = publisher(s["url"])
        if s["acquisition"] not in ("manual_note", "connector_capture"):
            fail("INVALID_ACQUISITION")
        content = nonempty(s["content"], "EMPTY_SOURCE", 20000)
        checksum = s["sha256"]
        if type(checksum) is not str or not SHA.fullmatch(checksum) or digest(content.encode("utf-8")) != checksum:
            fail("SOURCE_DIGEST_MISMATCH")
        age = (now - timestamp(s["captured_at"])).total_seconds()
        if age < 0:
            fail("FUTURE_SOURCE")
        receipt = s.get("capture_receipt")
        valid_attestation = (
            s["acquisition"] == "connector_capture" and
            verify_capture(receipt, trusted_keys, expected_binding={
                'task_id': task_id, 'repo_head': o['repo_head'], 'source_id': sid
            }) and
            receipt["url"] == s["url"] and
            receipt["captured_at"] == s["captured_at"] and
            receipt["excerpt"] == content and
            receipt["excerpt_sha256"] == checksum and
            receipt["hostname"] == urlsplit(s["url"]).hostname and
            receipt["authority_effect"] == "NONE" and
            receipt["claim_truth"] == "NOT_VERIFIED"
        )
        sources[sid] = {"publisher_group": group, "digest": checksum,
                        "attested": bool(valid_attestation),
                        "fresh": age <= MAX_AGE_DAYS * 86400,
                        "url": s["url"], "acquisition": s["acquisition"]}
    output = []
    seen = set()
    for raw in o["proposals"]:
        p = obj(raw,
                {"id", "local_component", "candidate", "mechanism", "test_metric", "falsifier", "source_ids"},
                {"id", "local_component", "candidate", "mechanism", "test_metric", "falsifier", "source_ids"})
        pid = ident(p["id"])
        if pid in seen:
            fail("DUPLICATE_PROPOSAL_ID")
        seen.add(pid)
        component = nonempty(p["local_component"], "INVALID_COMPONENT", 300)
        if component.startswith("/") or ".." in component.split("/") or "*" in component:
            fail("INVALID_COMPONENT")
        for k in ("candidate", "mechanism", "test_metric", "falsifier"):
            nonempty(p[k], "INVALID_PROPOSAL", 2000)
        ids = p["source_ids"]
        if type(ids) is not list or not ids or len(ids) > 30:
            fail("INVALID_SOURCE_REFS")
        ids = [ident(x) for x in ids]
        if len(set(ids)) != len(ids):
            fail("DUPLICATE_SOURCE_REF")
        if any(i not in sources for i in ids):
            fail("UNKNOWN_SOURCE_REF")
        fresh = [i for i in ids if sources[i]["fresh"]]
        groups = sorted({sources[i]["publisher_group"] for i in fresh})
        # A manually entered note is not evidence of a performed source capture.
        # Bound local key MAC verifies snapshot+task+repo+source identity,
        # but cannot prove an honest collector or truthful website content.
        collected = [i for i in fresh if sources[i]["attested"]]
        eligible = {sources[i]["publisher_group"] for i in collected
                    if not sources[i]["publisher_group"].startswith("unattributed:")
                    and sources[i]["publisher_group"] != "github-unknown-issuer"}
        # Byte-identical mirrors cannot form a second independent observation.
        distinct_digest_count = len({sources[i]["digest"] for i in collected
                                     if sources[i]["publisher_group"] in eligible})
        ready = len(eligible) >= 2 and distinct_digest_count >= 2
        if ready:
            status = "READY_FOR_INDEPENDENT_TEST"
            reason = "TWO_PUBLISHER_GROUPS_NOT_AUTHENTICATED"
        elif any(not sources[i]["fresh"] for i in ids):
            status = "NEEDS_RESEARCH"
            reason = "STALE_OR_INSUFFICIENT_DIVERSITY"
        elif len(collected) < 2:
            status = "NEEDS_RESEARCH"
            reason = "INSUFFICIENT_CAPTURE_EVIDENCE"
        else:
            status = "NEEDS_RESEARCH"
            reason = "INSUFFICIENT_PUBLISHER_DIVERSITY"
        output.append({"id": pid, "status": status, "reason": reason,
                       "fresh_source_count": len(fresh),
                       "collected_source_count": len(collected),
                       "publisher_groups": groups,
                       "source_sha256": {i: sources[i]["digest"] for i in sorted(ids)},
                       "test_metric": p["test_metric"], "falsifier": p["falsifier"],
                       "local_component": component})
    return {"schema": "aegis.research.receipt.v1", "task_id": task_id,
            "as_of_utc": o["as_of_utc"], "repo_head": o["repo_head"],
            "packet_sha256": digest(canonical(o)),
            "source_digest_integrity": "CHECKED_NOT_AUTHENTICATED",
            "freshness_basis": ("LOCAL_TRUSTED_CLOCK" if trusted_keys is not None
                                else "CALLER_REPORTED_AS_OF_UNAUTHENTICATED"),
            "collector_attestation": ("LOCAL_HMAC_VERIFIED_FOR_QUORUM" if trusted_keys is not None
                                      else "NOT_VERIFIED"),
            "external_claim_verification": "NOT_PERFORMED",
            "benchmark_superiority": "NOT_ESTABLISHED",
            "tool_execution": "NOT_EXECUTED", "authority_effect": "NONE",
            "proposals": sorted(output, key=lambda p: p["id"])}


def main(argv=None) -> int:
    cli = argparse.ArgumentParser(description="Offline, read-only AEGIS evidence scout")
    cli.add_argument("packet", help="JSON research packet. No URLs are fetched")
    cli.add_argument("--output", help="write JSON receipt to local path")
    cli.add_argument("--trust-key-file", help="owner-only 32-byte external verifier key file")
    cli.add_argument("--trust-key-id", help="trusted runner key ID configured out of band")
    args = cli.parse_args(argv)
    try:
        if bool(args.trust_key_file) != bool(args.trust_key_id):
            fail("TRUST_KEY_AND_ID_REQUIRED")
        keys = None
        if args.trust_key_file:
            from research_attestation import read_protected_key
            keys = {ident(args.trust_key_id).lower(): read_protected_key(args.trust_key_file)}
        result = evaluate(parse_json(Path(args.packet).read_text(encoding="utf-8")),
                          trusted_keys=keys)
    except (ResearchError, OSError, ValueError) as exc:
        print(json.dumps({"status": "REJECTED", "reason": str(exc), "authority_effect": "NONE"}), file=sys.stderr)
        return 2
    encoded = json.dumps(result, indent=2, sort_keys=True) + "\n"
    if args.output:
        Path(args.output).write_text(encoded, encoding="utf-8")
    else:
        sys.stdout.write(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
