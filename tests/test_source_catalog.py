import importlib.util
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec=importlib.util.spec_from_file_location('catalog',Path(__file__).resolve().parents[1]/'scripts/source_catalog.py')
c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)

class CatalogTests(unittest.TestCase):
    def manifest(self, **changes):
        source={'repository':'owner/one','revision':'a'*40,'ref':'main','visibility':'public','truncated':False,
                'assets':[{'path':'src/shared.ts','blob_sha':'b'*40}]}
        source.update(changes)
        return {'schema_version':1,'observed_at':'2026-10-16','sources':[source]}

    def test_cross_repo_identity_and_read_only_search(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d); x=self.manifest(); second=dict(x['sources'][0],repository='owner/two');x['sources'].append(second)
            (p/'in.json').write_text(json.dumps(x))
            self.assertEqual(c.build(p/'in.json',p/'db'),2)
            self.assertEqual(len(c.search(p/'db','shared.ts')),2)
            self.assertEqual(c.search(p/'db',"' OR 1=1 --"),[])
            with sqlite3.connect(p/'db') as db:
                self.assertEqual(db.execute('SELECT count(DISTINCT blob_sha) FROM source_assets').fetchone()[0],1)

    def test_rejects_private_incomplete_unsafe_and_duplicate_without_clobber(self):
        for change in [{'visibility':'private'},{'truncated':True},
                       {'assets':[{'path':'../escape','blob_sha':'b'*40}]},
                       {'revision':'main'},
                       {'assets':[{'path':'x','blob_sha':'b'*40}]*2}]:
            with self.subTest(change=change),tempfile.TemporaryDirectory() as d:
                p=Path(d); (p/'in.json').write_text(json.dumps(self.manifest(**change)));(p/'db').write_bytes(b'previous')
                with self.assertRaises((ValueError,sqlite3.IntegrityError)): c.build(p/'in.json',p/'db')
                self.assertEqual((p/'db').read_bytes(),b'previous')

    def test_cannot_replace_manifest(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'in.json';p.write_text(json.dumps(self.manifest()))
            with self.assertRaises(ValueError):c.build(p,p)

if __name__=='__main__':unittest.main()
