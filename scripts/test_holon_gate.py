import copy
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import holon_gate as h


def task(tid, paths=None, owner=None, deps=None, state='OPEN', priority='p1'):
    return {'id': tid, 'objective': 'Deliver independently checked benefit',
            'done_when': 'A replayable artifact lands after independent approval',
            'priority': priority, 'state': state, 'paths': paths or [],
            'claimed_by': owner, 'depends_on': deps or []}


class UniversalHolonTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        (self.root / 'proof.txt').write_text('CHECKED\n')
        self.hash = hashlib.sha256((self.root / 'proof.txt').read_bytes()).hexdigest()
        self.base = {'tasks': [task('T1')]}

    def audit(self, data=None, actor='GPT-6'):
        return h.evaluate(data or self.base, self.root, actor)

    def sub(self, **changes):
        d = {'task_id': 'T1', 'author': 'GPT-6', 'source_sha': 'a' * 40,
             'artifact_file': 'proof.txt', 'artifact_sha256': self.hash,
             'tests': [{'name': 'replay', 'source_sha': 'a' * 40, 'result': 'PASS'}],
             'review': {'reviewer': 'Claude', 'verdict': 'ACCEPT', 'source_sha': 'a' * 40}}
        d.update(changes)
        return d

    def test_clean_task_remains_available_not_done(self):
        r = self.audit()['tasks'][0]
        self.assertEqual(r['readiness'], 'AVAILABLE')
        self.assertEqual(self.audit()['admitted_tasks'], 0)

    def test_valid_evidence_plus_distinct_reviewer_only_review_ready(self):
        self.base['submissions'] = [self.sub()]
        r = self.audit()['tasks'][0]
        self.assertEqual(r['evidence'], 'HASH_MATCH')
        self.assertEqual(r['readiness'], 'REVIEW_READY_NOT_ADMITTED')
        self.assertEqual(self.audit()['authority_effect'], 'NONE')

    def test_claimed_main_landing_never_becomes_done(self):
        self.base['tasks'][0]['state'] = 'REPORTED_LANDED'
        self.base['submissions'] = [self.sub()]
        self.assertIn('LANDING_REPORTED_NOT_ATTESTED', self.audit()['tasks'][0]['blockers'])
        self.assertEqual(self.audit()['admitted_tasks'], 0)

    def test_self_review_not_independent(self):
        self.base['submissions'] = [self.sub(review={'reviewer':'GPT-6', 'verdict':'ACCEPT','source_sha':'a'*40})]
        r = self.audit()['tasks'][0]
        self.assertIn('INDEPENDENT_REVIEW_NOT_RECORDED', r['blockers'])
        self.assertNotEqual(r['readiness'], 'REVIEW_READY_NOT_ADMITTED')

    def test_stale_test_sha_not_proof(self):
        self.base['submissions'] = [self.sub(tests=[{'source_sha':'b'*40, 'result':'PASS'}])]
        self.assertIn('TEST_EVIDENCE_MISSING_OR_STALE', self.audit()['tasks'][0]['blockers'])

    def test_bad_artifact_hash_is_not_replay(self):
        self.base['submissions'] = [self.sub(artifact_sha256='f'*64)]
        self.assertEqual(self.audit()['tasks'][0]['evidence'], 'HASH_MISMATCH')

    def test_symlink_artifact_cannot_read_outside_root(self):
        outside = self.root.parent / 'outside_holon_proof.txt'
        try:
            outside.write_text('EXTERNAL')
            (self.root/'escape.txt').symlink_to(outside)
            self.base['submissions'] = [self.sub(artifact_file='escape.txt')]
            self.assertEqual(self.audit()['tasks'][0]['evidence'], 'OUTSIDE_WORKSPACE')
        finally:
            outside.unlink(missing_ok=True)

    def test_conflicting_paths_block_both_active_claims(self):
        self.base['tasks'] = [task('A', ['supabase/functions/agent'], 'GPT-6', state='IN_PROGRESS'),
                              task('B', ['supabase/functions/agent/index.ts'], 'Claude', state='CLAIMED')]
        out = self.audit()['tasks']
        self.assertEqual([r['readiness'] for r in out], ['COORDINATE','COORDINATE'])
        self.assertEqual(out[0]['scope_collisions'], ['B'])

    def test_sibling_files_do_not_conflict(self):
        self.base['tasks'] = [task('A',['src/agent.py'],'GPT-6',state='CLAIMED'),
                              task('B',['src/agent.py.bak'],'Claude',state='CLAIMED')]
        out = self.audit()['tasks']
        self.assertEqual(out[0]['scope_collisions'], [])
        self.assertEqual(out[1]['scope_collisions'], [])

    def test_unclaimed_task_overlapping_claimed_is_blocked_before_start(self):
        self.base['tasks'] = [task('A',['src/foo'], 'GPT-6',state='CLAIMED'),
                              task('B',['src/foo'],'Claude',state='OPEN')]
        out = self.audit()['tasks']
        self.assertEqual(out[0]['scope_collisions'], ['B'])
        self.assertEqual(out[1]['scope_collisions'], ['A'])
        self.assertIn('COORDINATE_WITH_CLAIM_OWNER', out[1]['blockers'])
        self.assertEqual(out[1]['readiness'], 'COORDINATE')

    def test_path_escape_rejected(self):
        for path in ['../secrets', '/etc/passwd', 'src/../foo', 'C:/tmp/file', '~/ssh']:
            self.base['tasks'][0]['paths']=[path]
            with self.assertRaises(h.InvalidSnapshot, msg=path): self.audit()

    def test_unknown_and_duplicate_ids_rejected(self):
        self.base['tasks'][0]['depends_on']=['missing']
        with self.assertRaises(h.InvalidSnapshot):self.audit()
        self.base['tasks'][0]['depends_on']=[]
        self.base['tasks'].append(copy.deepcopy(self.base['tasks'][0]))
        with self.assertRaises(h.InvalidSnapshot):self.audit()

    def test_cycles_are_blocked(self):
        self.base['tasks']=[task('A',deps=['B']),task('B',deps=['A'])]
        for t in self.audit()['tasks']:
            self.assertIn('CYCLIC_DEPENDENCY',t['blockers'])
            self.assertEqual(t['readiness'],'BLOCKED')

    def test_claims_do_not_unlock_dependencies(self):
        self.base['tasks']=[task('A',state='REPORTED_LANDED'),task('B',deps=['A'])]
        result = self.audit()['tasks']
        self.assertIn('DEPENDENCIES_NOT_INDEPENDENTLY_ADMITTED', result[1]['blockers'])

    def test_report_is_order_deterministic(self):
        self.base['tasks']=[task('B',priority='p2'),task('A',priority='p0')]
        self.assertEqual([x['id'] for x in self.audit()['tasks']], ['A','B'])
        self.assertEqual(json.dumps(self.audit(), sort_keys=True),json.dumps(self.audit(),sort_keys=True))

    def test_large_dependency_graph_cannot_crash_recursion(self):
        self.base['tasks'] = [task(str(i), deps=[str(i-1)] if i else []) for i in range(1300)]
        r = self.audit()['tasks']
        self.assertEqual(len(r), 1300)
        self.assertEqual(len([x for x in r if x['readiness'] == 'AVAILABLE']), 1)

    def test_cycle_descendants_also_blocked(self):
        self.base['tasks'] = [task('A',deps=['B']),task('B',deps=['A']),task('C',deps=['A'])]
        by_id = {t['id']:t for t in self.audit()['tasks']}
        self.assertIn('CYCLIC_DEPENDENCY',by_id['C']['blockers'])

    def test_submission_by_nonclaim_owner_not_review_ready(self):
        self.base['tasks'][0]['claimed_by'] = 'Claude'
        self.base['submissions'] = [self.sub()]
        r = self.audit(actor='Claude')['tasks'][0]
        self.assertIn('SUBMISSION_NOT_FROM_CLAIM_OWNER',r['blockers'])
        self.assertNotEqual(r['readiness'],'REVIEW_READY_NOT_ADMITTED')

    def test_invalid_source_sha_fail_closed(self):
        self.base['submissions']=[self.sub(source_sha='123')]
        with self.assertRaises(h.InvalidSnapshot): self.audit()

    def test_unavailable_local_file_keeps_unverified(self):
        self.base['submissions']=[self.sub(artifact_file='absent.txt')]
        self.assertEqual(self.audit()['tasks'][0]['evidence'],'UNAVAILABLE_OR_UNSAFE')

    def test_input_not_modified(self):
        d=copy.deepcopy(self.base)
        self.audit()
        self.assertEqual(self.base,d)

    def test_duplicate_json_key_is_not_silently_overridden(self):
        p=self.root/'bad.json'
        p.write_text('{"tasks":[],"tasks":[]}')
        with patch('sys.stdout'):
            self.assertEqual(h.main(['--input',str(p),'--actor','GPT-6']),2)

    def test_nan_or_infinity_cannot_enter_task_snapshot(self):
        p=self.root/'bad.json'
        p.write_text('{"tasks":[],"score":NaN}')
        with patch('sys.stdout'):
            self.assertEqual(h.main(['--input',str(p),'--actor','GPT-6']),2)

    def test_oversized_snapshot_denied(self):
        p=self.root/'large.json'
        p.write_text('{"tasks":[],'+'"a":"'+'x'*1100000+'"}')
        with patch('sys.stdout'):
            self.assertEqual(h.main(['--input',str(p),'--actor','GPT-6']),2)

    def test_cli_outputs_json_and_invalid_input_exit_nonzero(self):
        p=self.root/'snapshot.json'
        p.write_text(json.dumps(self.base))
        with patch('sys.stdout') as stdout:
            rc=h.main(['--input',str(p),'--actor','Claude','--root',str(self.root)])
        self.assertEqual(rc,0)
        self.assertTrue(stdout.write.called)
        p.write_text('{}')
        with patch('sys.stdout'):
            rc=h.main(['--input',str(p),'--actor','Claude','--root',str(self.root)])
        self.assertEqual(rc,2)


if __name__ == '__main__':
    unittest.main(verbosity=2)
