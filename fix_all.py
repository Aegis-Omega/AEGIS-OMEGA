import os

TARGET_DIR = r"C:\Users\hhk33\Documents\AEGIS--"
os.makedirs(TARGET_DIR, exist_ok=True)
os.chdir(TARGET_DIR)

files = {
    "init_db.py": """import sqlite3
from pathlib import Path

DB_PATH = Path("memory_store.sqlite")
SCHEMA = \"\"\"
PRAGMA journal_mode=WAL;
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS witnesses (
    witness_id TEXT PRIMARY KEY,
    timestamp INTEGER NOT NULL,
    phase TEXT NOT NULL,
    validity TEXT NOT NULL,
    model_version TEXT NOT NULL,
    index_hash TEXT NOT NULL,
    residual_delta REAL NOT NULL,
    plan_hash TEXT NOT NULL,
    output_hash TEXT NOT NULL,
    parent_witness TEXT,
    FOREIGN KEY(parent_witness) REFERENCES witnesses(witness_id)
);
CREATE INDEX IF NOT EXISTS idx_witness_validity ON witnesses(validity);
CREATE INDEX IF NOT EXISTS idx_witness_timestamp ON witnesses(timestamp);
CREATE INDEX IF NOT EXISTS idx_witness_index ON witnesses(index_hash);

CREATE TABLE IF NOT EXISTS artifacts (
    witness_id TEXT PRIMARY KEY,
    plan TEXT,
    output TEXT,
    tool_calls TEXT,
    FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
);
\"\"\"

def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print("[OK] memory_store.sqlite initialized")
    finally:
        conn.close()

if __name__ == "__main__":
    initialize_database()
""",
    "validator.py": """import hashlib
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
""",
    "kernel_one.py": """import json
import time
import hmac
import hashlib
import sqlite3
from typing import Any
from pathlib import Path
import yaml
from validator import calculate_residual_delta, ValidationError, validate_request_structure, validate_proposal_schema

KERNEL_SECRET_SIGNING_KEY = b"aegis_sovereign_secure_key_vector_2026"

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
                    \"\"\"INSERT INTO witnesses (witness_id, timestamp, phase, validity, model_version, index_hash, residual_delta, plan_hash, output_hash, parent_witness)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\"\"\",
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
""",
    "test_kernel_one.py": """import json
from pathlib import Path
from kernel_one import KernelOneEngine

PAYLOADS = Path("adversarial_payloads.jsonl")

def load_payloads():
    return [json.loads(line) for line in PAYLOADS.read_text().splitlines() if line.strip()]

def main():
    kernel = KernelOneEngine()
    cases = load_payloads()
    passed_assertions = 0
    print(f"[TEST RUNNER] Executing {len(cases)} Test Manifest Configurations...\\n")

    for case in cases:
        request = {"task": case.get("task", ""), "metrics": case.get("metrics", {}), "parent_witness": None}
        if "request_id" in case: request["request_id"] = case["request_id"]
        if "target_file" in case: request["target_file"] = case["target_file"]

        proposal_dict = {}
        if "plan" in case or "output" in case or "tool_calls" in case:
            if "plan" in case: proposal_dict["plan"] = case["plan"]
            if "output" in case: proposal_dict["output"] = case["output"]
            if "tool_calls" in case: proposal_dict["tool_calls"] = case["tool_calls"]
        else:
            proposal_dict = {"plan": "Default valid action blueprint strategy", "output": "Execution block finalized cleanly.", "tool_calls": []} if case.get("name") != "missing_tool_calls" else {"plan": "Implement orchestrator", "output": "done"}
        
        if "unexpected" in case: proposal_dict["unexpected"] = case["unexpected"]

        result = kernel.process_transaction(request, json.dumps(proposal_dict))
        status_match = result["status"] == case["expected_status"]
        
        if status_match:
            passed_assertions += 1
            print(f"[OK] {case['name']:<30} => Returned: {result['status']:<20} | Expected: {case['expected_status']}")
        else:
            print(f"[FAIL] {case['name']:<30} => Returned: {result['status']:<20} | Expected: {case['expected_status']}")
            print(f"       Reason Noted: {result.get('reason')}")

    print(f"\\n[METRICS] Verification finished. Passed: {passed_assertions}/{len(cases)} assertions.")
    if passed_assertions != len(cases):
        raise SystemExit("Security Gate Core Failure: Adversarial bypass detected.")

if __name__ == "__main__":
    main()
""",
    "kernel_daemon.py": """import os
import sys
import time
import json
import httpx
from pathlib import Path
from kernel_one import KernelOneEngine

SHARED_IPC_DIR = Path.home() / "Documents" / "Aegis_IPC"
SHARED_IPC_DIR.mkdir(parents=True, exist_ok=True)

INBOX_PATH = SHARED_IPC_DIR / "kernel_inbox.json"
STAGING_OUTBOX_PATH = SHARED_IPC_DIR / "kernel_outbox.tmp"
FINAL_OUTBOX_PATH = SHARED_IPC_DIR / "kernel_outbox.json"

KERNEL = KernelOneEngine()

def invoke_local_inference_server(task: str) -> str:
    url = os.getenv("AEGIS_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
    model_name = os.getenv("AEGIS_MODEL_NAME", "gemma-local")
    payload = {
        "model": model_name,
        "messages": [{"role": "system", "content": "Return ONLY valid JSON with keys: 'plan', 'output', 'tool_calls'."}, {"role": "user", "content": task}],
        "temperature": 0.1
    }
    with httpx.Client(timeout=httpx.Timeout(60.0, connect=30.0), limits=httpx.Limits(max_keepalive_connections=1, max_connections=1)) as client:
        try:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return json.dumps({"plan": "CRITICAL_DAEMON_FALLBACK", "output": f"Inference pipeline stall intercepted: {str(e)}", "tool_calls": []})

print(f"[*] Kernel One Active. Secure File POSIX Channel monitoring: {SHARED_IPC_DIR}")
try:
    while True:
        if INBOX_PATH.exists():
            time.sleep(0.05)
            try:
                with open(INBOX_PATH, "r", encoding="utf-8") as f:
                    request_payload = json.load(f)
                print(f"[+] Processing Task ID: {request_payload.get('request_id', 'UNKNOWN')}")
                raw_response = invoke_local_inference_server(request_payload.get("task", ""))
                execution_trace = KERNEL.process_transaction(request_payload, raw_response)
                with open(STAGING_OUTBOX_PATH, "w", encoding="utf-8") as f:
                    json.dump(execution_trace, f, indent=2)
                os.replace(STAGING_OUTBOX_PATH, FINAL_OUTBOX_PATH)
                print(f"[SUCCESS] State compilation complete. Status: {execution_trace['status']}")
            except Exception as err:
                with open(STAGING_OUTBOX_PATH, "w", encoding="utf-8") as f:
                    json.dump({"status": "RECONCILED_FALLBACK", "reason": f"Fatal Daemon Abort Thread: {str(err)}"}, f, indent=2)
                os.replace(STAGING_OUTBOX_PATH, FINAL_OUTBOX_PATH)
            finally:
                if INBOX_PATH.exists():
                    os.remove(INBOX_PATH)
        time.sleep(0.2)
except KeyboardInterrupt:
    print("\\n[!] Graceful shutdown sequence initialized. Stopping IPC loops.")
    sys.exit(0)
"""
}

for filename, content in files.items():
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"Fixed: {filename}")

print("\\n[OK] All core files repaired. Run: python init_db.py && python test_kernel_one.py")
