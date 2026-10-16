import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_frontier_router_v1 import router,descriptor

class FrontierTests(unittest.TestCase):
 def test_domain_router_preserves_uncertainty(self):
  self.assertEqual(descriptor('.lean','FORMAL_SOURCE','FORMAL_SOURCE_STATIC_ONLY')[1], 'EVALUATOR_REQUIRED')
  self.assertEqual(descriptor('.npz','STRUCTURED_DATA','BINARY_OR_UNSUPPORTED_STRUCTURE')[0], 'QUANTUM_TENSOR')
  self.assertEqual(descriptor('.csv','STRUCTURED_DATA','CSV_TIME_SERIES_EVOLUTION')[1], 'EXECUTED_OBSERVATIONAL')
 def test_every_asset_assigned_once(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'db.sqlite';c=sqlite3.connect(p)
   c.execute('CREATE TABLE assets(digest TEXT,format TEXT,category TEXT,science_state TEXT,bytes INTEGER)')
   c.execute('CREATE TABLE coverage(state TEXT)')
   c.executemany('INSERT INTO assets VALUES (?,?,?,?,?)',[('a'*64,'.npz','OTHER','BINARY_OR_UNSUPPORTED_STRUCTURE',8),('b'*64,'.csv','DATA','CSV_TABULAR_EVOLUTION',44)])
   c.executemany('INSERT INTO coverage VALUES (?)',[('UNIQUE_REPRESENTATION_EVOLVED',),('DEDUP_LINKED_TO_EVALUATED_CONTENT',)])
   c.commit();c.close()
   r=router(p)
   self.assertEqual(r['unique_assets_assigned'],2)
   self.assertEqual(sum(x['asset_count'] for x in r['cohorts']),2)
   self.assertEqual(r['assets_by_status']['EVALUATOR_REQUIRED'],1)
   self.assertEqual(r['scientific_admission'],'DENIED')
 def test_blocked_status_fail_closed(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'db.sqlite';c=sqlite3.connect(p)
   c.execute('CREATE TABLE assets(digest TEXT,format TEXT,category TEXT,science_state TEXT,bytes INTEGER)')
   c.execute('CREATE TABLE coverage(state TEXT)')
   c.execute('INSERT INTO assets VALUES (?,?,?,?,?)',('a'*64,'.json','DATA','PARSED_JSON',1))
   c.execute('INSERT INTO coverage VALUES (?)',('AWAITING_RUN_BUDGET',));c.commit();c.close()
   with self.assertRaisesRegex(ValueError,'CORPUS_INCOMPLETE_OR_BLOCKED'):router(p)

if __name__=='__main__':unittest.main()
