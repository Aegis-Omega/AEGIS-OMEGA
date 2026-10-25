"""Cross-module composition tests; require real issue_evolution when running in GitHub."""
import tempfile
import unittest
from pathlib import Path
from agents.dendrite_workplane import compose,publish,observe_evolution

HEAD='a'*40
REPO='Aegis-Omega/AEGIS-OMEGA'

def fixture(count=37,edge=True):
    issues=[]
    for n in range(1,count+1):
        labels=[{'name':'needs-operator'}] if n==3 else [{'name':'task'}]
        title='finance' if n==3 else 'Lean theorem' if n==2 else 'Engineering task'
        issues.append(dict(number=n,title=title,body='Depends on #2' if edge and n==1 else '',labels=labels))
    return dict(repository=REPO,issues=issues,complete_pages=True,acquisition='EXPLICIT_OFFLINE_FIXTURE',pages=1)

def trial():
    return dict(schema='AEGIS_ISSUE_EVOLUTION_TRIAL_V1',issue=f'{REPO}#1',baseline='b'*40,candidate='c'*40,
                pre_registered_metric='task_success',holdout_digest='d'*64,rollback_ref='b'*40,
                paired_results=[dict(task_id=f't{i}',baseline_score=0.2,candidate_score=0.9,safety_regression=False) for i in range(32)])

class UnifiedWorkplaneTests(unittest.TestCase):
    def test_shards_cover_all_37_issues(self):
        r=compose(fixture(),source_head=HEAD)
        self.assertEqual(r['node_count'],37)
        self.assertEqual(len(r['issue_route_shards']),2)
        self.assertEqual(sum(len(x['events']) for x in r['issue_route_shards']),37)
    def test_no_promotion_or_execution(self):
        r=compose(fixture(),source_head=HEAD)
        self.assertEqual(r['skill_promotion'],'DENIED')
        self.assertEqual(r['execution_effect'],'NONE')
        self.assertEqual(r['production_admission'],'DENIED')
    def test_round_consistency(self):
        r=compose(fixture(),source_head=HEAD)
        self.assertEqual(r['issue_evolution']['issue_count'],r['node_count'])
    def test_nonempty_trial_creates_cross_issue_lesson(self):
        r=compose(fixture(),source_head=HEAD,trials=[trial()])
        self.assertGreaterEqual(len(r['lesson_route_shards']),1)
    def test_operator_issue_not_in_finance_or_engineering(self):
        r=compose(fixture(),source_head=HEAD)
        messages=[event for shard in r['issue_route_shards'] for event in shard['events']]
        operator=messages[2]
        self.assertNotIn('finance',operator['delivered_roles'])
        self.assertNotIn('engineering',operator['delivered_roles'])
        self.assertIn('cybersecurity',operator['delivered_roles'])
    def test_invalid_head_denied(self):
        with self.assertRaisesRegex(ValueError,'INVALID_WORKPLANE_SOURCE_HEAD'):
            compose(fixture(),source_head='main')
    def test_lineage_pair_required(self):
        with self.assertRaisesRegex(ValueError,'EVOLUTION_INPUT_PAIR_REQUIRED'):
            compose(fixture(),source_head=HEAD,skill_tree='/tmp/missing')
    def test_deterministic_compilation(self):
        self.assertEqual(compose(fixture(),source_head=HEAD),compose(fixture(),source_head=HEAD))
    def test_hash_tamper_denied_before_any_spool_write(self):
        p=compose(fixture(2),source_head=HEAD)
        p['node_count']=999
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'spool'
            with self.assertRaisesRegex(ValueError,'WORKPLANE_RECEIPT_INVALID'):
                publish(p,root=target)
            self.assertFalse(target.exists())
    def test_publish_and_read_via_real_mailbox(self):
        from agents.dendrite_mailbox import read_local
        p=compose(fixture(3),source_head=HEAD)
        with tempfile.TemporaryDirectory() as d:
            dst=Path(d)/'private'
            out=publish(p,root=dst)
            self.assertEqual(out['delivery'],'LOCAL_SPOOL_ONLY')
            self.assertGreater(len(read_local(dst,'engineering')),0)
    def test_repeated_publication_dedup(self):
        p=compose(fixture(2),source_head=HEAD)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'spool'
            first=publish(p,root=dest)
            second=publish(p,root=dest)
            self.assertGreater(first['batches'][0]['written'],0)
            self.assertEqual(second['batches'][0]['written'],0)
    def test_actual_private_hmac_delivery(self):
        from agents.dendrite_attestation import read_attested
        key=b'x'*32
        p=compose(fixture(2),source_head=HEAD)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'spool';secret=Path(d)/'key';secret.write_bytes(key);secret.chmod(0o600)
            result=publish(p,root=dest,key_file=secret,key_id='issue_relay')
            self.assertGreater(result['batches'][0]['attestations_written'],0)
            self.assertGreaterEqual(len(read_attested(dest,'engineering',{'issue_relay':key})),1)
    def test_unpaired_relay_key_denied_before_writes(self):
        p=compose(fixture(2),source_head=HEAD)
        with tempfile.TemporaryDirectory() as d:
            dest=Path(d)/'spool'
            with self.assertRaisesRegex(ValueError,'RELAY_KEY_ARGUMENTS_INCOMPLETE'):
                publish(p,root=dest,key_id='foo')
            self.assertFalse(dest.exists())

if __name__=='__main__':unittest.main()
