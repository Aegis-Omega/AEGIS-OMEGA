#!/usr/bin/env python3
"""AEGIS Ω production CLI for the Weil convergence bridge v1.

The command emits deterministic proof packets for exact-rational local proof
obligations. It does not claim the Riemann Hypothesis is proved.
"""
from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import (
    ExactRationalV1,
    WeilBridgeError,
    WeilInstanceEvidenceV1,
    verify_weil_instance,
)

PACKET_KIND = "AEGIS_WEIL_PROOF_PACKET_V1"
PACKET_SEMANTICS = "EVIDENCE_ONLY_NOT_RH_PROOF"

_REQUIRED_INSTANCE_KEYS = {
    "test_function_digest",
    "cutoff",
    "q_r",
    "norm_sq",
    "epsilon_r",
    "approximation_delta",
    "finite_evaluator_root",
    "approximation_bound_root",
}
_OPTIONAL_INSTANCE_KEYS = {"assumption_tags"}


def _require_object(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WeilBridgeError(f"{name}:OBJECT_REQUIRED")
    return value


def _rational(name: str, value: Any) -> ExactRationalV1:
    obj = _require_object(name, value)
    if set(obj) != {"numerator", "denominator"}:
        raise WeilBridgeError(f"{name}:EXACT_RATIONAL_FIELDS_INVALID")
    return ExactRationalV1(obj["numerator"], obj["denominator"])


def instance_from_dict(payload: Any) -> WeilInstanceEvidenceV1:
    obj = _require_object("instance", payload)
    keys = set(obj)
    missing = _REQUIRED_INSTANCE_KEYS - keys
    unknown = keys - (_REQUIRED_INSTANCE_KEYS | _OPTIONAL_INSTANCE_KEYS)
    if missing:
        raise WeilBridgeError("INSTANCE_REQUIRED_FIELD_MISSING")
    if unknown:
        raise WeilBridgeError("INSTANCE_UNKNOWN_FIELD")

    assumptions = obj.get("assumption_tags", [])
    if not isinstance(assumptions, list) or not all(isinstance(item, str) for item in assumptions):
        raise WeilBridgeError("ASSUMPTION_TAGS_INVALID")

    return WeilInstanceEvidenceV1(
        test_function_digest=obj["test_function_digest"],
        cutoff=obj["cutoff"],
        q_r=_rational("q_r", obj["q_r"]),
        norm_sq=_rational("norm_sq", obj["norm_sq"]),
        epsilon_r=_rational("epsilon_r", obj["epsilon_r"]),
        approximation_delta=_rational("approximation_delta", obj["approximation_delta"]),
        finite_evaluator_root=obj["finite_evaluator_root"],
        approximation_bound_root=obj["approximation_bound_root"],
        assumption_tags=tuple(assumptions),
    )


def build_packet(evidence: WeilInstanceEvidenceV1) -> dict[str, Any]:
    verification = verify_weil_instance(evidence)
    payload: dict[str, Any] = {
        "packet_kind": PACKET_KIND,
        "proof_semantics": PACKET_SEMANTICS,
        "evidence": asdict(evidence),
        "evidence_root": evidence.root,
        "verification": verification.to_dict(),
        "global_weil_positivity_proven": False,
        "rh_proven": False,
    }
    payload["packet_root"] = canonical_hash("AEGIS_WEIL_PROOF_PACKET_ROOT_V1", payload)
    return payload


def _load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise WeilBridgeError("INPUT_JSON_INVALID") from exc


def _write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n"
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=str(path.parent), text=True)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(encoded)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


def verify_instance_command(args: argparse.Namespace) -> int:
    evidence = instance_from_dict(_load_json(Path(args.input)))
    packet = build_packet(evidence)
    if args.output == "-":
        sys.stdout.write(json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    else:
        _write_json_atomic(Path(args.output), packet)
    return 0 if packet["verification"]["valid"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weil-proof", description="AEGIS Weil convergence proof verifier")
    subparsers = parser.add_subparsers(dest="command", required=True)
    verify = subparsers.add_parser("verify-instance", help="verify one exact-rational Weil proof obligation")
    verify.add_argument("--input", required=True, help="input JSON path")
    verify.add_argument("--output", required=True, help="output proof packet path, or '-' for stdout")
    verify.set_defaults(func=verify_instance_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except WeilBridgeError as exc:
        sys.stderr.write(f"WEIL_PROOF_INPUT_REJECTED:{exc.code}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
