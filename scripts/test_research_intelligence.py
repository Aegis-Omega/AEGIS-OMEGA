#!/usr/bin/env python3
"""Native stdlib falsifiers for AEGIS research intake (no network)."""
import copy
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from research_intelligence import evaluate, parse_json, ResearchError, publisher


def source(sid, url, t='2026-10-10T00:00:00Z'):
    content = 'Summary of published behavior for source ' + sid
    return {'id': sid, 'url': url, 'captured_at': t, 'content': content,
            'sha256': hashlib.sha256(content.encode()).hexdigest(),
            'acquisition': 'connector_capture'}


def packet():
    return {
        'schema': 'aegis.research.packet.v1', 'task_id': 'uwp-13',
        'as_of_utc': '2026-10-11T06:14:00Z', 'repo_head': 'a'*64,
        'sources': [source('lc', 'https://docs.langchain.com/oss/python/langgraph/persistence'),
                    source('oa', 'https://developers.openai.com/api/docs/guides/agent-evals')],
        'proposals': [{
            'id': 'p1', 'local_component': 'agents/cognitive_pipeline.py',
            'candidate': 'Add source-specific verified snapshots',
            'mechanism': 'Bind proposal to evidence checks and a falsifier',
            'test_metric': 'False acceptance rate versus fixed baseline',
            'falsifier': 'A stale or wrong-source claim passes intake',
            'source_ids': ['lc', 'oa']}]
    }


class ResearchScoutTests(unittest.TestCase):
    def reject(self, mutation, code):
        obj = packet()
        mutation(obj)
        with self.assertRaisesRegex(ResearchError, code):
            evaluate(obj)

    def test_complete_packet_ready_for_test_not_admitted(self):
        r = evaluate(packet())
        self.assertEqual(r['proposals'][0]['status'], 'NEEDS_RESEARCH')
        self.assertEqual(r['external_claim_verification'], 'NOT_PERFORMED')
        self.assertEqual(r['benchmark_superiority'], 'NOT_ESTABLISHED')
        self.assertEqual(r['authority_effect'], 'NONE')
        self.assertEqual(r['tool_execution'], 'NOT_EXECUTED')
        self.assertEqual(len(r['packet_sha256']), 64)

    def test_same_json_key_order_same_digest(self):
        original = packet()
        reversed_obj = {k: original[k] for k in reversed(original)}
        self.assertEqual(evaluate(original)['packet_sha256'], evaluate(reversed_obj)['packet_sha256'])

    def test_modifying_a_source_changes_digest(self):
        first = packet()
        second = copy.deepcopy(first)
        second['sources'][0]['content'] += ' and more'
        second['sources'][0]['sha256'] = hashlib.sha256(second['sources'][0]['content'].encode()).hexdigest()
        self.assertNotEqual(evaluate(first)['packet_sha256'], evaluate(second)['packet_sha256'])

    def test_one_source_insufficient(self):
        q = packet(); q['proposals'][0]['source_ids'] = ['lc']
        self.assertEqual(evaluate(q)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_duplicate_issuer_not_independent(self):
        q = packet()
        q['sources'][1]['url'] = 'https://openai.github.io/openai-agents-js'
        q['sources'][0]['url'] = 'https://developers.openai.com/a'
        self.assertEqual(evaluate(q)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_mirrored_identical_content_not_independent(self):
        q = packet()
        q['sources'][1]['content'] = q['sources'][0]['content']
        q['sources'][1]['sha256'] = q['sources'][0]['sha256']
        self.assertEqual(evaluate(q)['proposals'][0]['status'], 'NEEDS_RESEARCH')

    def test_stale_source_insufficient(self):
        q = packet(); q['sources'][1]['captured_at'] = '2026-06-01T00:00:00Z'
        self.assertEqual(evaluate(q)['proposals'][0]['reason'], 'STALE_OR_INSUFFICIENT_DIVERSITY')

    def test_future_source_rejected(self):
        self.reject(lambda q: q['sources'][0].update(captured_at='2026-11-01T00:00:00Z'), 'FUTURE_SOURCE')

    def test_two_manual_notes_cannot_be_ready(self):
        q = packet()
        for s in q['sources']:
            s['acquisition'] = 'manual_note'
        r = evaluate(q)['proposals'][0]
        self.assertEqual(r['status'], 'NEEDS_RESEARCH')
        self.assertEqual(r['reason'], 'INSUFFICIENT_CAPTURE_EVIDENCE')
        self.assertEqual(r['collected_source_count'], 0)

    def test_one_collected_plus_manual_cannot_be_ready(self):
        q = packet()
        q['sources'][1]['acquisition'] = 'manual_note'
        r = evaluate(q)['proposals'][0]
        self.assertEqual(r['status'], 'NEEDS_RESEARCH')
        self.assertEqual(r['collected_source_count'], 0)

    def test_two_fake_captures_never_ready(self):
        r = evaluate(packet())
        self.assertEqual(r['proposals'][0]['status'], 'NEEDS_RESEARCH')
        self.assertEqual(r['external_claim_verification'], 'NOT_PERFORMED')
        self.assertEqual(r['benchmark_superiority'], 'NOT_ESTABLISHED')

    def test_source_tamper_rejected(self):
        self.reject(lambda q: q['sources'][0].update(content='Altered claim, unchanged hash'), 'SOURCE_DIGEST_MISMATCH')

    def test_false_sha_rejected(self):
        self.reject(lambda q: q['sources'][0].update(sha256='0'*64), 'SOURCE_DIGEST_MISMATCH')

    def test_duplicate_sources_rejected(self):
        self.reject(lambda q: q['sources'].append(copy.deepcopy(q['sources'][0])), 'DUPLICATE_SOURCE_ID')

    def test_duplicate_proposals_rejected(self):
        self.reject(lambda q: q['proposals'].append(copy.deepcopy(q['proposals'][0])), 'DUPLICATE_PROPOSAL_ID')

    def test_unknown_refs_rejected(self):
        self.reject(lambda q: q['proposals'][0].update(source_ids=['lc','unknown']), 'UNKNOWN_SOURCE_REF')

    def test_duplicate_refs_rejected(self):
        self.reject(lambda q: q['proposals'][0].update(source_ids=['lc','lc']), 'DUPLICATE_SOURCE_REF')

    def test_no_refs_rejected(self):
        self.reject(lambda q: q['proposals'][0].update(source_ids=[]), 'INVALID_SOURCE_REFS')

    def test_empty_falsifier_rejected(self):
        self.reject(lambda q: q['proposals'][0].update(falsifier=''), 'INVALID_PROPOSAL')

    def test_unbounded_repo_path_rejected(self):
        self.reject(lambda q: q['proposals'][0].update(local_component='../.env'), 'INVALID_COMPONENT')

    def test_git_sha1_commit_oid_valid(self):
        q = packet(); q['repo_head'] = 'a'*40
        self.assertEqual(evaluate(q)['repo_head'], 'a'*40)

    def test_no_repo_head_rejected(self):
        self.reject(lambda q: q.update(repo_head='main'), 'INVALID_REPO_HEAD')

    def test_wrong_schema_rejected(self):
        self.reject(lambda q: q.update(schema='unknown'), 'SCHEMA_MISMATCH')

    def test_unknown_fields_rejected(self):
        self.reject(lambda q: q['sources'][0].update(api_key='secret'), 'INVALID_OBJECT_FIELDS')

    def test_bad_acquisition_rejected(self):
        self.reject(lambda q: q['sources'][0].update(acquisition='verified_by_ai'), 'INVALID_ACQUISITION')

    def test_block_http(self):
        self.reject(lambda q: q['sources'][0].update(url='http://docs.langchain.com/'), 'INVALID_URL')

    def test_block_credentials(self):
        self.reject(lambda q: q['sources'][0].update(url='https://username:password@docs.langchain.com/'), 'INVALID_URL')

    def test_block_private_hosts(self):
        for url in ['https://127.0.0.1/test', 'https://localhost/', 'https://internal.local/',
                    'https://192.168.1.1/', 'https://[::1]/', 'https://api.internal/', 'https://foo:8443/']:
            with self.subTest(url=url):
                self.reject(lambda q: q['sources'][0].update(url=url), 'INVALID_URL')

    def test_block_tracking_query_or_token_fragment(self):
        self.reject(lambda q: q['sources'][0].update(url='https://docs.langchain.com/?token=abc'), 'INVALID_URL')
        self.reject(lambda q: q['sources'][0].update(url='https://docs.langchain.com/#secret'), 'INVALID_URL')

    def test_spoofed_domain_not_distinct_trusted_publisher(self):
        self.assertTrue(publisher('https://openai.com.evil.example.org/x').startswith('unattributed:'))

    def test_reject_invalid_date(self):
        self.reject(lambda q: q['sources'][0].update(captured_at='2026-02-30T00:00:00Z'), 'INVALID_UTC_TIMESTAMP')

    def test_reject_non_utc(self):
        self.reject(lambda q: q.update(as_of_utc='2026-10-11T06:14:00+02:00'), 'INVALID_UTC_TIMESTAMP')

    def test_reject_duplicate_json_keys(self):
        with self.assertRaisesRegex(ResearchError, 'DUPLICATE_JSON_KEY'):
            parse_json('{"schema":1,"schema":2}')

    def test_reject_float_and_nan(self):
        for raw in ['{"x":1.2}', '{"x":NaN}', '{"x":Infinity}']:
            with self.subTest(raw=raw), self.assertRaises(ResearchError):
                parse_json(raw)

    def test_reject_large_payload(self):
        with self.assertRaisesRegex(ResearchError, 'INPUT_TOO_LARGE'):
            parse_json(' ' * 300001)

    def test_run_cli_no_network(self):
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td)/'packet.json'
            fp.write_text(json.dumps(packet()), encoding='utf-8')
            run = subprocess.run([sys.executable, str(Path(__file__).parent/'research_intelligence.py'), str(fp)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stderr)
            self.assertEqual(json.loads(run.stdout)['authority_effect'], 'NONE')

    def test_cli_nonzero_on_corrupt_packet(self):
        with tempfile.TemporaryDirectory() as td:
            fp = Path(td)/'packet.json'
            q = packet(); q['sources'][0]['content'] = 'TAMPER'
            fp.write_text(json.dumps(q), encoding='utf-8')
            run = subprocess.run([sys.executable, str(Path(__file__).parent/'research_intelligence.py'), str(fp)],
                                 capture_output=True, text=True)
            self.assertEqual(run.returncode, 2)
            self.assertIn('SOURCE_DIGEST_MISMATCH', run.stderr)


if __name__ == '__main__':
    unittest.main()
