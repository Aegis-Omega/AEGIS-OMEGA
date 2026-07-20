import json
import sqlite3

DB_PATH = "memory_store.sqlite"


class Reconciler:
    def __init__(self, state_path="state_vector.json"):
        self.state_path = state_path

    def rollback_to_last_verified(self):
        conn = sqlite3.connect(DB_PATH)
        try:
            row = conn.execute(
                """
                SELECT witness_id, phase, residual_delta
                FROM witnesses
                WHERE validity='VERIFIED'
                ORDER BY timestamp DESC
                LIMIT 1
                """
            ).fetchone()

            if row is None:
                raise RuntimeError("No VERIFIED witness exists.")

            witness_id, phase, delta = row
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
