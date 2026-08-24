#!/usr/bin/env python3
"""Collect and certify AEGIS-Ω Jetson target-hardware execution evidence.

This utility does not claim that a run happened. It validates measurements and
artifacts supplied by the target harness, hashes every bound artifact, applies the
same fail-closed admission conjunction as `aegis_runtime::jetson_execution`, and
emits a deterministic receipt.

Input is JSON. All artifact paths are replaced by SHA-256 digests in the output.
The receipt is canonical JSON (`sort_keys=True`, compact separators, UTF-8).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path
from typing import Any

RAGC_BUDGET_US = 15_000
END_TO_END_BUDGET_US = 50_000
ORIN_SM = 87
VALID_SKU_POWER = {
    "ORIN_NANO_SUPER_8GB": {25},
    "ORIN_NX_8GB": {40},
    "ORIN_NX_16GB": {25, 40},
}
VALID_PRECISIONS = {"FP16", "INT8_QAT", "INT4_WEIGHT_ONLY"}


class EvidenceError(ValueError):
    """Fail-closed evidence validation error."""


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def require_bool(obj: dict[str, Any], key: str) -> bool:
    value = obj.get(key)
    if type(value) is not bool:  # bool is intentionally exact here.
        raise EvidenceError(f"{key} must be a boolean")
    return value


def require_nonnegative_int(obj: dict[str, Any], key: str) -> int:
    value = obj.get(key)
    if type(value) is not int or value < 0:
        raise EvidenceError(f"{key} must be a non-negative integer")
    return value


def require_string(obj: dict[str, Any], key: str) -> str:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        raise EvidenceError(f"{key} must be a non-empty string")
    return value


def bind_file(path_value: str, field: str) -> dict[str, Any]:
    path = Path(path_value).expanduser().resolve()
    if not path.is_file():
        raise EvidenceError(f"{field} does not resolve to a file: {path}")
    return {
        "name": path.name,
        "bytes": path.stat().st_size,
        "sha256": sha256_file(path),
    }


def validate_input(raw: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []

    sku = require_string(raw, "sku")
    if sku not in VALID_SKU_POWER:
        raise EvidenceError(f"unsupported sku: {sku}")
    power_watts = require_nonnegative_int(raw, "power_watts")
    if power_watts not in VALID_SKU_POWER[sku]:
        failures.append("NVP_MODEL_PROFILE_INVALID")

    target_sm = require_nonnegative_int(raw, "target_sm")
    if target_sm != ORIN_SM:
        failures.append("COMPUTE_CAPABILITY_MISMATCH")

    nvpmodel = raw.get("nvpmodel")
    if not isinstance(nvpmodel, dict):
        raise EvidenceError("nvpmodel must be an object")
    mode_name = require_string(nvpmodel, "mode_name")
    raw_output = require_string(nvpmodel, "raw_output")
    nvpmodel_bound = {
        "mode_name": mode_name,
        "mode_id": nvpmodel.get("mode_id"),
        "raw_output_sha256": sha256_bytes(raw_output.encode("utf-8")),
    }

    rt = raw.get("real_time")
    if not isinstance(rt, dict):
        raise EvidenceError("real_time must be an object")
    rt_bound = {
        "preempt_rt": require_bool(rt, "preempt_rt"),
        "duration_seconds": require_nonnegative_int(rt, "duration_seconds"),
        "page_faults": require_nonnegative_int(rt, "page_faults"),
        "scheduler_migrations": require_nonnegative_int(rt, "scheduler_migrations"),
        "irq_latency_p99_9_us": require_nonnegative_int(rt, "irq_latency_p99_9_us"),
        "irq_latency_max_us": require_nonnegative_int(rt, "irq_latency_max_us"),
        "p99_9_limit_us": require_nonnegative_int(rt, "p99_9_limit_us"),
        "max_limit_us": require_nonnegative_int(rt, "max_limit_us"),
    }
    if not rt_bound["preempt_rt"]:
        failures.append("PREEMPT_RT_NOT_ACTIVE")
    if rt_bound["duration_seconds"] < 86_400:
        failures.append("CYCLICTEST_DURATION_LT_24H")
    if rt_bound["page_faults"] != 0:
        failures.append("PAGE_FAULTS_IN_CRITICAL_LOOP")
    if rt_bound["scheduler_migrations"] != 0:
        failures.append("SCHEDULER_MIGRATIONS_IN_CRITICAL_LOOP")
    if rt_bound["irq_latency_p99_9_us"] > rt_bound["p99_9_limit_us"]:
        failures.append("IRQ_P99_9_BUDGET_EXCEEDED")
    if rt_bound["irq_latency_max_us"] > rt_bound["max_limit_us"]:
        failures.append("IRQ_MAX_BUDGET_EXCEEDED")

    zero_copy = raw.get("zero_copy")
    if not isinstance(zero_copy, dict):
        raise EvidenceError("zero_copy must be an object")
    backend = require_string(zero_copy, "backend")
    if backend not in {"CUDA_IPC", "NVMM_DMA_BUF"}:
        raise EvidenceError(f"unsupported zero-copy backend: {backend}")
    zero_copy_bound = {
        "backend": backend,
        "verified": require_bool(zero_copy, "verified"),
        "host_memcpy_in_critical_path": require_nonnegative_int(
            zero_copy, "host_memcpy_in_critical_path"
        ),
        "buffer_reallocations_after_warmup": require_nonnegative_int(
            zero_copy, "buffer_reallocations_after_warmup"
        ),
        "dma_sync_errors": require_nonnegative_int(zero_copy, "dma_sync_errors"),
        "lifecycle_violations": require_nonnegative_int(
            zero_copy, "lifecycle_violations"
        ),
    }
    if not zero_copy_bound["verified"]:
        failures.append("ZERO_COPY_NOT_VERIFIED")
    for key, code in {
        "host_memcpy_in_critical_path": "HOST_MEMCPY_IN_CRITICAL_PATH",
        "buffer_reallocations_after_warmup": "POST_WARMUP_REALLOCATION",
        "dma_sync_errors": "DMA_SYNC_ERROR",
        "lifecycle_violations": "BUFFER_LIFECYCLE_VIOLATION",
    }.items():
        if zero_copy_bound[key] != 0:
            failures.append(code)

    trt = raw.get("tensorrt")
    if not isinstance(trt, dict):
        raise EvidenceError("tensorrt must be an object")
    precision = require_string(trt, "precision")
    target_local_build = require_bool(trt, "target_local_build")
    explicit_qdq = require_bool(trt, "explicit_qdq")
    unsupported_fallbacks = require_nonnegative_int(
        trt, "unsupported_precision_fallbacks"
    )
    accuracy_delta_ppm = trt.get("accuracy_delta_ppm")
    if type(accuracy_delta_ppm) is not int:
        raise EvidenceError("accuracy_delta_ppm must be an integer")
    max_accuracy_loss_ppm = require_nonnegative_int(trt, "max_accuracy_loss_ppm")
    latency_p99_us = require_nonnegative_int(trt, "latency_p99_us")

    if precision not in VALID_PRECISIONS:
        failures.append("PRECISION_UNSUPPORTED_ON_ORIN")
    if precision in {"INT8_QAT", "INT4_WEIGHT_ONLY"} and not explicit_qdq:
        failures.append("EXPLICIT_QDQ_REQUIRED")
    if not target_local_build:
        failures.append("ENGINE_NOT_BUILT_ON_TARGET")
    if unsupported_fallbacks != 0:
        failures.append("UNSUPPORTED_PRECISION_FALLBACK")
    if accuracy_delta_ppm < -max_accuracy_loss_ppm:
        failures.append("ACCURACY_REGRESSION_EXCEEDED")
    if latency_p99_us > END_TO_END_BUDGET_US:
        failures.append("ENGINE_LATENCY_BUDGET_EXCEEDED")

    artifacts = trt.get("artifacts")
    if not isinstance(artifacts, dict):
        raise EvidenceError("tensorrt.artifacts must be an object")
    required_artifacts = ("model", "onnx", "plugin", "engine", "calibration")
    artifact_bindings = {
        name: bind_file(require_string(artifacts, name), f"tensorrt.artifacts.{name}")
        for name in required_artifacts
    }
    trt_bound = {
        "precision": precision,
        "target_local_build": target_local_build,
        "explicit_qdq": explicit_qdq,
        "unsupported_precision_fallbacks": unsupported_fallbacks,
        "accuracy_delta_ppm": accuracy_delta_ppm,
        "max_accuracy_loss_ppm": max_accuracy_loss_ppm,
        "latency_p99_us": latency_p99_us,
        "artifacts": artifact_bindings,
    }

    latency = raw.get("latency")
    if not isinstance(latency, dict):
        raise EvidenceError("latency must be an object")
    latency_bound = {
        "ragc_window_p99_us": require_nonnegative_int(latency, "ragc_window_p99_us"),
        "end_to_end_p99_us": require_nonnegative_int(latency, "end_to_end_p99_us"),
        "deadline_misses": require_nonnegative_int(latency, "deadline_misses"),
    }
    if latency_bound["ragc_window_p99_us"] > RAGC_BUDGET_US:
        failures.append("RAGC_WINDOW_BUDGET_EXCEEDED")
    if latency_bound["end_to_end_p99_us"] > END_TO_END_BUDGET_US:
        failures.append("END_TO_END_BUDGET_EXCEEDED")
    if latency_bound["deadline_misses"] != 0:
        failures.append("DEADLINE_MISS")

    thermal = raw.get("thermal")
    if not isinstance(thermal, dict):
        raise EvidenceError("thermal must be an object")
    thermal_bound = {
        "max_temperature_millicelsius": require_nonnegative_int(
            thermal, "max_temperature_millicelsius"
        ),
        "temperature_limit_millicelsius": require_nonnegative_int(
            thermal, "temperature_limit_millicelsius"
        ),
        "throttle_events": require_nonnegative_int(thermal, "throttle_events"),
    }
    if (
        thermal_bound["max_temperature_millicelsius"]
        > thermal_bound["temperature_limit_millicelsius"]
    ):
        failures.append("THERMAL_LIMIT_EXCEEDED")
    if thermal_bound["throttle_events"] != 0:
        failures.append("THERMAL_THROTTLE_EVENT")

    sgm = raw.get("sgm")
    if not isinstance(sgm, dict):
        raise EvidenceError("sgm must be an object")
    receipt_file = bind_file(require_string(sgm, "certificate_path"), "sgm.certificate_path")
    sgm_bound = {
        "certificate": receipt_file,
        "certificate_valid": require_bool(sgm, "certificate_valid"),
        "accepted": require_bool(sgm, "accepted"),
        "hellinger_squared_ppb": require_nonnegative_int(
            sgm, "hellinger_squared_ppb"
        ),
        "max_hellinger_squared_ppb": require_nonnegative_int(
            sgm, "max_hellinger_squared_ppb"
        ),
        "policy_revision": require_string(sgm, "policy_revision"),
    }
    if not sgm_bound["certificate_valid"]:
        failures.append("SGM_CERTIFICATE_INVALID")
    if not sgm_bound["accepted"]:
        failures.append("SGM_REJECTED")
    if sgm_bound["hellinger_squared_ppb"] > sgm_bound["max_hellinger_squared_ppb"]:
        failures.append("HELLINGER_BOUND_EXCEEDED")

    replay_verified = require_bool(raw, "replay_verified")
    scope_match = require_bool(raw, "scope_match")
    agent_plane_blocks_hard_path = require_bool(raw, "agent_plane_blocks_hard_path")
    if not replay_verified:
        failures.append("REPLAY_NOT_VERIFIED")
    if not scope_match:
        failures.append("SCOPE_MISMATCH")
    if agent_plane_blocks_hard_path:
        failures.append("AGENT_PLANE_BLOCKS_HARD_PATH")

    bound = {
        "contract": "AEGIS_JETSON_EXECUTION_CONTRACT_V1",
        "sku": sku,
        "power_watts": power_watts,
        "target_sm": target_sm,
        "nvpmodel": nvpmodel_bound,
        "real_time": rt_bound,
        "zero_copy": zero_copy_bound,
        "tensorrt": trt_bound,
        "latency": latency_bound,
        "thermal": thermal_bound,
        "sgm": sgm_bound,
        "scope_match": scope_match,
        "replay_verified": replay_verified,
        "agent_plane_blocks_hard_path": agent_plane_blocks_hard_path,
    }
    return bound, sorted(set(failures))


def build_receipt(raw: dict[str, Any]) -> dict[str, Any]:
    bound, failures = validate_input(raw)
    evidence_digest = sha256_bytes(canonical_bytes(bound))
    verdict = "ADMITTED" if not failures else "DENIED"
    body = {
        "contract": bound["contract"],
        "evidence_digest": evidence_digest,
        "failures": failures,
        "verdict": verdict,
    }
    return {
        **body,
        "receipt_hash": sha256_bytes(canonical_bytes(body)),
        "bound_evidence": bound,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    try:
        raw = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise EvidenceError("input root must be a JSON object")
        receipt = build_receipt(raw)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_bytes(canonical_bytes(receipt) + b"\n")
    except (OSError, json.JSONDecodeError, EvidenceError) as exc:
        print(f"DENIED: {exc}", file=sys.stderr)
        return 2

    print(receipt["verdict"])
    print(f"receipt_hash={receipt['receipt_hash']}")
    return 0 if receipt["verdict"] == "ADMITTED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
