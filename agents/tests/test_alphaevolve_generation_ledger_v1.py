"""Generation-depth invariants: 2**128 is an identifier, not fabricated work."""
from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from agents.alphaevolve_generation_ledger_v1 import generation_id, verify, GENESIS
from agents.alphaevolve_islands_v1 import search
from agents.tests.test_alphaevolve_islands_v1 import synthetic


class GenerationDepthTests(unittest.TestCase):
    def test_exact_2_to_128_generation_is_129_bit_id(self):
        n = 2**128
        self.assertEqual(generation_id(n), str(n))
        self.assertEqual(int(generation_id(n)).bit_length(), 129)
        self.assertEqual(generation_id(2**2000), str(2**2000))

    def test_no_integer_or_float_coercion_in_sqlite(self):
        with sqlite3.connect(':memory:') as conn:
            conn.execute('CREATE TABLE boundary (generation TEXT PRIMARY KEY)')
            conn.execute('INSERT INTO boundary VALUES (?)', (generation_id(2**128),))
            stored = conn.execute('SELECT generation,typeof(generation) FROM boundary').fetchone()
            self.assertEqual(stored, (str(2**128), 'text'))

    def test_noncanonical_and_negative_numbers_refused(self):
        for value in (-1, 1.5, True, '01', '+1', '1e40', '1.0', '', ' 10', '0xFF'):
            with self.subTest(value=value), self.assertRaises(ValueError):
                generation_id(value)

    def test_continuation_can_exceed_per_invocation_limit(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d); cat = synthetic(root); db = root/'campaign.sqlite'
            with patch('agents.alphaevolve_islands_v1.MAX_TICKS', 3):
                a = search(catalog=cat,root=root,database=db,additional_ticks=3)
                b = search(catalog=cat,root=root,database=db,additional_ticks=3)
            self.assertEqual(a['generation_next_decimal'], '3')
            self.assertEqual(b['generation_next_decimal'], '6')
            self.assertEqual(b['generation_ledger_verified'], 6)
            self.assertEqual(b['executed_generations_claimed'],6)
            self.assertEqual(b['generation_identifier_representation'],'ARBITRARY_PRECISION_DECIMAL_TEXT')

    def test_corrupted_earlier_generation_does_not_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'campaign.sqlite'
            search(catalog=cat,root=root,database=db,additional_ticks=5)
            with sqlite3.connect(db) as conn:
                conn.execute("UPDATE generation_ledger SET status='FORGED' WHERE generation='2'")
            with self.assertRaisesRegex(ValueError,'GENERATION_LEDGER_HASH_INVALID'):
                search(catalog=cat,root=root,database=db,additional_ticks=1)
            with sqlite3.connect(db) as conn:
                self.assertEqual(conn.execute('SELECT COUNT(*) FROM ticks').fetchone()[0], 5)

    def test_larger_claimed_generation_without_history_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'campaign.sqlite'
            search(catalog=cat,root=root,database=db,additional_ticks=3)
            with sqlite3.connect(db) as conn:
                conn.execute('INSERT INTO ticks VALUES (?,?,?)', (generation_id(2**128), 'fake', 'FAKE'))
            with self.assertRaisesRegex(ValueError,'GENERATION_LEDGER_COUNT_MISMATCH'):
                search(catalog=cat,root=root,database=db,additional_ticks=1)

    def test_legacy_integer_schema_migrates_without_loss(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'campaign.sqlite'
            with sqlite3.connect(db) as conn:
                conn.executescript('''
                  CREATE TABLE campaign (key TEXT PRIMARY KEY,value TEXT NOT NULL);
                  CREATE TABLE ticks(tick INTEGER PRIMARY KEY,candidate_id TEXT NOT NULL,status TEXT NOT NULL);
                  CREATE TABLE breeding(tick INTEGER PRIMARY KEY,candidate_id TEXT NOT NULL,mother_id TEXT,father_id TEXT,genome TEXT NOT NULL,inheritance_trace TEXT NOT NULL,genome_digest TEXT NOT NULL);
                  CREATE TABLE candidates(id TEXT PRIMARY KEY,island INTEGER NOT NULL,tick INTEGER NOT NULL,parent TEXT,program TEXT NOT NULL,train REAL NOT NULL,validation REAL NOT NULL,regression INTEGER NOT NULL,outcome TEXT NOT NULL,evaluation_digest TEXT NOT NULL);
                ''')
                conn.execute('INSERT INTO ticks VALUES (?,?,?)',(0,'older','DUPLICATE'))
                conn.execute('INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?)',
                             ('older',0,0,None,'{"schema":"AEGIS_SAFE_SIMPLEX_DSL_V1","alpha":0,"beta":0,"shrink":0}',1.0,1.0,1,'EVALUATED_VETO','a'*64))
            report=search(catalog=cat,root=root,database=db,additional_ticks=2)
            self.assertEqual(report['generation_next_decimal'],'3')
            with sqlite3.connect(db) as conn:
                self.assertEqual({c[1]:c[2] for c in conn.execute('PRAGMA table_info(ticks)')}['tick'],'TEXT')
                self.assertEqual({c[1]:c[2] for c in conn.execute('PRAGMA table_info(breeding)')}['tick'],'TEXT')
                self.assertEqual({c[1]:c[2] for c in conn.execute('PRAGMA table_info(candidates)')}['tick'],'TEXT')
                source_types=conn.execute('SELECT source FROM generation_ledger ORDER BY rowid').fetchall()
                self.assertEqual(source_types,[('LEGACY_RECORD_UNAUTHENTICATED',),('EVALUATED_TICK',),('EVALUATED_TICK',)])


if __name__ == '__main__':
    unittest.main()
