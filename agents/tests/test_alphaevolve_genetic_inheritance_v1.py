"""AEGIS genetic reproduction falsifiers + integration with existing islands."""
import copy
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from agents.alphaevolve_genetic_inheritance_v1 import (
    founder, phenotype, reproduce, validate, genome_digest,
)
from agents.alphaevolve_islands_v1 import program, search, finalize
from agents.tests.test_alphaevolve_islands_v1 import synthetic


class DiploidTests(unittest.TestCase):
    def test_both_zygote_karyotypes(self):
        mom=founder(program(8,28,0.2),sex='XX')
        dad=founder(program(2,4,0.1),sex='XY')
        found=set()
        for i in range(80):
            child,trace=reproduce(mom,dad,seed=i)
            self.assertTrue(validate(child))
            self.assertEqual(child['sex_chromosomes'][0]['kind'],'X')
            self.assertIn(child['sex_chromosomes'][1]['kind'],('X','Y'))
            self.assertEqual(trace['sex_chromosomes'],[x['kind'] for x in child['sex_chromosomes']])
            self.assertTrue(0<=phenotype(child)['shrink']<=1)
            found.add(''.join(x['kind'] for x in child['sex_chromosomes']))
        self.assertEqual(found,{'XX','XY'})

    def test_y_only_from_paternal_side(self):
        mom=founder(program(4,0,0),sex='XX')
        dad=founder(program(5,10,0),sex='XY')
        dad['sex_chromosomes'][1]['regulator']=0.5
        for i in range(100):
            child,_=reproduce(mom,dad,seed=i)
            if child['sex_chromosomes'][1]['kind']=='Y':
                self.assertIn(child['sex_chromosomes'][1]['regulator'],(.5,.4,.48,.52,.6))
            self.assertEqual(child['sex_chromosomes'][0]['kind'],'X')

    def test_recessive_gene_retention(self):
        mom=founder(program(4,8,.2),sex='XX')
        mom['autosomes'][1][0]=[12.,0.]
        self.assertEqual(phenotype(mom)['alpha'],4.)
        self.assertNotEqual(mom['autosomes'][0][0],mom['autosomes'][1][0])

    def test_invalid_karyotype_rejected(self):
        bad=founder(program(1,2,.3))
        bad['sex_chromosomes'][0]['kind']='Y'
        with self.assertRaisesRegex(ValueError,'GENOME_XY_INHERITANCE_INVALID'):
            validate(bad)

    def test_malformed_genome_and_nan_rejected(self):
        g=founder(program(1,2,.3))
        for bad in (float('nan'),float('inf'),True,100):
            x=copy.deepcopy(g);x['autosomes'][0][0][0]=bad
            with self.assertRaises(ValueError):validate(x)

    def test_wrong_parents_fail_closed(self):
        a=founder(program(1,2,.3),sex='XY')
        b=founder(program(1,2,.3),sex='XX')
        with self.assertRaisesRegex(ValueError,'GENOME_PARENTAL_KARYOTYPE_INVALID'):
            reproduce(a,b,seed=1)

    def test_deterministic_genomic_replay(self):
        mom=founder(program(1,2,.3),sex='XX')
        dad=founder(program(3,5,.4),sex='XY')
        a=reproduce(mom,dad,seed=42)
        b=reproduce(mom,dad,seed=42)
        self.assertEqual(a,b)
        self.assertEqual(genome_digest(a[0]),genome_digest(b[0]))

    def test_integration_genetic_resumption_and_holdout_freeze(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root);db=root/'evolve.sqlite'
            a=search(catalog=cat,root=root,database=db,additional_ticks=30,islands=4,inheritance_mode='diploid_xy_v1')
            b=search(catalog=cat,root=root,database=db,additional_ticks=40,islands=4,inheritance_mode='diploid_xy_v1')
            self.assertEqual(b['ticks_proposed'],70)
            self.assertEqual(b['genetic_trace_count'],70)
            self.assertGreater(b['genetic_offspring'],0)
            self.assertEqual(b['inheritance_mode'],'diploid_xy_v1')
            c=sqlite3.connect(db)
            rows=c.execute('SELECT genome,genome_digest,inheritance_trace FROM breeding').fetchall()
            self.assertEqual(len(rows),70)
            for raw,h,trace in rows:
                self.assertEqual(genome_digest(json.loads(raw)),h)
                self.assertIn('generation_kind',json.loads(trace))
            c.close()
            with self.assertRaisesRegex(ValueError,'CAMPAIGN_SOURCE_OR_CONFIG_DRIFT'):
                search(catalog=cat,root=root,database=db,additional_ticks=1,inheritance_mode='asexual_v1')
            result=finalize(catalog=cat,root=root,database=db)
            self.assertEqual(result['scientific_admission'],'DENIED')
            with self.assertRaisesRegex(ValueError,'CAMPAIGN_ALREADY_FROZEN'):
                search(catalog=cat,root=root,database=db,additional_ticks=1,inheritance_mode='diploid_xy_v1')

    def test_two_databases_same_genetic_history(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);cat=synthetic(root)
            a=search(catalog=cat,root=root,database=root/'a.sqlite',additional_ticks=32,islands=4,inheritance_mode='diploid_xy_v1')
            b=search(catalog=cat,root=root,database=root/'b.sqlite',additional_ticks=32,islands=4,inheritance_mode='diploid_xy_v1')
            self.assertEqual(a,b)
            l=[]
            for name in ('a.sqlite','b.sqlite'):
                conn=sqlite3.connect(root/name)
                l.append(conn.execute('SELECT genome_digest,inheritance_trace FROM breeding ORDER BY tick').fetchall())
                conn.close()
            self.assertEqual(*l)


if __name__=='__main__':unittest.main()
