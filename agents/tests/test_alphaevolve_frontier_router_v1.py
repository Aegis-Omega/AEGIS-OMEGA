import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_frontier_router_v1 import router,descriptor,reconcile_import_index

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


class IndexReconciliationTests(unittest.TestCase):
 def setUp(self):
  import hashlib,json
  self.tmp=tempfile.TemporaryDirectory()
  self.addCleanup(self.tmp.cleanup)
  self.c=Path(self.tmp.name)/'corpus.sqlite'
  self.d=Path(self.tmp.name)/'evolved.sqlite'
  c=sqlite3.connect(self.c)
  c.execute('CREATE TABLE objects(id INTEGER PRIMARY KEY,sha256 TEXT,status TEXT)')
  c.executemany('INSERT INTO objects VALUES(?,?,?)',[
   (1,'a'*64,'IMPORTED_BYTES_VERIFIED'),
   (2,'a'*64,'IMPORTED_BYTES_VERIFIED'),
   (3,'','QUARANTINED_Error'),
   (4,'c'*64,'IMPORTED_BYTES_VERIFIED')])
  c.commit();c.close()
  d=sqlite3.connect(self.d)
  d.execute('CREATE TABLE coverage(object_id INTEGER PRIMARY KEY,digest TEXT,state TEXT)')
  d.execute('CREATE TABLE assets(digest TEXT,state TEXT,verified INTEGER)')
  d.execute('CREATE TABLE meta(key TEXT PRIMARY KEY,value TEXT)')
  d.executemany('INSERT INTO coverage VALUES(?,?,?)',[
   (1,'a'*64,'UNIQUE_REPRESENTATION_EVOLVED'),
   (2,'a'*64,'DEDUP_LINKED_TO_EVALUATED_CONTENT'),
   (3,None,'SOURCE_QUARANTINED'),
   (4,None,'SENSITIVE_METADATA_ONLY')])
  d.execute('INSERT INTO assets VALUES(?,?,?)',('a'*64,'EVOLVED_ROUNDTRIP_VERIFIED',1))
  d.execute('INSERT INTO meta VALUES(?,?)',('last_receipt',json.dumps({
   'catalog_digest':hashlib.sha256(self.c.read_bytes()).hexdigest(),
   'total_indexed':4,'objects_accounted_for':4})))
  d.commit();d.close()

 def test_exact_read_only_reconciliation(self):
  import hashlib
  before=(hashlib.sha256(self.c.read_bytes()).hexdigest(),hashlib.sha256(self.d.read_bytes()).hexdigest())
  outcome=reconcile_import_index(self.c,self.d)
  self.assertEqual((outcome['objects_accounted'],outcome['unique_verified_assets'],
    outcome['alias_records'],outcome['sensitive_metadata_only'],outcome['quarantined']),(4,1,1,1,1))
  self.assertEqual(outcome['coverage_state'],'EXACT_READ_ONLY_PASS')
  self.assertEqual(outcome['scientific_admission'],'DENIED')
  self.assertEqual(before,(hashlib.sha256(self.c.read_bytes()).hexdigest(),hashlib.sha256(self.d.read_bytes()).hexdigest()))

 def test_missing_object_fails_closed(self):
  d=sqlite3.connect(self.d);d.execute('DELETE FROM coverage WHERE object_id=2');d.commit();d.close()
  with self.assertRaisesRegex(ValueError,'COVERAGE_MISMATCH'):
   reconcile_import_index(self.c,self.d)

 def test_wrong_alias_digest_fails_closed(self):
  d=sqlite3.connect(self.d);d.execute('UPDATE coverage SET digest=? WHERE object_id=2',('b'*64,));d.commit();d.close()
  with self.assertRaisesRegex(ValueError,'DIGEST_OR_STATE_MISMATCH'):
   reconcile_import_index(self.c,self.d)

 def test_stale_catalog_hash_fails_closed(self):
  c=sqlite3.connect(self.c);c.execute('INSERT INTO objects VALUES(?,?,?)',(5,'d'*64,'IMPORTED_BYTES_VERIFIED'));c.commit();c.close()
  with self.assertRaisesRegex(ValueError,'CATALOG_SHA256_MISMATCH'):
   reconcile_import_index(self.c,self.d)

 def test_unverified_asset_fails_closed(self):
  d=sqlite3.connect(self.d);d.execute('UPDATE assets SET verified=0');d.commit();d.close()
  with self.assertRaisesRegex(ValueError,'ASSET_NOT_VERIFIED'):
   reconcile_import_index(self.c,self.d)

 def test_blocked_input_fails_closed(self):
  d=sqlite3.connect(self.d);d.execute("UPDATE coverage SET state='EXPERIMENT_BLOCKED' WHERE object_id=1");d.commit();d.close()
  with self.assertRaisesRegex(ValueError,'INCOMPLETE_OR_BLOCKED'):
   reconcile_import_index(self.c,self.d)

if __name__=='__main__':unittest.main()
