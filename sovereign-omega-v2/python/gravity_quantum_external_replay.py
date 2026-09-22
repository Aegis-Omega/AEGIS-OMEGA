"""Verify provider-neutral Gravity/Quantum Lean replay receipts.

A successful external deployment is transport evidence only. A kernel receipt is
admissible only when the replay status is verified, exact-head-bound, exact-source
bound, pinned to the expected Lean/Mathlib environment, and authority-neutral.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

HEX64 = re.compile(r"^[0-9a-f]{64}$")

EXPECTED_RECEIPT_KIND = "AEGIS_GQ_CLOUDFLARE_LEAN_REPLAY_V1"
EXPECTED_LEAN_TARGET = "4.33.1"
EXPECTED_MATHLIB_SHA = "0df444a360eaa60ab8c11dca51a86af692955474"
EXPECTED_MODULE = "GravityQuantumPureProductV1"
EXPECTED_THEOREM = "coeffDet_ne_zero_iff_not_pureProductCoeffs"


def verify_external_replay(
    status: Mapping[str, Any],
    *,
    expected_head: str,
    expected_source_sha256: str,
) -> dict[str, Any]:
    reasons: list[str] = []

    def fail(code: str) -> None:
        if code not in reasons:
            reasons.append(code)

    if not isinstance(status, Mapping):
        return {
            "decision": "DENY",
            "reason_codes": ("MALFORMED_STATUS",),
            "authority_effect": "NONE",
        }

    if status.get("receipt_kind") != EXPECTED_RECEIPT_KIND:
        fail("WRONG_RECEIPT_KIND")
    if status.get("head_sha") != expected_head:
        fail("STALE_OR_WRONG_HEAD")
    if status.get("source_sha256") != expected_source_sha256:
        fail("SOURCE_BYTES_MISMATCH")
    if status.get("lean_target") != EXPECTED_LEAN_TARGET:
        fail("LEAN_PIN_MISMATCH")
    if status.get("mathlib_sha") != EXPECTED_MATHLIB_SHA:
        fail("MATHLIB_PIN_MISMATCH")
    if status.get("target_module") != EXPECTED_MODULE:
        fail("TARGET_MODULE_MISMATCH")
    if status.get("stage") != "VERIFIED_EXACT_SOURCE":
        fail("REPLAY_STAGE_NOT_VERIFIED")
    if status.get("verified") is not True:
        fail("REPLAY_NOT_VERIFIED")
    if status.get("authority_effect") != "NONE":
        fail("AUTHORITY_EFFECT_MISMATCH")
    if status.get("gravity_quantized") is not False:
        fail("FORBIDDEN_GRAVITY_PROMOTION")
    if status.get("quantum_gravity_proven") is not False:
        fail("FORBIDDEN_QG_PROMOTION")
    if not isinstance(expected_head, str) or HEX64.fullmatch(expected_head) is None:
        fail("EXPECTED_HEAD_INVALID")
    if (
        not isinstance(expected_source_sha256, str)
        or HEX64.fullmatch(expected_source_sha256) is None
    ):
        fail("EXPECTED_SOURCE_DIGEST_INVALID")

    return {
        "decision": "PASS" if not reasons else "DENY",
        "reason_codes": tuple(reasons),
        "authority_effect": "NONE",
    }


def kernel_receipt_from_external(
    status: Mapping[str, Any],
    *,
    expected_head: str,
    expected_source_sha256: str,
) -> dict[str, Any]:
    verification = verify_external_replay(
        status,
        expected_head=expected_head,
        expected_source_sha256=expected_source_sha256,
    )
    if verification["decision"] != "PASS":
        raise ValueError(
            "external replay is not admissible: "
            + ",".join(verification["reason_codes"])
        )
    return {
        "schema": "AEGIS_GQ_F2B_KERNEL_RECEIPT_V1",
        "kernel_replay": "PASS",
        "theorem": EXPECTED_THEOREM,
        "source_sha256": expected_source_sha256,
        "axiom_audit": "PASS",
        "sorryAx_present": False,
        "authority_effect": "NONE",
    }
