"""Adversarial tests for whole-corpus evolutionary intake #758."""
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_corpus_wide_v1 import (evolve_representation,evolve_numeric_csv,
    validate_source, run, inspect_structure)


class CorpusWide(unittest.TestCase):
    def setUp(self):
        self.ctx=tempfile.TemporaryDirectory()
        self.addCleanup(self.ctx.cleanup)
        self.root=Path(self.ctx.name)
        self.catalog=self.root/'catalog.sqlite'
        self.out=self.root/'evolved.sqlite'
        c=sqlite3.connect(self.catalog)
        c.execute('''CREATE TABLE objects(id INTEGER PRIMARY KEY,member TEXT,extracted_path TEXT,
            sha256 TEXT,bytes INTEGER,format TEXT,category TEXT,status TEXT)''')
        raw=(b'alpha,beta\n'+b'hello,world\n'*32)
        (self.root/'test.csv').write_bytes(raw)
        sha=hashlib.sha256(raw).hexdigest()
        records=[(1,'test.csv','test.csv',sha,len(raw),'.csv','STRUCTURED_DATA','IMPORTED_BYTES_VERIFIED'),
                 (2,'copy.csv','test.csv',sha,len(raw),'.csv','STRUCTURED_DATA','IMPORTED_BYTES_VERIFIED'),
                 (3,'unavailable','','',0,'','OTHER','QUARANTINED_OSError')]
        c.executemany('INSERT INTO objects VALUES (?,?,?,?,?,?,?,?)',records)
        c.commit();c.close()
        self.sha=sha
    def test_every_row_accounted_for(self):
        r=run(self.catalog,self.root,self.out)
        self.assertEqual((r['objects_accounted_for'],r['total_indexed']),(3,3))
        self.assertEqual(r['unique_asset_states'],{'EVOLVED_ROUNDTRIP_VERIFIED':1})
        self.assertEqual(r['object_states']['DEDUP_LINKED_TO_EVALUATED_CONTENT'],1)
        self.assertEqual(r['object_states']['SOURCE_QUARANTINED'],1)
        self.assertEqual(r['admission'],'DENIED')
    def test_roundtrip_both_competing_codecs(self):
        r=evolve_representation(self.root/'test.csv',self.sha,(self.root/'test.csv').stat().st_size)
        self.assertEqual(len(r['trials']),3)
        self.assertTrue(r['verified_full_file'])
        self.assertGreaterEqual(r['representation_gain_bytes'],0)
    def test_bad_source_hash_fails_closed(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_SHA_MISMATCH'):
            evolve_representation(self.root/'test.csv','a'*64,(self.root/'test.csv').stat().st_size)
    def test_traversal_rejected(self):
        for s in ('../x','/etc/passwd','a/../../x','x\\y'):
            with self.subTest(s=s),self.assertRaises(ValueError):
                validate_source(self.root,s,self.sha,0)
    def test_symlink_rejected(self):
        (self.root/'link').symlink_to('/etc/passwd')
        with self.assertRaisesRegex(ValueError,'SOURCE_SYMLINK'):
            validate_source(self.root,'link',self.sha,0)
    def test_resume_after_budget(self):
        (self.root/'other.txt').write_text('some other scientific data')
        raw=(self.root/'other.txt').read_bytes();h=hashlib.sha256(raw).hexdigest()
        c=sqlite3.connect(self.catalog);c.execute('INSERT INTO objects VALUES(4,?,?,?,?,?,?,?)',
            ('other.txt','other.txt',h,len(raw),'.txt','OTHER','IMPORTED_BYTES_VERIFIED'));c.commit();c.close()
        a=run(self.catalog,self.root,self.out,budget=1)
        self.assertEqual(a['object_states']['AWAITING_RUN_BUDGET'],1)
        b=run(self.catalog,self.root,self.out,budget=1)
        self.assertEqual(b['objects_accounted_for'],4)
        self.assertTrue(b['complete'])
        self.assertNotIn('AWAITING_RUN_BUDGET',b['object_states'])
        self.assertEqual(b['run_evaluated_new_unique'],1)
    def test_corrupt_is_not_dedup_claimed(self):
        c=sqlite3.connect(self.catalog);c.execute('UPDATE objects SET sha256=? WHERE id=1',('0'*64,));c.commit();c.close()
        r=run(self.catalog,self.root,self.out)
        self.assertEqual(r['object_states']['EXPERIMENT_BLOCKED'],1)
        self.assertEqual(r['object_states']['UNIQUE_REPRESENTATION_EVOLVED'],1)
    def test_json_parse_does_not_run_python(self):
        p=self.root/'test.py';p.write_text('raise RuntimeError("never execute")\n')
        self.assertEqual(inspect_structure(p,'.py')['state'],'PARSED_PYTHON_AST')
    def test_csv_non_numeric_not_promoted(self):
        r=evolve_numeric_csv(self.root/'test.csv')
        self.assertEqual(r['state'],'NOT_NUMERIC_TIMESERIES')
    def test_csv_real_forecast_selected_only_on_validation(self):
        p=self.root/'real.csv'
        p.write_text('time,value\n'+''.join(f'{i},{i*3+.01*i*i}\n' for i in range(180)))
        r=evolve_numeric_csv(p)
        self.assertEqual(r['state'],'OBSERVATIONAL_EVALUATED_NOT_ADMITTED')
        self.assertEqual(r['promotion'],'DENIED')
        self.assertEqual(r['selected_on'],'TEMPORAL_VALIDATION_ONLY')
    def test_time_axis_not_mistaken_for_scientific_discovery(self):
        p=self.root/'dynamic.csv'
        import math
        p.write_text('time_fs,coherence_l1\n'+''.join(
            f'{i*1e6},{math.sin(i*.13)+.2*math.cos(i*.067)}\n'
            for i in range(300)))
        r=evolve_numeric_csv(p)
        self.assertEqual(r['state'],'OBSERVATIONAL_EVALUATED_NOT_ADMITTED')
        self.assertEqual(r['target_column'],'coherence_l1')
        self.assertEqual(r['promotion'],'DENIED')

    def test_tabular_automatically_selects_measured_target(self):
        from agents.alphaevolve_corpus_wide_v1 import evolve_tabular_relations
        p=self.root/'tabular.csv'
        p.write_text('run_id,temperature,noise,quality_score\n'+''.join(
            f'{i},{1+i*.12},{(i*3)%7},{4+(.12*i)*2+((i*3)%7)*.01}\n'
            for i in range(200)))
        x=evolve_tabular_relations(p)
        self.assertEqual(x['state'],'OBSERVATIONAL_TABULAR_EVALUATED_NOT_ADMITTED')
        self.assertEqual(x['target'],'quality_score')
        self.assertEqual(x['admission'],'DENIED')
        self.assertGreaterEqual(x['candidate_count'],3)

    def test_tabular_fails_closed_without_label_semantics(self):
        from agents.alphaevolve_corpus_wide_v1 import evolve_tabular_relations
        p=self.root/'numbers.csv'
        p.write_text('a,b,c\n'+''.join(f'{i},{i*i},{i*i*i}\n' for i in range(200)))
        x=evolve_tabular_relations(p)
        self.assertEqual(x['state'],'TABULAR_NOT_EVALUATED')
        self.assertEqual(x['reason'],'TARGET_SEMANTICS_NOT_IDENTIFIED')

    def test_idempotent_same_source(self):
        a=run(self.catalog,self.root,self.out)
        b=run(self.catalog,self.root,self.out)
        self.assertEqual(a['candidate_trials'],b['candidate_trials'])
        self.assertEqual(b['run_evaluated_new_unique'],0)
    def test_catalog_cannot_be_mutated(self):
        with self.assertRaisesRegex(ValueError,'INPUT_MUTATION_FORBIDDEN'):
            run(self.catalog,self.root,self.catalog)

if __name__=='__main__':unittest.main()
