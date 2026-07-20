import os
import json
import time
import hmac
import hashlib
import sqlite3
from typing import Any
from pathlib import Path
import yaml
from validator import calculate_residual_delta, ValidationError, validate_request_structure, validate_proposal_schema

KERNEL_SECRET_SIGNING_KEY = os.environ.get(
    "AEGIS_KERNEL_SIGNING_KEY", "aegis_sovereign_secure_key_vector_2026"
).encode("utf-8")

class KernelOneEngine:
    def __init__(self, manifest_path="INDEX.yaml", db_path="memory_store.sqlite"):
        self.manifest_path = Path(manifest_path)
        self.db_path = Path(db_path)
        self.model_version = "Gemma-2B-INT4-Local"

    def _load_manifest(self) -> dict:
        if not self.manifest_path.exists():
            return {"safety": {"delta_critical": 0.70}, "files": {}}
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def sign_witness(self, witness_id: str) -> str:
        return hmac.new(KERNEL_SECRET_SIGNING_KEY, witness_id.encode("utf-8"), hashlib.sha256).hexdigest()

    def process_transaction(self, request_payload: Any, raw_model_response: str) -> dict:
        request_id = "UNKNOWN"
        try:
            validated_req = validate_request_structure(request_payload)
            request_id = validated_req["request_id"]
            task = validated_req["task"]
            metrics = validated_req["metrics"]
            target_file = request_payload.get("target_file", None)

            manifest = self._load_manifest()
            delta = calculate_residual_delta(metrics)

            if delta >= manifest["safety"]["delta_critical"]:
                raise ValidationError(f"Entropy threshold exceeded. Delta: {delta:.2f}")

            proposal = validate_proposal_schema(raw_model_response, str(self.manifest_path), target_file)

            task_hash = hashlib.sha256(task.encode()).hexdigest()
            plan_hash = hashlib.sha256(proposal["plan"].encode()).hexdigest()
            output_hash = hashlib.sha256(proposal["output"].encode()).hexdigest()
            index_hash = hashlib.sha256(self.manifest_path.read_bytes()).hexdigest() if self.manifest_path.exists() else "EMPTY"

            witness_id = hashlib.sha256(
                f"{request_id}:{task_hash}:{plan_hash}:{output_hash}:{index_hash}:{self.model_version}:{int(time.time())}".encode()
            ).hexdigest()
            
            signature = self.sign_witness(witness_id)

            conn = sqlite3.connect(self.db_path)
            try:
                conn.execute(
                    """INSERT INTO witnesses (witness_id, timestamp, phase, validity, model_version, index_hash, residual_delta, plan_hash, output_hash, parent_witness)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (witness_id, int(time.time()), "HARMONIZE", "VERIFIED", self.model_version, index_hash, delta, plan_hash, output_hash, request_payload.get("parent_witness"))
                )
                conn.execute(
                    "INSERT INTO artifacts (witness_id, plan, output, tool_calls) VALUES (?, ?, ?, ?)",
                    (witness_id, proposal["plan"], proposal["output"], json.dumps(proposal["tool_calls"]))
                )
                conn.commit()
            finally:
                conn.close()

            return {"status": "HARMONIZE_SUCCESS", "request_id": request_id, "witness_id": witness_id, "signature": signature, "admissible_output": proposal["output"]}
        except Exception as e:
            return {"status": "RECONCILED_FALLBACK", "request_id": request_id, "reason": str(e)}
