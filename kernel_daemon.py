import os
import sys
import time
import json
import httpx
from pathlib import Path
from kernel_one import KernelOneEngine

def get_shared_ipc_dir():
    candidates = [
        Path.home() / "Documents" / "Aegis_IPC",
        Path.home() / "Aegis_IPC",
        Path.cwd() / "Aegis_IPC"
    ]
    for target in candidates:
        try:
            target.mkdir(parents=True, exist_ok=True)
            test_file = target / ".write_test"
            test_file.touch()
            test_file.unlink()
            return target
        except (PermissionError, OSError):
            continue
    raise RuntimeError("No writable directory found for Aegis_IPC")

SHARED_IPC_DIR = get_shared_ipc_dir()
INBOX_PATH = SHARED_IPC_DIR / "kernel_inbox.json"
STAGING_OUTBOX_PATH = SHARED_IPC_DIR / "kernel_outbox.tmp"
FINAL_OUTBOX_PATH = SHARED_IPC_DIR / "kernel_outbox.json"

KERNEL = KernelOneEngine()

def invoke_local_inference_server(task: str) -> str:
    url = os.getenv("AEGIS_MODEL_URL", "http://127.0.0.1:8080/v1/chat/completions")
    model_name = os.getenv("AEGIS_MODEL_NAME", "gemma-local")
    
    system_prompt = (
        "Return ONLY valid JSON with keys: "
        "'plan', 'output', 'tool_calls'. No extra markdown prose text."
    )
    payload = {
        "model": model_name,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task}
        ],
        "temperature": 0.1
    }

    limits = httpx.Limits(max_keepalive_connections=1, max_connections=1)
    timeout_config = httpx.Timeout(60.0, connect=30.0)

    with httpx.Client(timeout=timeout_config, limits=limits) as client:
        try:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"]
        except Exception as e:
            return None  # Signal failure to caller

if __name__ == "__main__":
    print(f"[*] Kernel One Active. Secure File POSIX Channel monitoring: {SHARED_IPC_DIR}")
    print("[!] NOTE: External writers MUST use atomic replacement: write to .tmp, then os.replace() to .json")
    try:
        while True:
            if INBOX_PATH.exists():
                time.sleep(0.05)  # Allow OS to fully commit inode update if file just appeared
                try:
                    with open(INBOX_PATH, "r", encoding="utf-8") as f:
                        request_payload = json.load(f)
                    
                    print(f"[+] Processing Task ID: {request_payload.get('request_id', 'UNKNOWN')}")

                    raw_response = invoke_local_inference_server(request_payload.get("task", ""))
                    if raw_response is None:
                        execution_trace = {
                            "status": "RECONCILED_FALLBACK",
                            "request_id": request_payload.get('request_id', 'UNKNOWN'),
                            "reason": "Local inference server unavailable."
                        }
                    else:
                        execution_trace = KERNEL.process_transaction(request_payload, raw_response)

                    with open(STAGING_OUTBOX_PATH, "w", encoding="utf-8") as f:
                        json.dump(execution_trace, f, indent=2)

                    os.replace(STAGING_OUTBOX_PATH, FINAL_OUTBOX_PATH)
                    print(f"[SUCCESS] State compilation complete. Status: {execution_trace.get('status', 'UNKNOWN')}")

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