"""Adversarial and end-to-end checks for corpus-native autonomous evolution."""
import csv
import hashlib
import math
import os
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from agents.alphaevolve_corpus_discovery_v1 import (
    safe_path, inspect_index, _physical_project, _series_loss, _split,
    _detect_simplex, _extract_simplex, run, evolve_family, dig,
)

HEAD=("time", "A", "B", "C", "classical_A")


def sample_csv(i, scramble=False):
    rows=[]
    for t in range(110):
        v=0.2+0.12*math.sin(t/19+i/12)
        w=0.3+0.09*math.sin(t/25+i/15)
        rows.append([t*0.1,v,w,1-v-w,0.0])
    if scramble: rows[20],rows[21]=rows[21],rows[20]
    import io
    f=io.StringIO();writer=csv.writer(f);writer.writerow(HEAD);writer.writerows(rows)
    return f.getvalue().encode()


def prepare(tmp:Path, n=12):
    root=tmp/'corpus'; root.mkdir(); path=root/'idx.sqlite'
    db=sqlite3.connect(path)
    db.executescript('''CREATE TABLE objects (member TEXT,extracted_path TEXT,sha256 TEXT,bytes INTEGER,category TEXT,format TEXT,status TEXT);''')
    for i in range(n):
        name=f"experiment_gamma_{i//2}.csv"
        b=sample_csv(i)
        p=root/f"series_{i}.csv";p.write_bytes(b)
        db.execute("INSERT INTO objects VALUES (?,?,?,?,?,?,?)",(name,str(p.relative_to(root)),hashlib.sha256(b).hexdigest(),len(b),"STRUCTURED_DATA",".csv","IMPORTED_BYTES_VERIFIED"))
    db.commit();db.close();return root,path


class DiscoveryTests(unittest.TestCase):
    def test_source_path_traversal_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            for rel in ("../escape.csv","/tmp/escape.csv"):
                with self.assertRaisesRegex(ValueError,"CATALOG_PATH"):
                    safe_path(root,rel)

    def test_source_symlink_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d); (root/'real').write_text('text');(root/'linked').symlink_to(root/'real')
            with self.assertRaisesRegex(ValueError,"CATALOG_SYMLINK_REJECTED"):
                safe_path(root,'linked')

    def test_hash_mismatch_fail_closed(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d))
            (root/'series_3.csv').write_bytes(b'forged')
            with self.assertRaisesRegex(ValueError,"SOURCE_BYTES_HASH_MISMATCH"):
                inspect_index(db,root)

    def test_auto_discovers_family_without_filename_selection(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d)); result=inspect_index(db,root)
            family=result['families'][0]
            self.assertEqual(family['candidate_kind'],'SIMPLEX_DYNAMICS_FORECAST')
            self.assertEqual(family['file_count'],12)

    def test_evolution_runs_no_promotion(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d)); result=run(catalog=db,root=root,generations=12)
            self.assertEqual(result['production_admission'],'DENIED')
            self.assertEqual(len(result['experiments']),1)
            e=result['experiments'][0]
            self.assertEqual(e['admission'],'DENIED')
            self.assertEqual(e['holdout_group_count'],2)
            self.assertFalse(e['independent_group_threshold_for_issue758_met'])
            self.assertEqual(e['receipt_hash'],dig({k:v for k,v in e.items() if k!='receipt_hash'}))

    def test_fixed_split_independent_of_outcomes(self):
        labels=[f'gamma={i}' for i in range(9)]
        self.assertEqual(_split(labels),_split(labels[::-1]))
        x=_split(labels)
        self.assertFalse(set(x['train'])&set(x['validation']))
        self.assertFalse(set(x['train'])&set(x['holdout']))
        self.assertFalse(set(x['validation'])&set(x['holdout']))

    def test_simplex_projection(self):
        x=np.array([[-1.,0.1,0.3],[0.,0.,0.],[1.,4.,-1.]])
        y=_physical_project(x)
        np.testing.assert_allclose(y.sum(axis=1),1.0)
        self.assertTrue((y>=0).all())

    def test_no_future_label_leak(self):
        x=np.column_stack([np.linspace(0,1,100),np.linspace(1,0,100)])
        a=_series_loss(x,1.0,0.0)
        mutated=x.copy();mutated[-8:]=mutated[-8:][:,::-1]
        # Last holdout labels can affect loss, not model selection during train.
        self.assertNotEqual(a,_series_loss(mutated,1.0,0.0))

    def test_shuffled_time_rejected(self):
        rows=list(csv.reader(sample_csv(0,scramble=True).decode().splitlines()))[1:]
        item={'rows':rows,'member':'synthetic','source_sha256':'a'*64}
        self.assertIsNone(_detect_simplex(HEAD,[item]*12))

    def test_nonexistent_domain_unmeasured(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d))
            r=run(catalog=db,root=root,generations=2)
            self.assertIn('DOMAIN_EVALUATORS',r['unevaluated_domains'])

    def test_deterministic_replay(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d))
            self.assertEqual(run(catalog=db,root=root,generations=8),
                             run(catalog=db,root=root,generations=8))

    def test_invalid_generation_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root,db=prepare(Path(d))
            with self.assertRaisesRegex(ValueError,'EVOLUTION_BUDGET_INVALID'):
                run(catalog=db,root=root,generations=0)

if __name__=='__main__':unittest.main()
