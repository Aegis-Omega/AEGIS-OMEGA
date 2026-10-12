"""Source-bound, automatic corpus dispatch; no manual dataset name or admission."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_frontier_router_v1 import autonomous_dispatch

def fixture(root,entries):
    db=root/'corpus.sqlite'
    c=sqlite3.connect(db)
    c.execute('''CREATE TABLE assets(digest TEXT PRIMARY KEY, relpath TEXT, bytes INTEGER,
                 format TEXT, category TEXT, science_state TEXT)''')
    for name,ext,content in entries:
        p=root/name
        p.write_bytes(content)
        c.execute('INSERT INTO assets VALUES(?,?,?,?,?,?)',
                  (hashlib.sha256(content).hexdigest(),name,len(content),ext,'SCIENCE','PENDING'))
    c.commit();c.close()
    return db

class AutoDispatchTests(unittest.TestCase):
    def test_all_assets_registered_and_resume_not_reexecuted(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            raw=('time_fs,coherence_l1\n'+''.join(
                 f'{i},{1/(1+i*.005):.8f}\n' for i in range(220))).encode()
            cat=fixture(root,[('unrelated.csv','.csv',raw),
                              ('proof.json','.json',b'{"claimed":false}')])
            st=root/'state.sqlite'
            r=autonomous_dispatch(cat,root,st,budget=1)
            self.assertEqual(r['unique_assets_accounted'],2)
            self.assertEqual(r['science_states']['EVALUATED_OBSERVATIONAL'],1)
            self.assertEqual(r['science_states']['SCIENCE_EVALUATOR_UNAVAILABLE'],1)
            self.assertEqual(r['new_scientific_candidate_trials'],3)
            self.assertEqual(r['admission'],'DENIED')
            again=autonomous_dispatch(cat,root,st,budget=1)
            self.assertEqual(again['new_evaluation_attempts'],0)
            self.assertEqual(again['total_program_trials'],3)

    def test_unnamed_sensor_series_auto_discovered(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            data=''.join(f'{i},{30+i*.031+(i%7)*.2}\n' for i in range(210)).encode()
            db=fixture(root,[('anonymous.csv','.csv',data)])
            r=autonomous_dispatch(db,root,root/'state.sqlite')
            self.assertEqual(r['science_states']['EVALUATED_OBSERVATIONAL'],1)
            self.assertGreaterEqual(r['total_program_trials'],12)

    def test_changed_source_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cat=fixture(root,[('research.csv','.csv',b'time_fs,quality\n0,1\n')])
            (root/'research.csv').write_text('changed')
            r=autonomous_dispatch(cat,root,root/'state.sqlite')
            self.assertEqual(r['science_states']['BLOCKED_SOURCE_OR_SCHEMA'],1)
            self.assertEqual(r['total_program_trials'],0)

    def test_catalog_rebind_is_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cat=fixture(root,[('a.json','.json',b'{}')])
            st=root/'s.sqlite'
            autonomous_dispatch(cat,root,st)
            (root/'b.json').write_text('{"x":1}')
            c=sqlite3.connect(cat)
            raw=(root/'b.json').read_bytes()
            c.execute('INSERT INTO assets VALUES(?,?,?,?,?,?)',
                      (hashlib.sha256(raw).hexdigest(),'b.json',len(raw),'.json','SCIENCE','PENDING'))
            c.commit();c.close()
            with self.assertRaisesRegex(ValueError,'SOURCE_CATALOG_REBIND_DENIED'):
                autonomous_dispatch(cat,root,st)

    def test_budget_input_mutation_and_traversal_denied(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)
            cat=fixture(root,[('a.csv','.csv',b'1,2\n')])
            for budget in (0,2001,True):
                with self.assertRaisesRegex(ValueError,'INVALID_BATCH_BUDGET'):
                    autonomous_dispatch(cat,root,root/'s.sqlite',budget=budget)
            with self.assertRaisesRegex(ValueError,'INPUT_MUTATION_DENIED'):
                autonomous_dispatch(cat,root,cat)
            c=sqlite3.connect(cat);c.execute("UPDATE assets SET relpath='../a.csv'");c.commit();c.close()
            r=autonomous_dispatch(cat,root,root/'safe.sqlite')
            self.assertEqual(r['science_states']['BLOCKED_SOURCE_OR_SCHEMA'],1)

if __name__=='__main__':unittest.main()
