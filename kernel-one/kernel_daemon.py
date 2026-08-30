import os
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
    print("\n[!] Graceful shutdown sequence initialized. Stopping IPC loops.")
    sys.exit(0)
