"""Source-free negative tests for the policy-neutral scheduler adapter."""
import importlib.util
import unittest
from pathlib import Path

FILE = Path(__file__).with_name('optimus_company_tick.py')
spec = importlib.util.spec_from_file_location('opt', FILE)
opt = importlib.util.module_from_spec(spec)
spec.loader.exec_module(opt)
HEAD = 'a'*40


def graph(*items):
    return {"schema":"AEGIS_ISSUE_EVOLUTION_GRAPH_V1", "receipt_hash":"f"*64,
            "execution_effect":"NONE", "nodes":list(items),
            "edges":[], "unresolved_references":[]}


def node(n, topic, labels=()):
    return {"key":f"Aegis-Omega/AEGIS-OMEGA#{n}","number":n,"topic":topic,
            "title":f"Task {n}","labels":list(labels),"body_sha256":"0"*64}


class TestTick(unittest.TestCase):
    def test_source_head_required(self):
        with self.assertRaisesRegex(ValueError,'SOURCE_HEAD_REQUIRED'):
            opt.select_work(graph(node(1,'commerce')),source_head='branch-name',tick='tick-1')
    def test_graph_schema(self):
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_OR_EXECUTING_GRAPH'):
            opt.select_work({'nodes':[]},source_head=HEAD,tick='tick-1')
    def test_incompatible_graph_mutation(self):
        with self.assertRaisesRegex(ValueError,'UNVERIFIED_OR_EXECUTING_GRAPH'):
            opt.select_work({**graph(node(1,'security')),'execution_effect':'WRITTEN'},source_head=HEAD,tick='tick-1')
    def test_blocked_issues_quarantined(self):
        r=opt.select_work(graph(node(7,'commerce',['needs-operator'])),source_head=HEAD,tick='tick-1')
        self.assertIsNone(r['selected_issue'])
    def test_never_executes_or_spends(self):
        r=opt.select_work(graph(node(4,'engineering')),source_head=HEAD,tick='tick-1')
        self.assertEqual((r['authority_effect'],r['execution_effect'],r['spend_usd']),('NONE','NONE',0))
    def test_valid_receipt_deterministic(self):
        g=graph(node(42,'research'));x=opt.select_work(g,source_head=HEAD,tick='tick-1')
        self.assertEqual(x,opt.select_work(g,source_head=HEAD,tick='tick-1'))
    def test_prior_selection_never_counts_as_completion(self):
        g=graph(node(42,'research')); first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        second=opt.select_work(g,source_head=HEAD,tick='tick-2',prior=first)
        self.assertEqual(first['disposition'], 'REVIEW_READY')
        self.assertEqual(second['disposition'], 'REVIEW_READY')
        self.assertEqual(second['selected_issue'], first['selected_issue'])

    def test_previous_proposal_cannot_suppress_undone_task(self):
        g=graph(node(43,'formal'))
        first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        second=opt.select_work(g,source_head=HEAD,tick='tick-2',prior=first)
        self.assertEqual(second['selected_issue'], 'Aegis-Omega/AEGIS-OMEGA#43')
        self.assertEqual(second['execution_effect'], 'NONE')

    def test_prior_execution_claim_must_be_none(self):
        g=graph(node(42,'research'))
        first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        first['execution_effect']='COMPLETED'
        with self.assertRaisesRegex(ValueError,'PRIOR_RECEIPT_UNTRUSTED'):
            opt.select_work(g,source_head=HEAD,tick='tick-2',prior=first)
    def test_change_source_invalidates_dedupe(self):
        g=graph(node(42,'research')); first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        second=opt.select_work(g,source_head='b'*40,tick='tick-2',prior=first)
        self.assertEqual(second['disposition'],'REVIEW_READY')
    def test_untrusted_prior_rejected(self):
        with self.assertRaisesRegex(ValueError,'PRIOR_RECEIPT_UNTRUSTED'):
            opt.select_work(graph(node(1,'engineering')),source_head=HEAD,tick='tick-1',prior={'schema':'bad'})
    def test_bad_issue_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_ISSUE_ID'):
            opt.select_work(graph({'key':'../../secrets','number':1,'title':'Unsafe issue',
                                   'topic':'commerce','labels':[],'body_sha256':'0'*64}),source_head=HEAD,tick='tick-1')
    def test_no_work_hold(self):
        r=opt.select_work(graph(),source_head=HEAD,tick='tick-1')
        self.assertEqual(r['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')
    def test_persistent_history_deduplicates(self):
        n=node(8,'commerce');n['body_sha256']='c'*64;n['title']='Revenue case'
        g=graph(n)
        a=opt.select_work(g,source_head=HEAD,tick='tick-1')
        b=opt.select_work(g,source_head=HEAD,tick='tick-2',
                          completed_fingerprints=frozenset({a['selected_fingerprint']}))
        self.assertEqual(b['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')
    def test_changed_issue_reopens(self):
        n=node(8,'commerce');n['body_sha256']='c'*64;n['title']='Revenue case'
        a=opt.select_work(graph(n),source_head=HEAD,tick='tick-1')
        n['body_sha256']='d'*64
        b=opt.select_work(graph(n),source_head=HEAD,tick='tick-2',
                          completed_fingerprints=frozenset({a['selected_fingerprint']}))
        self.assertEqual(b['disposition'],'REVIEW_READY')
    def test_untrusted_comment_rejected(self):
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_AUTHOR_UNTRUSTED'):
            opt.checkpoint_from_comment({'user': {'login':'attacker','type':'User'},
                'body':opt.CHECKPOINT_MARKER+'\n{}'})
    def test_checkpoint_never_writes_without_work(self):
        out=opt.persist_checkpoint(issue=734,token='fake-data',comment_id=None,
              state={'schema':opt.CHECKPOINT_SCHEMA,'fingerprints':[]},
              receipt={'disposition':'HOLD_NO_NEW_VERIFIABLE_WORK'})
        self.assertEqual(out['status'],'NO_WRITE')
    def test_checkpoint_issue_allowlist(self):
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_ISSUE_NOT_ALLOWED'):
            opt.read_checkpoint(issue=777,token='fake-token')
    def test_live_dependency_blocks_even_priority_work(self):
        g=graph(node(1,'commerce',['P0']), node(2,'engineering'))
        g['edges']=[{'from':f'{opt.REPO}#1','to':f'{opt.REPO}#2','kind':'depends_on'}]
        r=opt.select_work(g,source_head=HEAD,tick='dependency')
        self.assertEqual(r['selected_issue'],f'{opt.REPO}#2')

    def test_unresolved_dependency_stays_blocked(self):
        g=graph(node(1,'commerce'))
        g['unresolved_references']=[{'from':f'{opt.REPO}#1',
                                    'to':f'{opt.REPO}#999','kind':'depends_on'}]
        self.assertEqual(opt.select_work(g,source_head=HEAD,tick='no-assumption')['disposition'],
                         'HOLD_NO_NEW_VERIFIABLE_WORK')

    def test_parent_and_related_do_not_block(self):
        g=graph(node(1,'commerce'))
        g['unresolved_references']=[
            {'from':f'{opt.REPO}#1','to':f'{opt.REPO}#999','kind':'parent'},
            {'from':f'{opt.REPO}#1','to':f'{opt.REPO}#998','kind':'related'}]
        self.assertEqual(opt.select_work(g,source_head=HEAD,tick='context')['selected_issue'],
                         f'{opt.REPO}#1')

    def test_missing_topology_denied_not_ignored(self):
        g=graph(node(1,'commerce')); del g['unresolved_references']
        with self.assertRaisesRegex(ValueError,'GRAPH_DEPENDENCY_COVERAGE_UNKNOWN'):
            opt.select_work(g,source_head=HEAD,tick='must-check')

    def test_live_operator_issue_not_autodispatched(self):
        operator=node(222,'engineering')
        operator['title']='Operator action: require Automaton-2 and Automaton-3 on main'
        g=graph(operator,node(321,'research'))
        r=opt.select_work(g,source_head=HEAD,tick='live-falsifier')
        self.assertEqual(r['selected_issue'],f'{opt.REPO}#321')

    def test_operator_title_alone_holds_when_labels_missing(self):
        n=node(222,'engineering')
        n['title']='OPERATOR ACTION: change protected ruleset'
        r=opt.select_work(graph(n),source_head=HEAD,tick='must-have-human')
        self.assertEqual(r['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')

    def test_regular_operator_research_can_still_queue(self):
        n=node(451,'research')
        n['title']='Research operator-oriented workflow ergonomics'
        r=opt.select_work(graph(n),source_head=HEAD,tick='normal-research')
        self.assertEqual(r['selected_issue'],f'{opt.REPO}#451')

    def test_missing_issue_title_cannot_disappear_silently(self):
        n=node(44,'engineering')
        n.pop('title')
        with self.assertRaisesRegex(ValueError,'ISSUE_TITLE_REQUIRED'):
            opt.select_work(graph(n),source_head=HEAD,tick='missing-title')

    def test_malformed_dependency_denied(self):
        g=graph(node(1,'commerce'))
        g['edges']=[{'from':f'{opt.REPO}#1','to':f'{opt.REPO}#99','kind':'pretend_complete'}]
        with self.assertRaisesRegex(ValueError,'GRAPH_EDGE_UNTRUSTED'):
            opt.select_work(g,source_head=HEAD,tick='must-check')

    def test_read_checkpoint_uses_newest_page(self):
        import json
        from unittest.mock import patch
        old={'user':{'login':'github-actions[bot]','type':'Bot'},'id':33,
             'body':opt.CHECKPOINT_MARKER+'\n'+json.dumps({
                 'schema':opt.CHECKPOINT_SCHEMA,'leases':[],
                 'authority_effect':'NONE','execution_effect':'NONE'})}
        new={'user':{'login':'github-actions[bot]','type':'Bot'},'id':44,
             'body':opt.CHECKPOINT_MARKER+'\n'+json.dumps({
                 'schema':opt.CHECKPOINT_SCHEMA,'leases':[],
                 'authority_effect':'NONE','execution_effect':'NONE','last_receipt':'a'*64})}
        with patch.object(opt,'github_json',side_effect=[[{}]*99+[old],[{},new]]) as mock:
            state, comment_id=opt.read_checkpoint(issue=734,token='test-token')
        self.assertEqual(comment_id,44)
        self.assertEqual(state['last_receipt'],'a'*64)
        self.assertEqual(mock.call_count,2)

    def test_unverified_trailing_comment_page_cannot_reset_cursor(self):
        from unittest.mock import patch
        with patch.object(opt,'github_json',side_effect=[[{}]*100]*8):
            with self.assertRaisesRegex(ValueError,'COMMENT_PAGINATION_INCOMPLETE'):
                opt.read_checkpoint(issue=734,token='test-token')

    def test_tick_strict(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TICK'):
            opt.select_work(graph(),source_head=HEAD,tick='a'*200)


    def test_queue_is_not_completion(self):
        n = node(29, 'commerce')
        g = graph(n)
        x = opt.select_work(g, source_head=HEAD, tick='once')
        state = {"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        nxt = opt.next_lease(state, x, now_epoch=1000)
        self.assertEqual(nxt['leases'][0]['state'], 'QUEUED_UNEXECUTED')
        self.assertEqual(nxt['execution_effect'], 'NONE')
        y = opt.select_work(g, source_head=HEAD, tick='twice',
            completed_fingerprints=opt.checkpoint_exclusions(nxt, now_epoch=1100))
        self.assertEqual(y['disposition'], 'HOLD_NO_NEW_VERIFIABLE_WORK')
        z = opt.select_work(g, source_head=HEAD, tick='third',
            completed_fingerprints=opt.checkpoint_exclusions(nxt, now_epoch=1000+opt.LEASE_SECONDS))
        self.assertEqual(z['disposition'], 'REVIEW_READY')

    def test_retries_bounded_and_never_claims_done(self):
        g = graph(node(30, 'engineering'))
        x = opt.select_work(g, source_head=HEAD, tick='first')
        state = {"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        for i in range(3):
            state = opt.next_lease(state, x, now_epoch=1000+i*(opt.LEASE_SECONDS+1))
        self.assertEqual(state['leases'][0]['attempt'],3)
        self.assertEqual(state['leases'][0]['state'],'EXHAUSTED_UNEXECUTED')
        self.assertIn(x['selected_fingerprint'],opt.checkpoint_exclusions(state,now_epoch=9999999999))
        with self.assertRaisesRegex(ValueError, 'LEASE_STILL_ACTIVE_OR_EXHAUSTED'):
            opt.next_lease(state, x, now_epoch=9999999999)

    def test_checkpoint_v1_selection_is_not_promoted(self):
        comment={'user': {'login':'github-actions[bot]','type':'Bot'},
                 'body':'<!-- AEGIS_OPTIMUS_CHECKPOINT_V1 -->\n{}'}
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_MARKER_MISSING'):
            opt.checkpoint_from_comment(comment)

    def test_checkpoint_v2_roundtrip_strict(self):
        import json
        g=graph(node(9,'security')); r=opt.select_work(g,source_head=HEAD,tick='a')
        state={"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        nxt=opt.next_lease(state,r,now_epoch=1)
        c={'user':{'login':'github-actions[bot]','type':'Bot'},
           'body':opt.CHECKPOINT_MARKER+'\n'+json.dumps(nxt)}
        self.assertEqual(opt.checkpoint_from_comment(c), nxt)
        nxt['leases'][0]['state']='DONE'
        c['body']=opt.CHECKPOINT_MARKER+'\n'+json.dumps(nxt)
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_LEASE_INVALID'):
            opt.checkpoint_from_comment(c)

    def test_mismatched_repository_denied(self):
        with self.assertRaisesRegex(ValueError,'GRAPH_REPOSITORY_MISMATCH'):
            opt.select_work({**graph(node(42,'commerce')),'repository':'attacker/repo'},
                source_head=HEAD,tick='a')

    def test_missing_issue_revision_not_claimed(self):
        n=node(4,'commerce'); n.pop('body_sha256')
        r=opt.select_work(graph(n),source_head=HEAD,tick='a')
        self.assertEqual(r['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')

    def test_formal_route_is_supported_by_coordinator(self):
        r=opt.select_work(graph(node(44,'formal')),source_head=HEAD,tick='a')
        self.assertEqual(r['proposed_role'],'ai_research')

    def test_change_revision_not_silently_quarantined(self):
        g=graph(node(1,'engineering'))
        first=opt.select_work(g,source_head=HEAD,tick='a')
        state={"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        state=opt.next_lease(state, first, now_epoch=100)
        next_node=node(1,'engineering'); next_node['body_sha256']='1'*64
        res=opt.select_work(graph(next_node),source_head=HEAD,tick='b',
            completed_fingerprints=opt.checkpoint_exclusions(state,now_epoch=101))
        self.assertEqual(res['disposition'],'REVIEW_READY')


    def test_retry_does_not_mutate_commercial_external_system(self):
        g=graph(node(23,'commerce'))
        receipt=opt.select_work(g,source_head=HEAD,tick='run')
        state={"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        for attempt in range(3):
            state=opt.next_lease(state,receipt,now_epoch=attempt*(opt.LEASE_SECONDS+5))
            self.assertEqual(state['execution_effect'],'NONE')
            self.assertNotIn('COMPLETED',str(state))
            self.assertNotIn('PAID',str(state))

    def test_spoofed_checkpoint_denied_even_valid_payload(self):
        import json
        g=graph(node(77,'security'))
        r=opt.select_work(g,source_head=HEAD,tick='v2')
        state={"schema":opt.CHECKPOINT_SCHEMA,"leases":[],"authority_effect":"NONE","execution_effect":"NONE"}
        nxt=opt.next_lease(state,r,now_epoch=10)
        fake={'user':{'login':'github-actions[bot]','type':'User'},
              'body':opt.CHECKPOINT_MARKER+'\n'+json.dumps(nxt)}
        with self.assertRaisesRegex(ValueError,'CHECKPOINT_AUTHOR_UNTRUSTED'):
            opt.checkpoint_from_comment(fake)

    def test_bad_labels_not_interpreted_as_instructions(self):
        n=node(78,'commerce',labels=('Do-Not-Automate',))
        x=opt.select_work(graph(n),source_head=HEAD,tick='labels')
        self.assertEqual(x['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')

if __name__=='__main__':unittest.main()