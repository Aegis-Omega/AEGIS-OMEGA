import hashlib
import json
from pathlib import Path
from typing import Any, Dict
import yaml

class ValidationError(Exception):
    pass

def calculate_residual_delta(metrics):
    weights = {"uncertainty": 0.4, "tool_failures": 0.2, "novelty": 0.2, "reviewer_disagreement": 0.2}
    return sum(metrics[k] * weights[k] for k in weights)

def validate_request_structure(req: Any) -> Dict[str, Any]:
    if not isinstance(req, dict):
        raise ValidationError("Request must be a structural dictionary wrapper object.")
    required_keys = {"request_id": str, "task": str, "metrics": dict}
    for key, expected_type in required_keys.items():
        if key not in req:
            raise ValidationError(f"Missing required execution key: '{key}'")
        if not isinstance(req[key], expected_type):
            raise ValidationError(f"Type error on execution tracking key '{key}'")

    metrics = req["metrics"]
    for field in ["uncertainty", "tool_failures", "novelty", "reviewer_disagreement"]:
        if field not in metrics:
            raise ValidationError(f"Missing observable signal metric: '{field}'")
        if not isinstance(metrics[field], (int, float)) or isinstance(metrics[field], bool):
            raise ValidationError(f"Type violation on observable field '{field}': Must be numeric primitive.")
    return req

def validate_proposal_schema(raw_text: str, manifest_path="INDEX.yaml", target_file: str = None) -> dict:
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        raise ValidationError("Stochastic engine returned unparsable content structures.")
    
    if set(data.keys()) != {"plan", "output", "tool_calls"}:
        raise ValidationError("Payload structural schema layout contains unexpected or missing keys.")

    if not isinstance(data["plan"], str) or not isinstance(data["output"], str) or not isinstance(data["tool_calls"], list):
        raise ValidationError("Internal proposal properties violated specified typestate values.")

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = yaml.safe_load(f)
    files_registry = manifest.get("files", {})

    if target_file:
        if target_file not in files_registry or files_registry[target_file].get("frozen", False):
            raise ValidationError(f"Constitutional mutation error: File '{target_file}' is frozen.")

    for call in data["tool_calls"]:
        if not isinstance(call, dict):
            raise ValidationError("Tool structure corrupted.")
        file_arg = call.get("file")
        if file_arg and file_arg in files_registry and files_registry[file_arg].get("frozen", False):
            raise ValidationError(f"Constitutional mutation block: Tool call targets frozen asset '{file_arg}'")
    return data
