from __future__ import annotations

import copy
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve()
sys.path.insert(0, str(HERE.parents[1]))

from collect_execution_evidence import (  # noqa: E402
    EvidenceError,
    build_receipt,
)


class JetsonEvidenceCollectorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.paths = {}
        for name in ("model", "onnx", "plugin", "engine", "calibration", "sgm"):
            path = root / f"{name}.bin"
            path.write_bytes(f"artifact:{name}".encode("utf-8"))
            self.paths[name] = str(path)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def base_input(self) -> dict:
        return {
            "sku": "ORIN_NANO_SUPER_8GB",
            "power_watts": 25,
            "target_sm": 87,
            "nvpmodel": {
                "mode_name": "MAXN_SUPER",
                "mode_id": 2,
                "raw_output": "NV Power Mode: MAXN_SUPER\nMODE ID: 2\n",
            },
            "real_time": {
                "preempt_rt": True,
                "duration_seconds": 86400,
                "page_faults": 0,
                "scheduler_migrations": 0,
                "irq_latency_p99_9_us": 12,
                "irq_latency_max_us": 18,
                "p99_9_limit_us": 15,
                "max_limit_us": 20,
            },
            "zero_copy": {
                "backend": "CUDA_IPC",
                "verified": True,
                "host_memcpy_in_critical_path": 0,
                "buffer_reallocations_after_warmup": 0,
                "dma_sync_errors": 0,
                "lifecycle_violations": 0,
            },
            "tensorrt": {
                "precision": "INT4_WEIGHT_ONLY",
                "target_local_build": True,
                "explicit_qdq": True,
                "unsupported_precision_fallbacks": 0,
                "accuracy_delta_ppm": -1000,
                "max_accuracy_loss_ppm": 10000,
                "latency_p99_us": 10000,
                "artifacts": {
                    "model": self.paths["model"],
                    "onnx": self.paths["onnx"],
                    "plugin": self.paths["plugin"],
                    "engine": self.paths["engine"],
                    "calibration": self.paths["calibration"],
                },
            },
            "latency": {
                "ragc_window_p99_us": 14000,
                "end_to_end_p99_us": 48000,
                "deadline_misses": 0,
            },
            "thermal": {
                "max_temperature_millicelsius": 70000,
                "temperature_limit_millicelsius": 75000,
                "throttle_events": 0,
            },
            "sgm": {
                "certificate_path": self.paths["sgm"],
                "certificate_valid": True,
                "accepted": True,
                "hellinger_squared_ppb": 1000,
                "max_hellinger_squared_ppb": 10000,
                "policy_revision": "policy:v1",
            },
            "scope_match": True,
            "replay_verified": True,
            "agent_plane_blocks_hard_path": False,
        }

    def test_complete_evidence_is_admitted(self) -> None:
        receipt = build_receipt(self.base_input())
        self.assertEqual(receipt["verdict"], "ADMITTED")
        self.assertEqual(receipt["failures"], [])
        self.assertEqual(len(receipt["receipt_hash"]), 64)

    def test_receipt_is_deterministic(self) -> None:
        evidence = self.base_input()
        self.assertEqual(
            build_receipt(evidence)["receipt_hash"],
            build_receipt(evidence)["receipt_hash"],
        )

    def test_fp8_is_denied_on_orin(self) -> None:
        evidence = self.base_input()
        evidence["tensorrt"]["precision"] = "FP8"
        receipt = build_receipt(evidence)
        self.assertEqual(receipt["verdict"], "DENIED")
        self.assertIn("PRECISION_UNSUPPORTED_ON_ORIN", receipt["failures"])

    def test_single_deadline_miss_denies_admission(self) -> None:
        evidence = self.base_input()
        evidence["latency"]["deadline_misses"] = 1
        receipt = build_receipt(evidence)
        self.assertEqual(receipt["verdict"], "DENIED")
        self.assertIn("DEADLINE_MISS", receipt["failures"])

    def test_agent_plane_cannot_block_hard_path(self) -> None:
        evidence = self.base_input()
        evidence["agent_plane_blocks_hard_path"] = True
        receipt = build_receipt(evidence)
        self.assertEqual(receipt["verdict"], "DENIED")
        self.assertIn("AGENT_PLANE_BLOCKS_HARD_PATH", receipt["failures"])

    def test_artifact_mutation_changes_receipt(self) -> None:
        evidence = self.base_input()
        before = build_receipt(evidence)["receipt_hash"]
        Path(self.paths["engine"]).write_bytes(b"mutated-engine")
        after = build_receipt(evidence)["receipt_hash"]
        self.assertNotEqual(before, after)

    def test_missing_artifact_is_not_silently_accepted(self) -> None:
        evidence = copy.deepcopy(self.base_input())
        evidence["tensorrt"]["artifacts"]["engine"] = "/missing/engine.plan"
        with self.assertRaises(EvidenceError):
            build_receipt(evidence)


if __name__ == "__main__":
    unittest.main()
