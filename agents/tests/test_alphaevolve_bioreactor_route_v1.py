"""Ensure existing frontier actually dispatches bioreactor science without admission."""
import hashlib
import sqlite3
import tempfile
import unittest
from pathlib import Path
from agents.alphaevolve_frontier_router_v1 import route_and_execute_bioreactor

class JoinedFrontierTests(unittest.TestCase):
    def test_bioreactor_is_part_of_frontier_without_admission(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);p=root/'bioreactor_1.csv'
            p.write_text(''.join(f'{i},{30+(i%5)*.1+i/20}\n' for i in range(200)))
            h=hashlib.sha256(p.read_bytes()).hexdigest()
            db=root/'corpus.sqlite';c=sqlite3.connect(db)
            c.executescript('''CREATE TABLE assets(digest TEXT,relpath TEXT,science_state TEXT,format TEXT,category TEXT,bytes INTEGER);
                           CREATE TABLE coverage(state TEXT);''')
            c.execute('INSERT INTO assets VALUES(?,?,?,?,?,?)',(h,p.name,'CSV_EVALUATOR_PENDING','.csv','STRUCTURED_DATA',p.stat().st_size))
            c.execute('INSERT INTO coverage VALUES(?)',('UNIQUE_REPRESENTATION_EVOLVED',))
            c.commit();c.close()
            x=route_and_execute_bioreactor(db,root)
            self.assertEqual(x['unique_assets_assigned'],1)
            self.assertEqual(x['bioreactor_cohort']['evaluated'],1)
            self.assertEqual(x['scientific_admission'],'DENIED')
            self.assertEqual(x['bioreactor_cohort']['scientific_admission'],'DENIED')

if __name__=='__main__':unittest.main()
