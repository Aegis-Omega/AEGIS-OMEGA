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

from harness.sdk.exact_ldlt import (
    ExactLDLTCertificateV1,
    ExactSymmetricMatrixV1,
    LDLTError,
    verify_exact_ldlt,
)
from harness.sdk.sovereign_execution import canonical_hash
from harness.sdk.weil_convergence_bridge import (
    ExactIntervalV1,
    ExactRationalV1,
    WeilBridgeError,
    WeilContributionV1,
    WeilFiniteCertificateV1,
    WeilInstanceEvidenceV1,
    verify_weil_finite_certificate,
    verify_weil_instance,
)

PACKET_KIND = "AEGIS_WEIL_PROOF_PACKET_V1"
FINITE_CERT_PACKET_KIND = "AEGIS_WEIL_FINITE_CERTIFICATE_PACKET_V1"
LDLT_PACKET_KIND = "AEGIS_EXACT_LDLT_PACKET_V1"
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

_REQUIRED_CERTIFICATE_KEYS = {
    "test_function_digest",
    "cutoff",
    "contributions",
    "norm_sq",
    "epsilon_r",
    "approximation_delta",
    "approximation_bound_root",
}
_OPTIONAL_CERTIFICATE_KEYS = {"assumption_tags"}
_REQUIRED_CONTRIBUTION_KEYS = {
    "contribution_id",
    "contribution_kind",
    "value_interval",
    "source_root",
}
_REQUIRED_LDLT_KEYS = {"matrix", "lower", "diagonal", "matrix_semantics_root"}


def _require_object(name: str, value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise WeilBridgeError(f"{name}:OBJECT_REQUIRED")
    return value


def _rational(name: str, value: Any) -> ExactRationalV1:
    obj = _require_object(name, value)
    if set(obj) != {"numerator", "denominator"}:
        raise WeilBridgeError(f"{name}:EXACT_RATIONAL_FIELDS_INVALID")
    return ExactRationalV1(obj["numerator"], obj["denominator"])


def _interval(name: str, value: Any) -> ExactIntervalV1:
    obj = _require_object(name, value)
    if set(obj) != {"lower", "upper"}:
        raise WeilBridgeError(f"{name}:EXACT_INTERVAL_FIELDS_INVALID")
    return ExactIntervalV1(
        lower=_rational(f"{name}.lower", obj["lower"]),
        upper=_rational(f"{name}.upper", obj["upper"]),
    )


def _assumptions(obj: dict[str, Any]) -> tuple[str, ...]:
    assumptions = obj.get("assumption_tags", [])
    if not isinstance(assumptions, list) or not all(isinstance(item, str) for item in assumptions):
        raise WeilBridgeError("ASSUMPTION_TAGS_INVALID")
    return tuple(assumptions)


def instance_from_dict(payload: Any) -> WeilInstanceEvidenceV1:
    obj = _require_object("instance", payload)
    keys = set(obj)
    missing = _REQUIRED_INSTANCE_KEYS - keys
    unknown = keys - (_REQUIRED_INSTANCE_KEYS | _OPTIONAL_INSTANCE_KEYS)
    if missing:
        raise WeilBridgeError("INSTANCE_REQUIRED_FIELD_MISSING")
    if unknown:
        raise WeilBridgeError("INSTANCE_UNKNOWN_FIELD")

    return WeilInstanceEvidenceV1(
        test_function_digest=obj["test_function_digest"],
        cutoff=obj["cutoff"],
        q_r=_rational("q_r", obj["q_r"]),
        norm_sq=_rational("norm_sq", obj["norm_sq"]),
        epsilon_r=_rational("epsilon_r", obj["epsilon_r"]),
        approximation_delta=_rational("approximation_delta", obj["approximation_delta"]),
        finite_evaluator_root=obj["finite_evaluator_root"],
        approximation_bound_root=obj["approximation_bound_root"],
        assumption_tags=_assumptions(obj),
    )


def _contribution_from_dict(index: int, payload: Any) -> WeilContributionV1:
    obj = _require_object(f"contribution[{index}]", payload)
    if set(obj) != _REQUIRED_CONTRIBUTION_KEYS:
        raise WeilBridgeError("CONTRIBUTION_FIELDS_INVALID")
    return WeilContributionV1(
        contribution_id=obj["contribution_id"],
        contribution_kind=obj["contribution_kind"],
        value_interval=_interval(f"contribution[{index}].value_interval", obj["value_interval"]),
        source_root=obj["source_root"],
    )


def certificate_from_dict(payload: Any) -> WeilFiniteCertificateV1:
    obj = _require_object("certificate", payload)
    keys = set(obj)
    missing = _REQUIRED_CERTIFICATE_KEYS - keys
    unknown = keys - (_REQUIRED_CERTIFICATE_KEYS | _OPTIONAL_CERTIFICATE_KEYS)
    if missing:
        raise WeilBridgeError("CERTIFICATE_REQUIRED_FIELD_MISSING")
    if unknown:
        raise WeilBridgeError("CERTIFICATE_UNKNOWN_FIELD")
    raw_contributions = obj["contributions"]
    if not isinstance(raw_contributions, list):
        raise WeilBridgeError("CONTRIBUTIONS_ARRAY_REQUIRED")
    return WeilFiniteCertificateV1(
        test_function_digest=obj["test_function_digest"],
        cutoff=obj["cutoff"],
        contributions=tuple(
            _contribution_from_dict(index, item)
            for index, item in enumerate(raw_contributions)
        ),
        norm_sq=_rational("norm_sq", obj["norm_sq"]),
        epsilon_r=_rational("epsilon_r", obj["epsilon_r"]),
        approximation_delta=_rational("approximation_delta", obj["approximation_delta"]),
        approximation_bound_root=obj["approximation_bound_root"],
        assumption_tags=_assumptions(obj),
    )


def _rational_rows(name: str, value: Any) -> tuple[tuple[ExactRationalV1, ...], ...]:
    if not isinstance(value, list) or not value:
        raise WeilBridgeError(f"{name}:NONEMPTY_ARRAY_REQUIRED")
    rows: list[tuple[ExactRationalV1, ...]] = []
    for i, raw_row in enumerate(value):
        if not isinstance(raw_row, list):
            raise WeilBridgeError(f"{name}:ROW_ARRAY_REQUIRED")
        rows.append(tuple(_rational(f"{name}[{i}][{j}]", item) for j, item in enumerate(raw_row)))
    return tuple(rows)


def ldlt_from_dict(payload: Any) -> ExactLDLTCertificateV1:
    obj = _require_object("ldlt", payload)
    if set(obj) != _REQUIRED_LDLT_KEYS:
        raise WeilBridgeError("LDLT_FIELDS_INVALID")
    raw_diagonal = obj["diagonal"]
    if not isinstance(raw_diagonal, list):
        raise WeilBridgeError("LDLT_DIAGONAL_ARRAY_REQUIRED")
    return ExactLDLTCertificateV1(
        matrix=ExactSymmetricMatrixV1(rows=_rational_rows("matrix", obj["matrix"])),
        lower=_rational_rows("lower", obj["lower"]),
        diagonal=tuple(_rational(f"diagonal[{i}]", item) for i, item in enumerate(raw_diagonal)),
        matrix_semantics_root=obj["matrix_semantics_root"],
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


def build_certificate_packet(certificate: WeilFiniteCertificateV1) -> dict[str, Any]:
    verification = verify_weil_finite_certificate(certificate)
    payload: dict[str, Any] = {
        "packet_kind": FINITE_CERT_PACKET_KIND,
        "proof_semantics": PACKET_SEMANTICS,
        "certificate": asdict(certificate),
        "certificate_root": certificate.root,
        "verification": verification.to_dict(),
        "global_weil_positivity_proven": False,
        "rh_proven": False,
    }
    payload["packet_root"] = canonical_hash("AEGIS_WEIL_FINITE_CERTIFICATE_PACKET_ROOT_V1", payload)
    return payload


def build_ldlt_packet(certificate: ExactLDLTCertificateV1) -> dict[str, Any]:
    verification = verify_exact_ldlt(certificate)
    payload: dict[str, Any] = {
        "packet_kind": LDLT_PACKET_KIND,
        "proof_semantics": PACKET_SEMANTICS,
        "certificate": asdict(certificate),
        "certificate_root": certificate.root,
        "verification": verification.to_dict(),
        "global_weil_positivity_proven": False,
        "rh_proven": False,
    }
    payload["packet_root"] = canonical_hash("AEGIS_EXACT_LDLT_PACKET_ROOT_V1", payload)
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


def _emit_packet(output: str, packet: dict[str, Any]) -> None:
    if output == "-":
        sys.stdout.write(json.dumps(packet, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    else:
        _write_json_atomic(Path(output), packet)


def verify_instance_command(args: argparse.Namespace) -> int:
    evidence = instance_from_dict(_load_json(Path(args.input)))
    packet = build_packet(evidence)
    _emit_packet(args.output, packet)
    return 0 if packet["verification"]["valid"] else 2


def verify_certificate_command(args: argparse.Namespace) -> int:
    certificate = certificate_from_dict(_load_json(Path(args.input)))
    packet = build_certificate_packet(certificate)
    _emit_packet(args.output, packet)
    return 0 if packet["verification"]["valid"] else 2


def verify_ldlt_command(args: argparse.Namespace) -> int:
    certificate = ldlt_from_dict(_load_json(Path(args.input)))
    packet = build_ldlt_packet(certificate)
    _emit_packet(args.output, packet)
    return 0 if packet["verification"]["valid"] else 2


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="weil-proof", description="AEGIS Weil convergence proof verifier")
    subparsers = parser.add_subparsers(dest="command", required=True)

    verify = subparsers.add_parser("verify-instance", help="verify one exact-rational Weil proof obligation")
    verify.add_argument("--input", required=True, help="input JSON path")
    verify.add_argument("--output", required=True, help="output proof packet path, or '-' for stdout")
    verify.set_defaults(func=verify_instance_command)

    verify_certificate = subparsers.add_parser(
        "verify-certificate",
        help="recompute and verify one decomposed finite Weil interval certificate",
    )
    verify_certificate.add_argument("--input", required=True, help="certificate JSON path")
    verify_certificate.add_argument("--output", required=True, help="output proof packet path, or '-' for stdout")
    verify_certificate.set_defaults(func=verify_certificate_command)

    verify_ldlt = subparsers.add_parser(
        "verify-ldlt",
        help="replay an exact rational LDLT certificate for finite-matrix PSD",
    )
    verify_ldlt.add_argument("--input", required=True, help="LDLT certificate JSON path")
    verify_ldlt.add_argument("--output", required=True, help="output proof packet path, or '-' for stdout")
    verify_ldlt.set_defaults(func=verify_ldlt_command)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return int(args.func(args))
    except (WeilBridgeError, LDLTError) as exc:
        sys.stderr.write(f"WEIL_PROOF_INPUT_REJECTED:{exc.code}\n")
        return 3


if __name__ == "__main__":
    raise SystemExit(main())
