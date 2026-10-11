import copy
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from aegis_workpack.protocol import Invalid, canonical, cli, read_json, sha, valid_path, validate_contract, verify


def manifest(name='work.txt', body=b'valid result'):
    return {'schema':'aegis.workpack.v1','task_id':'pilot-001','domain':'code','authority':'branch_only',
            'objective':'Produce one independently inspectable artifact',
            'producer':{'agent':'agent-neutral'},
            'artifacts':[{'path':name,'sha256':hashlib.sha256(body).hexdigest()}],
            'checks':[{'id':'A1','kind':'sha256','artifact':name}]}


class WorkpackTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root=Path(self.tmp.name)
        self.root.joinpath('work.txt').write_bytes(b'valid result')
        self.good=manifest()

    def status(self, data=None):
        return verify(self.root,data or self.good)

    def test_integrity_pass_not_admitted(self):
        r=self.status()
        self.assertEqual(r['disposition'],'NOT_ADMITTED')
        self.assertEqual(r['local_result'],'LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED')
        self.assertIs(r['work_complete'],False)
        self.assertEqual(r['authority_effect'],'NONE')
        self.assertEqual(r['domain_quality'],'UNVERIFIED')
    def test_tampering_fail(self):
        self.root.joinpath('work.txt').write_text('malicious edit')
        self.assertEqual(self.status()['artifact_integrity'],'FAIL')
    def test_missing_file_fail(self):
        self.root.joinpath('work.txt').unlink()
        self.assertEqual(self.status()['disposition'],'NOT_ADMITTED')
    def test_symlink_fail(self):
        outside=self.root/'outside';outside.write_bytes(b'valid result')
        self.root.joinpath('work.txt').unlink();self.root.joinpath('work.txt').symlink_to(outside)
        self.assertIn(self.status()['artifacts'][0]['reason'], {'SYMLINK_FORBIDDEN', 'UNSAFE_OR_MISSING_ARTIFACT'})
    def test_parent_symlink_fail(self):
        data=manifest('sub/work.txt');(self.root/'sub').symlink_to(self.root)
        self.assertEqual(self.status(data)['disposition'],'NOT_ADMITTED')
    def test_traversal_fail(self):
        for name in ['../x','a/../../b','/etc/passwd','a//b','a\\b','.','a/./b']:
            with self.subTest(name=name):
                d=manifest(name);self.assertEqual(self.status(d)['disposition'],'NOT_ADMITTED')
    def test_invalid_manifest_cli_returns_receipt_not_exception(self):
        from aegis_workpack.protocol import cli
        import contextlib
        import io
        (self.root / 'manifest.json').write_text('{not-json')
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            code = cli([str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(captured.getvalue())['disposition'], 'NOT_ADMITTED')

    def test_invalid_utf8_manifest_cli_fails_closed(self):
        from aegis_workpack.protocol import cli
        import contextlib
        import io
        (self.root / 'manifest.json').write_bytes(b'\xff')
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            code = cli([str(self.root)])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(captured.getvalue())['disposition'], 'NOT_ADMITTED')

    def test_manifest_symlink_parent_fails(self):
        from aegis_workpack.protocol import cli
        import contextlib
        import io
        outside = self.root / 'manifest.json'
        outside.write_text(json.dumps(self.good))
        (self.root / 'sub').symlink_to(self.root)
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            exit_code = cli([str(self.root), '--manifest', 'sub/manifest.json'])
        self.assertEqual(exit_code, 1)
        self.assertEqual(json.loads(buf.getvalue())['disposition'], 'NOT_ADMITTED')

    def test_regular_nested_artifact_works(self):
        (self.root/'nested').mkdir()
        (self.root/'nested'/'result.txt').write_bytes(b'valid result')
        d=manifest('nested/result.txt')
        self.assertEqual(self.status(d)['artifact_integrity'],'PASS')

    def test_duplicate_artifact_fails(self):
        d=copy.deepcopy(self.good);d['artifacts'].append(d['artifacts'][0]);self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_duplicate_check_fails(self):
        d=copy.deepcopy(self.good);d['checks'].append(d['checks'][0]);self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_undeclared_check_fails(self):
        d=copy.deepcopy(self.good);d['checks'][0]['artifact']='invisible';self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_unknown_check_fails(self):
        d=copy.deepcopy(self.good);d['checks'][0]['kind']='run_shell';self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_unknown_authority_fails(self):
        d=copy.deepcopy(self.good);d['authority']='root';self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_unsupported_domain_fails(self):
        d=copy.deepcopy(self.good);d['domain']='superintelligence';self.assertEqual(self.status(d)['contract'],'INVALID')
    def test_all_six_domains_integrity(self):
        for domain in ['code','science','data','operations','design','writing']:
            d=copy.deepcopy(self.good);d['domain']=domain
            self.assertEqual(self.status(d)['artifact_integrity'],'PASS')
    def test_operator_only_still_no_authority(self):
        d=copy.deepcopy(self.good);d['authority']='operator_required'
        self.assertEqual(self.status(d)['authority_effect'],'NONE')
    def test_reviewer_never_claimed_authenticated(self):
        d=copy.deepcopy(self.good);d['checks'].append({'id':'A2','kind':'independent_review','artifact':'work.txt'})
        r=self.status(d)
        self.assertEqual(r['checks'][1]['result'],'BLOCKED')
        self.assertEqual(r['disposition'],'NOT_ADMITTED')
    def test_text_contains_structural_only(self):
        d=copy.deepcopy(self.good);d['checks'].append({'id':'A2','kind':'text_contains','artifact':'work.txt','value':'valid'})
        r=self.status(d);self.assertEqual(r['checks'][1]['result'],'PASS')
        self.assertEqual(r['domain_quality'],'UNVERIFIED')
    def test_text_absence_fails(self):
        d=copy.deepcopy(self.good);d['checks'].append({'id':'A2','kind':'text_contains','artifact':'work.txt','value':'impossible'})
        self.assertEqual(self.status(d)['checks'][1]['result'],'FAIL')
    def test_json_keys(self):
        value=b'{"result":3,"source":"grounded"}'
        (self.root/'good.json').write_bytes(value)
        d=manifest('good.json',value);d['checks'].append({'id':'A2','kind':'json_keys','artifact':'good.json','keys':['result','source']})
        self.assertEqual(self.status(d)['checks'][1]['result'],'PASS')
    def test_json_nonfinite_extensions_fail_structural_check(self):
        for literal in (b'NaN', b'Infinity', b'-Infinity'):
            with self.subTest(literal=literal):
                raw = b'{"value":' + literal + b'}'
                (self.root / 'bad.json').write_bytes(raw)
                data = manifest('bad.json', raw)
                data['checks'].append({'id':'A2','kind':'json_keys',
                                       'artifact':'bad.json','keys':['value']})
                out = self.status(data)
                self.assertEqual(out['checks'][1]['result'], 'FAIL')
                self.assertEqual(out['checks'][1]['reason'], 'NONFINITE_JSON')
                self.assertEqual(out['local_result'], 'LOCAL_CHECKS_FAILED')

    def test_json_float_overflow_fail_structural_check(self):
        raw = b'{"value":1e400}'
        (self.root / 'bad.json').write_bytes(raw)
        data = manifest('bad.json', raw)
        data['checks'].append({'id':'A2','kind':'json_keys',
                               'artifact':'bad.json','keys':['value']})
        self.assertEqual(self.status(data)['checks'][1]['reason'], 'NONFINITE_JSON')

    def test_json_finite_float_still_valid(self):
        raw = b'{"value":1.25e-3,"negative":-5.5}'
        (self.root / 'good.json').write_bytes(raw)
        data = manifest('good.json', raw)
        data['checks'].append({'id':'A2','kind':'json_keys',
                               'artifact':'good.json','keys':['value','negative']})
        self.assertEqual(self.status(data)['checks'][1]['result'], 'PASS')

    def test_json_helper_rejects_exponent_overflow(self):
        (self.root / 'bad.json').write_bytes(b'{"value":1e400}')
        with self.assertRaisesRegex(Invalid, 'NONFINITE_JSON'):
            read_json(self.root / 'bad.json')

    def test_cli_rejects_exponent_overflow_in_manifest(self):
        import contextlib, io
        (self.root / 'manifest.json').write_bytes(b'{"schema":"aegis.workpack.v1","x":1e400}')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = cli([str(self.root), '--integrity-only'])
        self.assertEqual(status, 1)
        self.assertEqual(json.loads(output.getvalue())['reason'], 'NONFINITE_JSON')

    def test_json_duplicate_payload_fails(self):
        value=b'{"result":3,"result":4}'
        (self.root/'good.json').write_bytes(value)
        d=manifest('good.json',value);d['checks'].append({'id':'A2','kind':'json_keys','artifact':'good.json','keys':['result']})
        self.assertEqual(self.status(d)['checks'][1]['result'],'FAIL')
    def test_csv_valid(self):
        value=b'name,score\na,1\nb,2\n'
        (self.root/'data.csv').write_bytes(value)
        d=manifest('data.csv',value);d['domain']='data';d['checks'].append({'id':'A2','kind':'csv_columns','artifact':'data.csv','columns':['name','score'],'min_rows':2})
        self.assertEqual(self.status(d)['checks'][1]['result'],'PASS')
    def test_csv_missing_column_fails(self):
        value=b'name\na\n';(self.root/'data.csv').write_bytes(value)
        d=manifest('data.csv',value);d['checks'].append({'id':'A2','kind':'csv_columns','artifact':'data.csv','columns':['score'],'min_rows':1})
        self.assertEqual(self.status(d)['checks'][1]['result'],'FAIL')
    def test_csv_ragged_rows_fail(self):
        value=b'a,b\n1\n';(self.root/'data.csv').write_bytes(value)
        d=manifest('data.csv',value);d['checks'].append({'id':'A2','kind':'csv_columns','artifact':'data.csv','columns':['a'],'min_rows':1})
        self.assertEqual(self.status(d)['checks'][1]['result'],'FAIL')
    def test_csv_duplicate_header_fail(self):
        value=b'a,a\n1,2\n';(self.root/'data.csv').write_bytes(value)
        d=manifest('data.csv',value);d['checks'].append({'id':'A2','kind':'csv_columns','artifact':'data.csv','columns':['a'],'min_rows':1})
        self.assertEqual(self.status(d)['checks'][1]['result'],'FAIL')
    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                         "POSIX no-follow directory traversal required")
    def test_read_json_parent_symlink_is_rejected(self):
        # Previous helper resolved source.parent before applying O_NOFOLLOW.
        # This fixture proves it can read data outside the requested parent.
        (self.root/'sensitive').mkdir()
        (self.root/'sensitive'/'private.json').write_text('{"secret":"outside"}')
        (self.root/'safe').mkdir()
        (self.root/'safe'/'link').symlink_to(self.root/'sensitive', target_is_directory=True)
        with self.assertRaisesRegex(Invalid, "UNSAFE_OR_MISSING_ARTIFACT"):
            read_json(self.root/'safe'/'link'/'private.json')

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                         "POSIX no-follow directory traversal required")
    def test_read_json_leaf_symlink_is_rejected(self):
        (self.root/'private.json').write_text('{"secret":"outside"}')
        (self.root/'alias.json').symlink_to(self.root/'private.json')
        with self.assertRaisesRegex(Invalid, "UNSAFE_OR_MISSING_ARTIFACT"):
            read_json(self.root/'alias.json')

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                         "POSIX no-follow directory traversal required")
    def test_read_json_rejects_dotdot_without_normalizing(self):
        (self.root/'valid.json').write_text('{"ok":true}')
        with self.assertRaisesRegex(Invalid, "JSON_PATH_TRAVERSAL"):
            read_json(self.root/'safe'/'..'/'valid.json')

    def test_read_json_allows_regular_nested_file(self):
        nested=self.root/'ordinary'
        nested.mkdir()
        (nested/'report.json').write_text('{"ok":true,"n":123}')
        self.assertEqual(read_json(nested/'report.json'), {'ok':True,'n':123})

    def test_strict_duplicate_manifest_keys(self):
        p=self.root/'bad.json';p.write_text('{"schema":"x","schema":"y"}')
        with self.assertRaises(Invalid):read_json(p)
    def test_canonical_is_order_independent(self):
        self.assertEqual(sha(canonical({'a':1,'b':2})),sha(canonical({'b':2,'a':1})))
    def test_nonfinite_json_rejected(self):
        p=self.root/'bad.json';p.write_text('{"x":NaN}')
        with self.assertRaises(Invalid):read_json(p)
    def test_artifact_oversize_fails(self):
        (self.root/'work.txt').write_bytes(b'x'*(8*1024*1024+1))
        self.assertEqual(self.status()['artifact_integrity'],'FAIL')
    def test_manifest_oversize_rejected(self):
        p=self.root/'oversized.json';p.write_bytes(b'a'*(256*1024+1))
        with self.assertRaises(Invalid):read_json(p)
    def test_no_shell_side_effects(self):
        p=self.root/'NO_RUN';d=copy.deepcopy(self.good);d['checks'][0]['kind']='os.system'
        verify(self.root,d)
        self.assertFalse(p.exists())
    def test_read_only_does_not_write(self):
        before={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        verify(self.root,self.good)
        after={p.name:p.read_bytes() for p in self.root.iterdir() if p.is_file()}
        self.assertEqual(before,after)
    def test_invalid_agent_identity(self):
        d=copy.deepcopy(self.good);d['producer']['agent']=''
        self.assertEqual(self.status(d)['contract'],'INVALID')

    @unittest.skipUnless(hasattr(os, "mkfifo") and os.name == "posix", "POSIX FIFO only")
    def test_fifo_artifact_never_hangs_and_is_rejected(self):
        import subprocess
        (self.root / 'work.txt').unlink()
        os.mkfifo(self.root / 'work.txt')
        script = ("import json,sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[1])) + ");"
                  "from aegis_workpack.protocol import verify;"
                  "report=verify(" + repr(str(self.root)) + "," + repr(self.good) + ");"
                  "print(json.dumps(report))")
        child = subprocess.run([sys.executable, '-S', '-c', script],
                               capture_output=True, text=True, timeout=2)
        self.assertEqual(child.returncode, 0, child.stderr)
        out = json.loads(child.stdout)
        self.assertEqual(out['artifact_integrity'], 'FAIL')
        self.assertEqual(out['disposition'], 'NOT_ADMITTED')

    @unittest.skipUnless(hasattr(os, "mkfifo") and os.name == "posix", "POSIX FIFO only")
    def test_fifo_manifest_never_hangs_and_is_rejected(self):
        import subprocess
        os.mkfifo(self.root / 'manifest.json')
        child = subprocess.run([sys.executable, '-S', '-m', 'aegis_workpack.protocol', str(self.root)],
                               cwd=Path(__file__).resolve().parents[1],
                               capture_output=True, text=True, timeout=2)
        self.assertEqual(child.returncode, 1, child.stderr)
        self.assertEqual(json.loads(child.stdout)['disposition'], 'NOT_ADMITTED')

    @unittest.skipUnless(hasattr(os, "mkfifo") and os.name == "posix", "POSIX FIFO only")
    def test_fifo_read_json_helper_never_hangs(self):
        import subprocess
        os.mkfifo(self.root / 'report.json')
        script = ("import sys;sys.path.insert(0," + repr(str(Path(__file__).resolve().parents[1])) + ");"
                  "from aegis_workpack.protocol import read_json;"
                  "read_json(" + repr(str(self.root / 'report.json')) + ")")
        child = subprocess.run([sys.executable, '-S', '-c', script],
                               capture_output=True, text=True, timeout=2)
        self.assertNotEqual(child.returncode, 0)
        self.assertIn('ARTIFACT_NOT_REGULAR_FILE', child.stderr)

if __name__=='__main__':unittest.main()
