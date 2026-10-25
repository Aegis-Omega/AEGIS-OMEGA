"""Safety and deterministic search replay tests for real unlabeled series."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
import numpy as np
from agents.alphaevolve_bioreactor_v1 import (parse_unlabeled_series,candidate_predict,evolve,run_catalog)

class BioreactorTests(unittest.TestCase):
    def setUp(self):
        self.d=tempfile.TemporaryDirectory()
        self.root=Path(self.d.name)
        self.db=self.root/'db.sqlite'
        c=sqlite3.connect(self.db)
        c.execute('CREATE TABLE assets(digest TEXT,relpath TEXT,science_state TEXT,format TEXT)')
        c.commit();c.close()
    def tearDown(self):self.d.cleanup()
    def write(self,sep=',',decimal=False,bad=False):
        p=self.root/'bioreactor_yeast_fixture.csv'
        with p.open('w') as f:
            for i in range(200):
                row=[float(i),float(10+i//5+(i%5)*0.2)]
                if bad and i==40:row[0]=row[0]-3
                f.write(sep.join(str(x).replace('.',',') if decimal else str(x) for x in row)+'\n')
        h=hashlib.sha256(p.read_bytes()).hexdigest()
        return p,h
    def test_headerless_comma(self):
        p,_=self.write();t,y,m=parse_unlabeled_series(p)
        self.assertEqual((len(t),y.shape[1]),(200,1));self.assertEqual(m['delimiter'],',')
    def test_semicolon_decimal_comma(self):
        p,_=self.write(';',True);t,y,m=parse_unlabeled_series(p)
        self.assertEqual(len(t),200);self.assertTrue(m['decimal_comma'])
    def test_time_axis_invalid(self):
        p,_=self.write(bad=True)
        with self.assertRaisesRegex(ValueError,'INVALID_TIME_AXIS'):parse_unlabeled_series(p)
    def test_causal_predictor_cannot_look_ahead(self):
        y=np.arange(100,dtype=float)
        for prog in ('HOLD','MEAN_8','TREND_4_HALF','EMA_0.25'):
            a=candidate_predict(y,prog)
            b=y.copy();b[90:]+=10000
            other=candidate_predict(b,prog)
            np.testing.assert_array_equal(a[:91],other[:91])
    def test_real_candidate_search_fails_closed(self):
        p,sha=self.write();r=evolve(p,sha)
        self.assertEqual(r['admission'],'DENIED')
        self.assertEqual(r['observational_results'][0]['candidate_count'],12)
        self.assertIn(r['observational_results'][0]['winner'],['HOLD','MEAN_2','MEAN_4','MEAN_8','MEAN_16','MEAN_32','TREND_2_QUARTER','TREND_4_HALF','TREND_8_QUARTER','EMA_0.25','EMA_0.5','EMA_0.75'])
        self.assertEqual(evolve(p,sha),r)
    def test_hash_change_fail_closed(self):
        p,sha=self.write();p.write_bytes(p.read_bytes()+b'\n')
        with self.assertRaisesRegex(ValueError,'SOURCE_HASH_MISMATCH'):evolve(p,sha)
    def test_catalog_discovery(self):
        p,sha=self.write()
        c=sqlite3.connect(self.db);c.execute('INSERT INTO assets VALUES(?,?,?,?)',(sha,p.name,'CSV_EVALUATOR_PENDING','.csv'));c.commit();c.close()
        r=run_catalog(self.db,self.root)
        self.assertEqual((r['discovered'],r['evaluated'],r['channels_evaluated']),(1,1,1))
        self.assertEqual(r['scientific_admission'],'DENIED')
    def test_traversal_fail_closed(self):
        c=sqlite3.connect(self.db);c.execute('INSERT INTO assets VALUES(?,?,?,?)',('0'*64,'../bioreactor_injected.csv','CSV_EVALUATOR_PENDING','.csv'));c.commit();c.close()
        x=run_catalog(self.db,self.root)
        self.assertEqual(x['blocked'][0]['status'],'SOURCE_PATH_BLOCKED')

if __name__=='__main__':unittest.main()
