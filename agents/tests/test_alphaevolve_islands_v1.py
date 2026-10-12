"""AEGIS AlphaEvolve island-campaign regression tests; no network or untrusted execution."""
import hashlib
import json
import math
import sqlite3
import tempfile
import unittest
from pathlib import Path

import numpy as np
from agents.alphaevolve_islands_v1 import (
    _validate_program, program, Evaluator, search, finalize,
    _get_meta, KIND, MAX_TICKS, _database,
)


def synthetic(root:Path, n:int=14):
    root.mkdir(parents=True,exist_ok=True)
    db=root/'catalog.sqlite'
    c=sqlite3.connect(db)
    c.execute('CREATE TABLE objects (member TEXT,extracted_path TEXT,sha256 TEXT,bytes INTEGER,category TEXT,format TEXT,status TEXT)')
    for i in range(n):
        samples=['time,A,B,C,classical_A']
        for j in range(110):
            p=0.22+0.12*math.sin(j/17+i/23)
            q=0.3+0.06*math.cos(j/23+i/13)
            samples.append(f'{j*0.1},{p:.14g},{q:.14g},{1-p-q:.14g},0')
        data=('\n'.join(samples)+'\n').encode()
        f=root/f'series_{i}.csv';f.write_bytes(data)
        c.execute('INSERT INTO objects VALUES(?,?,?,?,?,?,?)',
            (f'GAG_gamma_{i//2}.csv',f.name,hashlib.sha256(data).hexdigest(),len(data),
             'STRUCTURED_DATA','.csv','IMPORTED_BYTES_VERIFIED'))
    c.commit();c.close();return db

class IslandTests(unittest.TestCase):
    def test_dsl_rejects_hidden_commands(self):
        with self.assertRaisesRegex(ValueError,'DSL_PROGRAM_SCHEMA'):
            _validate_program({'schema':'AEGIS_SAFE_SIMPLEX_DSL_V1','alpha':1,'beta':2,
                               'shrink':0,'__import__':'os'})
    def test_dsl_rejects_nonfinite_and_out_of_range(self):
        for value in [float('nan'),float('inf'),-20,500,True]:
            with self.subTest(value=value),self.assertRaises(ValueError):
                _validate_program({'schema':'AEGIS_SAFE_SIMPLEX_DSL_V1','alpha':value,
                                   'beta':0,'shrink':0})
    def test_program_digest_deterministic(self):
        self.assertEqual(program(1,2,.3),program(1.,2.,.3))

    def test_real_tracked_optimization_and_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'evolution.sqlite'
            a=search(catalog=cat,root=root,database=db,additional_ticks=25,islands=4)
            self.assertEqual(a['schema'],KIND)
            self.assertEqual(a['ticks_proposed'],25)
            self.assertEqual(a['holdout_evaluated'],False)
            b=search(catalog=cat,root=root,database=db,additional_ticks=18,islands=4)
            self.assertEqual(b['ticks_proposed'],43)
            self.assertGreaterEqual(b['programs_evaluated'],1)
            c=sqlite3.connect(db)
            self.assertEqual(c.execute('SELECT COUNT(*) FROM ticks').fetchone()[0],43)
            self.assertFalse(_get_meta(c,'finalized'))
            c.close()
            result=finalize(catalog=cat,root=root,database=db)
            self.assertEqual(result['scientific_admission'],'DENIED')
            self.assertFalse(result['issue758_minimum_30_independent_groups_met'])
            with self.assertRaisesRegex(ValueError,'CAMPAIGN_ALREADY_FROZEN'):
                search(catalog=cat,root=root,database=db,additional_ticks=1,islands=4)
            with self.assertRaisesRegex(ValueError,'HOLDOUT_ALREADY_OPENED'):
                finalize(catalog=cat,root=root,database=db)

    def test_source_drift_blocks_resume(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'evolution.sqlite'
            search(catalog=cat,root=root,database=db,additional_ticks=4,islands=2)
            (root/'series_0.csv').write_bytes(b'altered')
            with self.assertRaisesRegex(ValueError,'SOURCE_BYTES_HASH_MISMATCH'):
                search(catalog=cat,root=root,database=db,additional_ticks=2,islands=2)

    def test_cannot_change_islands_in_midflight(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'evolution.sqlite'
            search(catalog=cat,root=root,database=db,additional_ticks=4,islands=2)
            with self.assertRaisesRegex(ValueError,'CAMPAIGN_SOURCE_OR_CONFIG_DRIFT'):
                search(catalog=cat,root=root,database=db,additional_ticks=3,islands=3)

    def test_invalid_budget_no_campaign(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'evolution.sqlite'
            for budget in (0,True,MAX_TICKS+1):
                with self.subTest(budget=budget),self.assertRaisesRegex(ValueError,'TICK_BUDGET_INVALID'):
                    search(catalog=cat,root=root,database=db,additional_ticks=budget)
            self.assertFalse(db.exists())

    def test_campaign_determinism_independent_databases(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root)
            a=search(catalog=cat,root=root,database=root/'a.sqlite',additional_ticks=20,islands=3)
            b=search(catalog=cat,root=root,database=root/'b.sqlite',additional_ticks=20,islands=3)
            self.assertEqual(a,b)

    def test_partition_disjoint(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root)
            ev,_=Evaluator.discover(cat,root)
            g=ev.groups
            self.assertFalse(set(g['train'])&set(g['holdout']))
            self.assertFalse(set(g['validation'])&set(g['holdout']))

    def test_scores_finite_for_safe_program(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root)
            ev,_=Evaluator.discover(cat,root)
            score,groups=ev.score(ev.train,(2.,4.,.2))
            self.assertTrue(math.isfinite(score))
            self.assertEqual(set(groups),set(ev.groups['train']))

if __name__ == '__main__':unittest.main()
