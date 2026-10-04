#!/usr/bin/env python3
"""AEGIS Ω independent offline ExecutionEnvelope verifier v1.

Dependency-free, read-only, and intentionally independent of
sovereign-omega-v2/python/canonical_envelope.py.

It verifies deterministic canonical bytes, envelope hashes, sequence/linkage,
and optional caller-supplied expected roots. It does NOT authenticate a signer,
client principal, transparency log, model execution, or provider execution.

Until the KMS Ed25519 verifier is implemented, a non-null signature is rejected
fail-closed rather than silently treated as trustworthy.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0.0"
RESULT_KIND = "AEGIS_OFFLINE_ENVELOPE_VERIFICATION_V1"
CHAIN_KIND = "AEGIS_EXECUTION_ENVELOPE_CHAIN_V1"
CANON_VERSION = "JCS-1"
GENESIS = "0" * 64
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")

BODY_FIELDS = (
    "canon_version",
    "seq",
    "prev_hash",
    "request_digest",
    "response_digest",
    "model_id",
    "epistemic_tier",
    "provider",
)
ENVELOPE_FIELDS = frozenset((*BODY_FIELDS, "envelope_hash", "signature"))
CHAIN_PACKAGE_FIELDS = frozenset(("schema_version", "kind", "envelopes", "expected_terminal_hash"))


class VerificationError(ValueError):
    pass


def _reject_float(_value: str) -> Any:
    raise VerificationError("FLOAT_IN_HASHED_STATE")


def _reject_constant(_value: str) -> Any:
    raise VerificationError("NON_FINITE_NUMBER")


def load_json(path: str | Path) -> Any:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise VerificationError("INPUT_UNREADABLE") from exc
    try:
        return json.loads(
            raw,
            parse_float=_reject_float,
            parse_constant=_reject_constant,
        )
    except VerificationError:
        raise
    except json.JSONDecodeError as exc:
        raise VerificationError("INVALID_JSON") from exc


def _validate_tree(value: Any) -> None:
    if isinstance(value, float):
        raise VerificationError("FLOAT_IN_HASHED_STATE")
    if value is None or isinstance(value, (str, bool, int)):
        return
    if isinstance(value, list):
        for item in value:
            _validate_tree(item)
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise VerificationError("NON_STRING_OBJECT_KEY")
            _validate_tree(item)
        return
    raise VerificationError("UNSUPPORTED_JSON_TYPE")


def canon(value: Any) -> bytes:
    """Independent float-free canonical JSON path matching Envelope Phase 1."""
    _validate_tree(value)
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def sha256_hex(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _hash(name: str, value: Any) -> str:
    if not isinstance(value, str) or SHA256_RE.fullmatch(value) is None:
        raise VerificationError(f"{name}:INVALID_SHA256")
    return value


def _nonempty_string(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise VerificationError(f"{name}:INVALID_STRING")
    return value


def verify_envelope(
    envelope: Any,
    *,
    expected_seq: int | None = None,
    expected_prev_hash: str | None = None,
    expected_envelope_hash: str | None = None,
) -> dict[str, Any]:
    if not isinstance(envelope, dict):
        raise VerificationError("ENVELOPE_MUST_BE_OBJECT")
    keys = frozenset(envelope)
    if keys != ENVELOPE_FIELDS:
        missing = sorted(ENVELOPE_FIELDS - keys)
        extra = sorted(keys - ENVELOPE_FIELDS)
        raise VerificationError(
            "ENVELOPE_FIELD_SET_MISMATCH"
            + (f":MISSING={','.join(missing)}" if missing else "")
            + (f":EXTRA={','.join(extra)}" if extra else "")
        )

    if envelope["canon_version"] != CANON_VERSION:
        raise VerificationError("CANON_VERSION_UNSUPPORTED")
    seq = envelope["seq"]
    if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0:
        raise VerificationError("SEQUENCE_INVALID")

    prev_hash = _hash("prev_hash", envelope["prev_hash"])
    request_digest = _hash("request_digest", envelope["request_digest"])
    response_digest = _hash("response_digest", envelope["response_digest"])
    claimed_hash = _hash("envelope_hash", envelope["envelope_hash"])
    _nonempty_string("model_id", envelope["model_id"])
    _nonempty_string("epistemic_tier", envelope["epistemic_tier"])
    _nonempty_string("provider", envelope["provider"])

    if envelope["signature"] is not None:
        raise VerificationError("SIGNATURE_VERIFICATION_UNSUPPORTED")

    body = {key: envelope[key] for key in BODY_FIELDS}
    recomputed = sha256_hex(canon(body))
    if recomputed != claimed_hash:
        raise VerificationError("ENVELOPE_HASH_MISMATCH")

    if expected_seq is not None and seq != expected_seq:
        raise VerificationError("EXPECTED_SEQUENCE_MISMATCH")
    if expected_prev_hash is not None:
        _hash("expected_prev_hash", expected_prev_hash)
        if prev_hash != expected_prev_hash:
            raise VerificationError("EXPECTED_PREV_HASH_MISMATCH")
    if expected_envelope_hash is not None:
        _hash("expected_envelope_hash", expected_envelope_hash)
        if claimed_hash != expected_envelope_hash:
            raise VerificationError("EXPECTED_ENVELOPE_HASH_MISMATCH")

    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RESULT_KIND,
        "status": "VALID",
        "verification_scope": "INTEGRITY_AND_LINKAGE_ONLY",
        "seq": seq,
        "prev_hash": prev_hash,
        "request_digest": request_digest,
        "response_digest": response_digest,
        "envelope_hash": claimed_hash,
        "signature_state": "ABSENT_PHASE1",
        "signature_verified": False,
        "client_principal_verified": False,
        "transparency_log_verified": False,
        "provider_execution_verified": False,
        "model_execution_verified": False,
    }


def _extract_chain(value: Any) -> tuple[list[Any], str | None]:
    if isinstance(value, list):
        return value, None
    if not isinstance(value, dict):
        raise VerificationError("CHAIN_INPUT_INVALID")
    if frozenset(value) != CHAIN_PACKAGE_FIELDS:
        raise VerificationError("CHAIN_PACKAGE_FIELD_SET_MISMATCH")
    if value.get("schema_version") != SCHEMA_VERSION:
        raise VerificationError("CHAIN_SCHEMA_UNSUPPORTED")
    if value.get("kind") != CHAIN_KIND:
        raise VerificationError("CHAIN_KIND_UNSUPPORTED")
    envelopes = value.get("envelopes")
    if not isinstance(envelopes, list):
        raise VerificationError("CHAIN_ENVELOPES_INVALID")
    expected = value.get("expected_terminal_hash")
    if expected is not None:
        _hash("expected_terminal_hash", expected)
    return envelopes, expected


def verify_chain(
    value: Any,
    *,
    expected_terminal_hash: str | None = None,
) -> dict[str, Any]:
    envelopes, packaged_terminal = _extract_chain(value)
    if not envelopes:
        raise VerificationError("CHAIN_EMPTY")

    previous = GENESIS
    results: list[dict[str, Any]] = []
    for index, envelope in enumerate(envelopes):
        result = verify_envelope(
            envelope,
            expected_seq=index,
            expected_prev_hash=previous,
        )
        results.append(result)
        previous = result["envelope_hash"]

    terminals = [
        candidate
        for candidate in (packaged_terminal, expected_terminal_hash)
        if candidate is not None
    ]
    for candidate in terminals:
        _hash("expected_terminal_hash", candidate)
        if previous != candidate:
            raise VerificationError("EXPECTED_TERMINAL_HASH_MISMATCH")

    chain_descriptor = {
        "schema_version": SCHEMA_VERSION,
        "kind": CHAIN_KIND,
        "envelope_count": len(results),
        "genesis_hash": GENESIS,
        "terminal_hash": previous,
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RESULT_KIND,
        "status": "VALID",
        "verification_scope": "INTEGRITY_AND_LINKAGE_ONLY",
        "envelope_count": len(results),
        "genesis_hash": GENESIS,
        "terminal_hash": previous,
        "chain_descriptor_hash": sha256_hex(canon(chain_descriptor)),
        "signature_state": "ABSENT_PHASE1",
        "signature_verified": False,
        "client_principal_verified": False,
        "transparency_log_verified": False,
        "provider_execution_verified": False,
        "model_execution_verified": False,
    }


def _human(result: dict[str, Any]) -> str:
    if result.get("status") != "VALID":
        return "INVALID"
    lines = [
        "AEGIS Ω OFFLINE VERIFIER — VALID",
        f"scope: {result['verification_scope']}",
    ]
    if "envelope_count" in result:
        lines.extend(
            [
                f"envelopes: {result['envelope_count']}",
                f"terminal_hash: {result['terminal_hash']}",
                f"chain_descriptor_hash: {result['chain_descriptor_hash']}",
            ]
        )
    else:
        lines.extend(
            [
                f"seq: {result['seq']}",
                f"envelope_hash: {result['envelope_hash']}",
                f"prev_hash: {result['prev_hash']}",
            ]
        )
    lines.extend(
        [
            "signature_verified: false",
            "client_principal_verified: false",
            "transparency_log_verified: false",
            "provider_execution_verified: false",
            "model_execution_verified: false",
        ]
    )
    return "\n".join(lines)


def _invalid(code: str) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "kind": RESULT_KIND,
        "status": "INVALID",
        "error": code,
        "signature_verified": False,
        "client_principal_verified": False,
        "transparency_log_verified": False,
        "provider_execution_verified": False,
        "model_execution_verified": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="json_output")
    sub = parser.add_subparsers(dest="command", required=True)

    one = sub.add_parser("envelope", help="verify one Phase-1 ExecutionEnvelope")
    one.add_argument("path")
    one.add_argument("--expected-seq", type=int)
    one.add_argument("--expected-prev-hash")
    one.add_argument("--expected-envelope-hash")

    chain = sub.add_parser("chain", help="verify a genesis-relative envelope chain")
    chain.add_argument("path")
    chain.add_argument("--expected-terminal-hash")

    args = parser.parse_args(argv)
    try:
        value = load_json(args.path)
        if args.command == "envelope":
            result = verify_envelope(
                value,
                expected_seq=args.expected_seq,
                expected_prev_hash=args.expected_prev_hash,
                expected_envelope_hash=args.expected_envelope_hash,
            )
        else:
            result = verify_chain(
                value,
                expected_terminal_hash=args.expected_terminal_hash,
            )
    except VerificationError as exc:
        result = _invalid(str(exc))
        if args.json_output:
            print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        else:
            print(f"AEGIS Ω OFFLINE VERIFIER — INVALID\nerror: {exc}", file=sys.stderr)
        return 2

    if args.json_output:
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
    else:
        print(_human(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
