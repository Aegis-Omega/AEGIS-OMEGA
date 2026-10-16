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
            "execution_effect":"NONE", "nodes":list(items)}


def node(n, topic, labels=()):
    return {"key":f"Aegis-Omega/AEGIS-OMEGA#{n}","number":n,"topic":topic,"labels":list(labels)}


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
    def test_prior_prevents_duplicate(self):
        g=graph(node(42,'research')); first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        second=opt.select_work(g,source_head=HEAD,tick='tick-2',prior=first)
        self.assertEqual(second['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')
    def test_change_source_invalidates_dedupe(self):
        g=graph(node(42,'research')); first=opt.select_work(g,source_head=HEAD,tick='tick-1')
        second=opt.select_work(g,source_head='b'*40,tick='tick-2',prior=first)
        self.assertEqual(second['disposition'],'REVIEW_READY')
    def test_untrusted_prior_rejected(self):
        with self.assertRaisesRegex(ValueError,'PRIOR_RECEIPT_UNTRUSTED'):
            opt.select_work(graph(node(1,'engineering')),source_head=HEAD,tick='tick-1',prior={'schema':'bad'})
    def test_bad_issue_rejected(self):
        with self.assertRaisesRegex(ValueError,'INVALID_ISSUE_ID'):
            opt.select_work(graph({'key':'../../secrets','topic':'commerce','labels':[]}),source_head=HEAD,tick='tick-1')
    def test_no_work_hold(self):
        r=opt.select_work(graph(),source_head=HEAD,tick='tick-1')
        self.assertEqual(r['disposition'],'HOLD_NO_NEW_VERIFIABLE_WORK')
    def test_tick_strict(self):
        with self.assertRaisesRegex(ValueError,'INVALID_TICK'):
            opt.select_work(graph(),source_head=HEAD,tick='a'*200)

if __name__=='__main__':unittest.main()