from __future__ import annotations

import json
import os
import hashlib
from pathlib import Path
from typing import Any, Dict, Optional

from kernel_one import KernelOneEngine


class FrontierRouter:
    """
    Escalates rejected trajectories to frontier nodes.
    The remote model remains a proposal engine; the local kernel remains the authority.
    """
    def __init__(
        self,
        kernel: Optional[KernelOneEngine] = None,
        frontier_request_path: str = "frontier_request.json",
        frontier_response_path: str = "frontier_response.json",
    ):
        self.kernel = kernel or KernelOneEngine()
        self.frontier_request_path = Path(frontier_request_path)
        self.frontier_response_path = Path(frontier_response_path)

    def _sha256_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _atomic_write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        tmp_path = path.with_suffix(path.suffix + ".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        os.replace(tmp_path, path)

    def build_frontier_request(
        self,
        task: str,
        rejection_reason: str,
        witness_id: Optional[str],
        index_hash: str,
        residual_delta: float,
        retry_count: int = 0,
    ) -> Dict[str, Any]:
        return {
            "request_id": self._sha256_text(
                f"{task}:{rejection_reason}:{index_hash}:{witness_id}:{retry_count}"
            ),
            "task": task,
            "reason": rejection_reason,
            "witness_id": witness_id,
            "index_hash": index_hash,
            "residual_delta": residual_delta,
            "retry_count": retry_count,
        }

    def persist_frontier_request(self, payload: Dict[str, Any]) -> None:
        self._atomic_write_json(self.frontier_request_path, payload)

    def load_frontier_response(self) -> Dict[str, Any]:
        if not self.frontier_response_path.exists():
            raise FileNotFoundError(
                f"Missing frontier response payload at: {self.frontier_response_path}"
            )
        with open(self.frontier_response_path, "r", encoding="utf-8") as f:
            return json.load(f)

    def validate_frontier_response(
        self,
        request_payload: Dict[str, Any],
        frontier_response: Dict[str, Any],
    ) -> Dict[str, Any]:
        raw_model_response = json.dumps({
            "plan": frontier_response.get("plan", ""),
            "output": frontier_response.get("output", ""),
            "tool_calls": frontier_response.get("tool_calls", []),
        })

        if "metrics" not in request_payload:
            request_payload["metrics"] = {
                "uncertainty": 0.0,
                "tool_failures": 0,
                "novelty": 0.0,
                "reviewer_disagreement": 0.0
            }

        return self.kernel.process_transaction(
            request_payload=request_payload,
            raw_model_response=raw_model_response,
        )

    def escalate(
        self,
        task: str,
        rejection_reason: str,
        request_payload: Dict[str, Any],
    ) -> Dict[str, Any]:
        index_hash = "EMPTY"
        if hasattr(self.kernel, "manifest_path") and self.kernel.manifest_path.exists():
            index_hash = hashlib.sha256(self.kernel.manifest_path.read_bytes()).hexdigest()

        frontier_payload = self.build_frontier_request(
            task=task,
            rejection_reason=rejection_reason,
            witness_id=request_payload.get("parent_witness") or request_payload.get("witness"),
            index_hash=index_hash,
            residual_delta=request_payload.get("metrics", {}).get("uncertainty", 1.0),
            retry_count=int(request_payload.get("retry_count", 0)),
        )

        self.persist_frontier_request(frontier_payload)

        try:
            frontier_response = self.load_frontier_response()
        except FileNotFoundError as e:
            return {
                "status": "RECONCILED_FALLBACK",
                "request_id": request_payload.get("request_id", "UNKNOWN"),
                "reason": str(e)
            }

        return self.validate_frontier_response(
            request_payload=request_payload,
            frontier_response=frontier_response
        )
