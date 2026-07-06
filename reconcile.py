import json
import sqlite3
from pathlib import Path

DB_PATH = Path("memory_store.sqlite")

class Reconciler:
    def __init__(self, state_path="state_vector.json", db_path="memory_store.sqlite"):
        self.state_path = state_path
        self.db_path = db_path

    def rollback_to_last_verified(self):
        conn = sqlite3.connect(self.db_path)
        try:
            row = conn.execute(
                """
                SELECT w.witness_id, w.phase, w.residual_delta, a.tool_calls
                FROM witnesses w
                JOIN artifacts a ON w.witness_id = a.witness_id
                WHERE w.validity='VERIFIED'
                ORDER BY w.timestamp DESC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                raise RuntimeError("No VERIFIED witness exists.")

            witness_id, phase, delta, tool_calls_json = row
            
            # Verify signature before rollback
            try:
                tool_calls_data = json.loads(tool_calls_json)
                stored_signature = tool_calls_data.get("signature")
                if not stored_signature:
                    raise RuntimeError("Missing signature in artifact.")
                
                # Recompute signature
                import hmac
                import hashlib
                from kernel_one import KERNEL_SECRET_SIGNING_KEY
                expected_signature = hmac.new(
                    KERNEL_SECRET_SIGNING_KEY,
                    witness_id.encode("utf-8"),
                    hashlib.sha256
                ).hexdigest()
                
                if not hmac.compare_digest(stored_signature, expected_signature):
                    raise RuntimeError("Corrupted witness detected: Signature mismatch.")
            except Exception as e:
                raise RuntimeError(f"Witness integrity verification failed: {str(e)}")

            state = {
                "phase": "ASSESS",
                "witness": witness_id,
                "validity": "UNVERIFIED",
                "residual_delta": delta,
                "retry_count": 0
            }

            with open(self.state_path, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)

            return state
        finally:
            conn.close()