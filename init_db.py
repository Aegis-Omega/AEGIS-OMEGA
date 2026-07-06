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
CREATE INDEX IF NOT EXISTS idx_witness_parent ON witnesses(parent_witness);
CREATE INDEX IF NOT EXISTS idx_witness_index ON witnesses(index_hash);

CREATE TABLE IF NOT EXISTS artifacts (
    witness_id TEXT PRIMARY KEY,
    plan TEXT,
    output TEXT,
    tool_calls TEXT,
    FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
);

CREATE TABLE IF NOT EXISTS embeddings (
    witness_id TEXT PRIMARY KEY,
    embedding BLOB,
    FOREIGN KEY(witness_id) REFERENCES witnesses(witness_id)
);
"""

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