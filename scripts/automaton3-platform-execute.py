#!/usr/bin/env python3
"""MCP-facing proof-carrying platform start boundary."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

from harness.sdk.proof_carrying_platform_execution import (  # noqa: E402
    ProofCarryingPlatformExecutionError,
    execute_platform_start_from_environment,
)
from harness.sdk.sovereign_execution import canonical_hash  # noqa: E402

BOUNDARY = "PROOF_CARRYING_PLATFORM_EXECUTION_V1"


def emit(value: dict[str, Any]) -> None:
    print(json.dumps(value, sort_keys=True, separators=(",", ":")))


def denial(
    *,
    codes: list[str],
    external_effect: str,
    detail: str = "",
    authority_outcome: str = "DENIED",
    decision_receipt_root: str | None = None,
) -> dict[str, Any]:
    authority: dict[str, Any] = {"outcome": authority_outcome, "denial_codes": codes}
    if decision_receipt_root is not None:
        authority["decision_receipt_root"] = decision_receipt_root
    return {
        "verification_boundary": BOUNDARY,
        "authority": authority,
        "external_effect": external_effect,
        "complete_verification": {"status": "MISSING"},
        "admission": "UNAVAILABLE",
        "detail_digest": canonical_hash("AEGIS_PLATFORM_EXECUTION_BOUNDARY_ERROR_V1", detail),
    }


def main() -> int:
    try:
        action = json.load(sys.stdin)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        emit(denial(codes=["ACTION_INPUT_MALFORMED"], external_effect="NOT_EXECUTED", detail=str(exc)))
        return 0
    if not isinstance(action, dict):
        emit(denial(codes=["ACTION_INPUT_NOT_OBJECT"], external_effect="NOT_EXECUTED"))
        return 0

    bridge_url = os.environ.get("AEGIS_BRIDGE_URL", "http://localhost:7890")
    api_key = os.environ.get("AEGIS_API_KEY", "")
    if not api_key:
        emit(denial(codes=["PLATFORM_API_KEY_UNAVAILABLE"], external_effect="NOT_EXECUTED"))
        return 0

    try:
        bundle = execute_platform_start_from_environment(
            action=action,
            bridge_url=bridge_url,
            api_key=api_key,
        )
    except ProofCarryingPlatformExecutionError as exc:
        codes = list(exc.denial_codes) or ["PROOF_CARRYING_EXECUTION_FAILED"]
        emit(denial(
            codes=codes,
            external_effect=exc.external_effect,
            detail=str(exc),
            authority_outcome=exc.authority_outcome,
            decision_receipt_root=exc.decision_receipt_root,
        ))
        return 0
    except Exception as exc:
        # Once this boundary is entered, an unclassified failure cannot establish
        # whether a POST crossed the transport boundary. Fail closed as UNKNOWN.
        emit(denial(codes=["PROOF_CARRYING_EXECUTION_ERROR"], external_effect="UNKNOWN", detail=type(exc).__name__))
        return 0

    result = bundle.as_dict()
    result.update({
        "verification_boundary": BOUNDARY,
        "authority": {
            "outcome": "ADMITTED",
            "decision_receipt_root": bundle.decision_receipt.root,
        },
        "external_effect": "VERIFIED",
        "admission": "UNAVAILABLE",
    })
    emit(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
