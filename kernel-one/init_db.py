import sqlite3
from pathlib import Path

DB_PATH = Path("memory_store.sqlite")
SCHEMA = """
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

CREATE TABLE IF NOT EXISTS witness_envelopes (
    witness_id TEXT PRIMARY KEY,
    schema_version TEXT NOT NULL,
    request_id TEXT NOT NULL,
    artifact_path TEXT NOT NULL,
    artifact_sha256 TEXT NOT NULL,
    observed_at INTEGER NOT NULL,
    sequence INTEGER NOT NULL,
    parent_receipt_hash TEXT NOT NULL,
    key_id TEXT NOT NULL,
    algorithm TEXT NOT NULL CHECK (algorithm = 'hmac-sha256'),
    canonical_json TEXT NOT NULL,
    signature TEXT NOT NULL,
    UNIQUE(key_id, sequence),
    FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
);
CREATE INDEX IF NOT EXISTS idx_witness_envelope_request
    ON witness_envelopes(request_id);
CREATE INDEX IF NOT EXISTS idx_witness_envelope_parent
    ON witness_envelopes(parent_receipt_hash);
"""


def initialize_database(db_path: str | Path = DB_PATH):
    path = Path(db_path)
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        print(f"[OK] {path} initialized")
    finally:
        conn.close()


if __name__ == "__main__":
    initialize_database()
