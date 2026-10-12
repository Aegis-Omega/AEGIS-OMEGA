"""AEGIS Ω #758 — truthful, arbitrary-precision generation IDs and audit chain.

The ID can represent generation 2**128 and beyond, but IDs are NOT evidence that
those generations occurred. Only one completed evaluator outcome advances the
counter. SQLite TEXT avoids implicit 64-bit / IEEE754 coercion. The hash chain
is unsigned and provides integrity/replay only, not publisher authenticity.
"""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3

SCHEMA = 'AEGIS_GENERATION_LEDGER_V1'
GENESIS = '0' * 64
MAX_ID_DIGITS = 4096


def generation_id(value: int | str) -> str:
    if type(value) is int:
        if value < 0:
            raise ValueError('GENERATION_NEGATIVE')
        value = str(value)
    if not isinstance(value, str) or not 1 <= len(value) <= MAX_ID_DIGITS or not re.fullmatch(r'0|[1-9][0-9]*', value):
        raise ValueError('GENERATION_ID_NONCANONICAL')
    return value


def _canonical(value: dict) -> str:
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False)


def _get(conn: sqlite3.Connection, key: str):
    row = conn.execute('SELECT value FROM campaign WHERE key=?', (key,)).fetchone()
    return None if row is None else json.loads(row[0])


def _set(conn: sqlite3.Connection, key: str, value):
    conn.execute('INSERT OR REPLACE INTO campaign (key,value) VALUES (?,?)', (key, _canonical(value)))


def migrate_integer_tick_schema(conn: sqlite3.Connection) -> bool:
    """Transactional, lossless migration from the real AEGIS integer-tick tables.

    Keep every row, including all recorded family/parent references, and rebuild
    candidate ranking indices. Never cast generation identifiers through FLOAT.
    """
    specs = [
        ('ticks', '''CREATE TABLE ticks (tick TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,status TEXT NOT NULL)''',
         'INSERT INTO ticks SELECT CAST(tick AS TEXT), candidate_id, status FROM ticks_legacy_v1 ORDER BY tick'),
        ('breeding', '''CREATE TABLE breeding (tick TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,mother_id TEXT,father_id TEXT,genome TEXT NOT NULL,inheritance_trace TEXT NOT NULL,genome_digest TEXT NOT NULL)''',
         'INSERT INTO breeding SELECT CAST(tick AS TEXT),candidate_id,mother_id,father_id,genome,inheritance_trace,genome_digest FROM breeding_legacy_v1 ORDER BY tick'),
        ('candidates', '''CREATE TABLE candidates (id TEXT PRIMARY KEY,island INTEGER NOT NULL,tick TEXT NOT NULL,parent TEXT,program TEXT NOT NULL,train REAL NOT NULL,validation REAL NOT NULL,regression INTEGER NOT NULL,outcome TEXT NOT NULL,evaluation_digest TEXT NOT NULL)''',
         'INSERT INTO candidates SELECT id,island,CAST(tick AS TEXT),parent,program,train,validation,regression,outcome,evaluation_digest FROM candidates_legacy_v1'),
    ]
    needs = []
    for name, create, copy in specs:
        columns = conn.execute(f'PRAGMA table_info({name})').fetchall()
        if not columns:
            raise ValueError('GENERATION_SCHEMA_TABLE_MISSING:' + name)
        kind = next((col[2].upper() for col in columns if col[1] == 'tick'), None)
        if kind not in ('INTEGER', 'TEXT'):
            raise ValueError('GENERATION_SCHEMA_TICK_UNKNOWN:' + name)
        if kind == 'INTEGER':
            needs.append((name, create, copy))
    if not needs:
        return False
    # The schema is committed by the caller. Every table modification is atomic.
    with conn:
        for name, create, copy in needs:
            conn.execute(f'ALTER TABLE {name} RENAME TO {name}_legacy_v1')
            conn.execute(create)
            conn.execute(copy)
            before = conn.execute(f'SELECT COUNT(*) FROM {name}_legacy_v1').fetchone()[0]
            after = conn.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]
            if before != after:
                raise ValueError('GENERATION_SCHEMA_MIGRATION_LOST_ROWS')
            conn.execute(f'DROP TABLE {name}_legacy_v1')
        conn.execute('CREATE INDEX IF NOT EXISTS idx_candidates_rank ON candidates(island,regression,validation)')
    return True


def prepare(conn: sqlite3.Connection, *, binding: str) -> None:
    """Backfill existing local ticks transparently, but never claim they were re-run."""
    if not isinstance(binding, str) or not re.fullmatch('[a-f0-9]{64}', binding):
        raise ValueError('GENERATION_BINDING_INVALID')
    migrate_integer_tick_schema(conn)
    conn.execute('''CREATE TABLE IF NOT EXISTS generation_ledger (
        generation TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
        prev_hash TEXT NOT NULL, entry_hash TEXT NOT NULL,
        status TEXT NOT NULL, source TEXT NOT NULL)''')
    count = conn.execute('SELECT COUNT(*) FROM ticks').fetchone()[0]
    registered = conn.execute('SELECT COUNT(*) FROM generation_ledger').fetchone()[0]
    if registered == 0 and count:
        with conn:
            rows = conn.execute('SELECT tick,candidate_id,status FROM ticks ORDER BY rowid').fetchall()
            if len(rows) != count:
                raise ValueError('GENERATION_BACKFILL_INCONSISTENT')
            prev = GENESIS
            for i, (raw, cid, status) in enumerate(rows):
                gen = generation_id(raw)
                if gen != str(i):
                    raise ValueError('GENERATION_LEGACY_SEQUENCE_GAP')
                prev = _insert(conn, gen, cid, status, binding, prev, 'LEGACY_RECORD_UNAUTHENTICATED')
    verify(conn, binding=binding)


def _insert(conn: sqlite3.Connection, gen: str, cid: str, status: str,
            binding: str, prev_hash: str, source: str) -> str:
    body = {'schema': SCHEMA, 'generation': gen, 'candidate': cid,
            'status': status, 'source_binding': binding, 'prev_hash': prev_hash,
            'source': source}
    h = hashlib.sha256(_canonical(body).encode('ascii')).hexdigest()
    conn.execute('INSERT INTO generation_ledger VALUES (?,?,?,?,?,?)',
                 (gen, cid, prev_hash, h, status, source))
    return h


def verify(conn: sqlite3.Connection, *, binding: str) -> dict:
    prev = GENESIS
    observed = 0
    cursor = conn.execute('SELECT generation,candidate_id,prev_hash,entry_hash,status,source FROM generation_ledger ORDER BY rowid')
    for raw, cid, predecessor, claimed, status, source in cursor:
        gen = generation_id(raw)
        if gen != str(observed) or predecessor != prev or source not in ('EVALUATED_TICK', 'LEGACY_RECORD_UNAUTHENTICATED'):
            raise ValueError('GENERATION_LEDGER_SEQUENCE_OR_LINK_INVALID')
        body = {'schema': SCHEMA, 'generation': gen, 'candidate': cid,
                'status': status, 'source_binding': binding, 'prev_hash': predecessor,
                'source': source}
        actual = hashlib.sha256(_canonical(body).encode('ascii')).hexdigest()
        if actual != claimed:
            raise ValueError('GENERATION_LEDGER_HASH_INVALID')
        row = conn.execute('SELECT candidate_id,status FROM ticks WHERE tick=?', (gen,)).fetchone()
        if row != (cid, status):
            raise ValueError('GENERATION_LEDGER_TICK_MISMATCH')
        prev = claimed
        observed += 1
    real_count = conn.execute('SELECT COUNT(*) FROM ticks').fetchone()[0]
    if observed != real_count:
        raise ValueError('GENERATION_LEDGER_COUNT_MISMATCH')
    return {'next_generation': str(observed), 'chain_root': prev, 'verified_records': observed,
            'source_authentication': 'NOT_ESTABLISHED'}


def append_evaluated(conn: sqlite3.Connection, *, generation: int, candidate_id: str,
                     status: str, binding: str, prior_root: str) -> str:
    gen = generation_id(generation)
    if conn.execute('SELECT tick FROM ticks WHERE tick=?', (gen,)).fetchone() != (gen,):
        raise ValueError('GENERATION_TICK_NOT_RECORDED')
    if conn.execute('SELECT generation FROM generation_ledger WHERE generation=?', (gen,)).fetchone():
        raise ValueError('GENERATION_ALREADY_RECORDED')
    last = conn.execute('SELECT entry_hash FROM generation_ledger ORDER BY rowid DESC LIMIT 1').fetchone()
    if (last[0] if last else GENESIS) != prior_root:
        raise ValueError('GENERATION_ROOT_STALE')
    return _insert(conn, gen, candidate_id, status, binding, prior_root, 'EVALUATED_TICK')
