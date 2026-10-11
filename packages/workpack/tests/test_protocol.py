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

    def test_windows_drive_and_ads_paths_rejected_portably(self):
        from pathlib import PureWindowsPath
        self.assertEqual(str(PureWindowsPath('C:/Safe')/'D:/secret.txt'),
                         'D:\\secret.txt')
        for name in ('C:/Windows/System32/config/SAM', 'D:secret.txt',
                     'payload.txt:secret', 'nested/report.json::$DATA'):
            with self.subTest(name=name):
                self.assertFalse(valid_path(name))
                self.assertEqual(self.status(manifest(name)).get('contract'), 'INVALID')

    def test_windows_devices_and_file_aliases_rejected_portably(self):
        for name in ('CON', 'con.txt', 'folder/PRN.log', 'assets/NUL.json',
                     'AUX', 'COM1', 'COM9.txt', 'LPT1.log', 'CONIN$',
                     'CONOUT$', 'COM¹.txt', 'LPT².csv', 'folder/nul .txt'):
            with self.subTest(name=name):
                self.assertFalse(valid_path(name))

    def test_windows_invalid_chars_and_trailing_aliases_rejected(self):
        for name in ('part?.json', 'wild*card.txt', 'a|b', 'note<1>.txt',
                     'a"b', 'report.', 'report ', 'folder/next. ', 'x\x7f.txt'):
            with self.subTest(name=name):
                self.assertFalse(valid_path(name))

    def test_benign_relative_names_remain_supported(self):
        for name in ('nested/report.json', '.gitignore', 'report v2.txt',
                     'science/méthode.csv', 'data/output_001.json', 'dir/a.b.txt'):
            with self.subTest(name=name):
                self.assertTrue(valid_path(name))

    def test_cli_manifest_alternate_stream_syntax_rejected(self):
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()) as captured:
            code = cli([str(self.root), '--manifest', 'data.json:$DATA'])
        self.assertEqual(code, 1)
        receipt = json.loads(captured.getvalue())
        self.assertEqual(receipt['disposition'], 'NOT_ADMITTED')
        self.assertEqual(receipt['reason'], 'MANIFEST_PATH_INVALID')
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

    def test_extreme_json_depth_rejected_without_uncaught_exception(self):
        import contextlib, io
        depth=30000
        (self.root/'manifest.json').write_text('{"schema":"aegis.workpack.v1","x":'+'['*depth+'0'+']'*depth+'}')
        with self.assertRaisesRegex(Invalid,"JSON_DEPTH_LIMIT"):
            read_json(self.root/'manifest.json')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code=cli([str(self.root)])
        self.assertEqual(code,1)
        self.assertEqual(json.loads(output.getvalue())['reason'],'JSON_DEPTH_LIMIT')

    def test_huge_json_integer_rejected_without_uncaught_exception(self):
        import contextlib, io
        (self.root/'manifest.json').write_text('{"number":'+'9'*5000+'}')
        with self.assertRaisesRegex(Invalid,'JSON_INTEGER_TOO_LONG'):
            read_json(self.root/'manifest.json')
        with contextlib.redirect_stdout(io.StringIO()) as output:
            code=cli([str(self.root)])
        self.assertEqual(code,1)
        self.assertEqual(json.loads(output.getvalue())['reason'],'JSON_INTEGER_TOO_LONG')

    def test_cyclic_direct_manifest_is_bounded_and_not_admitted(self):
        d=copy.deepcopy(self.good)
        d['extension']=d
        r=verify(self.root,d)
        self.assertEqual(r['disposition'],'NOT_ADMITTED')
        self.assertEqual(r['reason'],'JSON_CYCLE_OR_SHARED_CONTAINER')

    def test_deep_direct_manifest_does_not_overflow_serializer(self):
        d=copy.deepcopy(self.good)
        nested=[]; d['extension']=nested
        for _ in range(200):
            next_value=[]; nested.append(next_value); nested=next_value
        r=verify(self.root,d)
        self.assertEqual(r['reason'],'JSON_DEPTH_LIMIT')
        self.assertEqual(r['disposition'],'NOT_ADMITTED')

    def test_brackets_inside_quoted_json_strings_are_not_counted(self):
        from aegis_workpack.protocol import _strict_json_loads
        s=json.dumps({'display':'['*150+'escaped quote: \" and a brace: {'})
        result=_strict_json_loads(s)
        self.assertEqual(result['display'].count('['),150)

    def test_nested_json_artifact_fails_structurally_without_crash(self):
        from aegis_workpack.protocol import _strict_json_loads
        huge='{ "key":' + '['*250+'0'+']'*250 + '}'
        raw=huge.encode()
        (self.root/'deep.json').write_bytes(raw)
        d=manifest('deep.json',raw)
        d['checks'].append({'id':'A2','kind':'json_keys','artifact':'deep.json','keys':['key']})
        r=verify(self.root,d)
        self.assertEqual(r['checks'][1]['result'],'FAIL')
        self.assertEqual(r['checks'][1]['reason'],'JSON_DEPTH_LIMIT')

    def test_large_flat_json_artifact_rejected_by_node_budget(self):
        from aegis_workpack.protocol import MAX_JSON_NODES
        raw=json.dumps({'status':'ok','payload':[0]*(MAX_JSON_NODES+1)},
                       separators=(',',':')).encode()
        self.assertLess(len(raw),MAX_JSON_NODES*4)
        (self.root/'large.json').write_bytes(raw)
        d=manifest('large.json',raw)
        d['checks'].append({'id':'A2','kind':'json_keys','artifact':'large.json',
                            'keys':['status']})
        r=verify(self.root,d)
        self.assertEqual(r['artifact_integrity'],'PASS')
        self.assertEqual(r['checks'][1]['result'],'FAIL')
        self.assertEqual(r['checks'][1]['reason'],'JSON_NODE_LIMIT')
        self.assertEqual(r['local_result'],'LOCAL_CHECKS_FAILED')

    def test_read_json_rejects_oversized_node_graph_within_byte_cap(self):
        from aegis_workpack.protocol import MAX_JSON_NODES
        raw=json.dumps({'payload':[0]*(MAX_JSON_NODES+1)},
                       separators=(',',':')).encode()
        p=self.root/'many.json';p.write_bytes(raw)
        with self.assertRaisesRegex(Invalid,'JSON_NODE_LIMIT'):
            read_json(p)

    def test_comma_rich_string_is_not_mistaken_for_json_node_budget(self):
        from aegis_workpack.protocol import _strict_json_loads,MAX_JSON_NODES
        text='a,'*(MAX_JSON_NODES+1)
        data=_strict_json_loads(json.dumps({'message':text}))
        self.assertEqual(data['message'],text)

    def test_large_single_string_json_artifact_still_passes_structural_check(self):
        # JSON artifact limit is 8 MiB. Do not accidentally impose the much
        # smaller manifest limit on structural validation of document content.
        raw=json.dumps({'status':'ok','text':'x'*300000}).encode()
        (self.root/'long.json').write_bytes(raw)
        d=manifest('long.json',raw)
        d['checks'].append({'id':'A2','kind':'json_keys','artifact':'long.json',
                            'keys':['status','text']})
        r=verify(self.root,d)
        self.assertEqual(r['checks'][1]['result'],'PASS')
        self.assertEqual(r['local_result'],'LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED')

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                         "POSIX dirfd protection only")
    def test_receipt_export_refuses_leaf_symlink_without_changing_target(self):
        import contextlib,io
        outside = self.root / 'outside-secret.txt'
        outside.write_text('DO_NOT_MODIFY', encoding='utf-8')
        output = self.root / 'receipt.json'
        output.symlink_to(outside)
        (self.root / 'manifest.json').write_text(json.dumps(self.good))
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = cli([str(self.root), '--output', str(output)])
        self.assertEqual(code, 2)
        self.assertEqual(outside.read_text(), 'DO_NOT_MODIFY')
        self.assertEqual(json.loads(buf.getvalue())['output_status'], 'NOT_WRITTEN')
        self.assertEqual(json.loads(buf.getvalue())['disposition'], 'NOT_ADMITTED')

    @unittest.skipUnless(os.name == "posix" and hasattr(os, "O_NOFOLLOW"),
                         "POSIX dirfd protection only")
    def test_receipt_export_refuses_parent_symlink_without_changing_target(self):
        import contextlib,io
        outside_dir = self.root / 'outside';outside_dir.mkdir()
        sentinel = outside_dir / 'receipt.json'
        sentinel.write_text('DO_NOT_MODIFY')
        (self.root / 'redirect').symlink_to(outside_dir, target_is_directory=True)
        (self.root / 'manifest.json').write_text(json.dumps(self.good))
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = cli([str(self.root), '--output', str(self.root/'redirect'/'receipt.json')])
        self.assertEqual(code, 2)
        self.assertEqual(sentinel.read_text(), 'DO_NOT_MODIFY')
        self.assertEqual(json.loads(buf.getvalue())['output_status'], 'NOT_WRITTEN')

    def test_receipt_export_refuses_existing_manifest_and_artifact(self):
        import contextlib,io
        (self.root / 'manifest.json').write_text(json.dumps(self.good))
        before_m = (self.root / 'manifest.json').read_bytes()
        before_a = (self.root / 'work.txt').read_bytes()
        for name in ('manifest.json','work.txt'):
            with self.subTest(name=name), contextlib.redirect_stdout(io.StringIO()) as buf:
                code = cli([str(self.root), '--output', str(self.root/name)])
            self.assertEqual(code, 2)
            self.assertEqual(json.loads(buf.getvalue())['output_status'], 'NOT_WRITTEN')
        self.assertEqual((self.root/'manifest.json').read_bytes(), before_m)
        self.assertEqual((self.root/'work.txt').read_bytes(), before_a)

    def test_receipt_export_creates_new_private_file_and_refuses_second_write(self):
        import contextlib,io
        (self.root / 'manifest.json').write_text(json.dumps(self.good))
        dest = self.root / 'new-receipt.json'
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code = cli([str(self.root), '--output', str(dest)])
        self.assertEqual(code, 1)  # NOT_ADMITTED, but receipt export worked
        self.assertEqual(json.loads(buf.getvalue()), json.loads(dest.read_text()))
        self.assertEqual(json.loads(dest.read_text())['disposition'], 'NOT_ADMITTED')
        if os.name == 'posix':
            self.assertEqual(dest.stat().st_mode & 0o777, 0o600)
        saved = dest.read_bytes()
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            self.assertEqual(cli([str(self.root), '--output', str(dest)]), 2)
        self.assertEqual(saved, dest.read_bytes())

    def test_receipt_export_rejects_parent_traversal(self):
        import contextlib,io
        (self.root / 'manifest.json').write_text(json.dumps(self.good))
        with contextlib.redirect_stdout(io.StringIO()) as buf:
            code=cli([str(self.root), '--output', str(self.root/'..'/'escape.json')])
        self.assertEqual(code, 2)
        self.assertEqual(json.loads(buf.getvalue())['output_error'], 'OUTPUT_TRAVERSAL_FORBIDDEN')

if __name__=='__main__':unittest.main()
