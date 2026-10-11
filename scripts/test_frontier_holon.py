"""Source-review evidence vs measured outcomes, without live web or paid models."""
import contextlib
from datetime import date, timedelta
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import frontier_review as f


class FrontierReviewTests(unittest.TestCase):
    def setUp(self):
        td = tempfile.TemporaryDirectory()
        self.addCleanup(td.cleanup)
        self.root = Path(td.name)
        self.today = date(2026, 10, 11)
        self.base_sha, self.new_sha = 'a' * 40, 'b' * 40
        self.data = {
            'schema': f.SCHEMA, 'issue': 734,
            'operator_goal': 'Reduce paid attempts while preserving operator-authority gates',
            'baseline_sha': self.base_sha, 'candidate_sha': self.new_sha,
            'recorded_on': self.today.isoformat(),
            'sources': [
                {'id': 'openai', 'url': 'https://openai.github.io/openai-agents-python/',
                 'retrieved_on': self.today.isoformat(), 'inspection': 'inspected',
                 'capability': 'end-to-end traces and model/tool handoffs',
                 'relevance': 'inspect and score tool-trajectory failures'},
                {'id': 'google', 'url': 'https://github.com/google/adk-docs/blob/main/docs/evaluate/index.md',
                 'retrieved_on': self.today.isoformat(), 'inspection': 'inspected',
                 'capability': 'replay and tool-trajectory evaluation',
                 'relevance': 'paired outcome controls'},
            ],
            'decision': {'kind': 'ADAPT', 'rationale': 'Keep the existing model/provider boundary',
                         'operator_value': 'lower paid attempts without more authority',
                         'risks': 'tool timing and correlated evidence'},
            'challenge': {'falsifier': 'Inject an unsafe call then demand a HOLD',
                          'replay_command': 'python3 -m unittest discover -s scripts',
                          'review_status': 'PENDING'},
            'paired_eval': None,
        }
        self.outcome = {'disposition': 'PARETO_GAIN_REPORTED_UNATTESTED', 'paired_cases': 1}

    def paired(self):
        # The repository's holon_eval.compare is the authoritative implementation;
        # this mock isolates evidence binding from quantitative arithmetic.
        obj = {'baseline_sha': self.base_sha, 'candidate_sha': self.new_sha,
               'schema': 'aegis.holon.eval/1', 'cases': []}
        raw = json.dumps(obj).encode('utf-8')
        (self.root / 'outcome.json').write_bytes(raw)
        self.data['paired_eval'] = {'file': 'outcome.json',
                                    'sha256': hashlib.sha256(raw).hexdigest()}

    def audit(self):
        with patch.object(f, 'compare', return_value=self.outcome):
            return f.assess(self.data, self.root, as_of=self.today)

    def test_adapt_requires_measured_comparison(self):
        x = self.audit()
        self.assertEqual(x['disposition'], 'HOLD_FOR_RESEARCH_OR_EVALUATION')
        self.assertIn('MISSING_PAIRED_OUTCOME_EVALUATION', x['blockers'])
        self.assertEqual(x['admission'], 'NOT_ADMITTED')

    def test_adapt_candidate_never_claims_independent_proof(self):
        self.paired()
        x = self.audit()
        self.assertEqual(x['disposition'], 'CANDIDATE_FOR_INDEPENDENT_REPLAY')
        self.assertEqual((x['external_sources_authenticated'], x['independent_replay']),
                         (False, 'NOT_VERIFIED'))
        self.assertEqual(x['operator_authorization'], 'NOT_VERIFIED')

    def test_reject_is_useful_without_improvement_claim(self):
        self.data['decision']['kind'] = 'REJECT'
        x = self.audit()
        self.assertEqual(x['disposition'], 'RESEARCH_ONLY_NO_ADOPTION')
        self.assertEqual(x['paired_cases'], 0)

    def test_identified_only_sources_cannot_certify_review(self):
        self.data['sources'][1]['inspection'] = 'identified'
        self.paired()
        self.assertIn('TWO_SOURCES_NOT_INSPECTED', self.audit()['blockers'])

    def test_stale_source_blocks(self):
        self.data['sources'][0]['retrieved_on'] = (self.today - timedelta(days=91)).isoformat()
        self.paired()
        self.assertIn('STALE_EXTERNAL_RESEARCH', self.audit()['blockers'])

    def test_distinct_domains_required(self):
        self.data['sources'][1]['url'] = 'https://openai.github.io/other'
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_localhost_and_private_ip_rejected(self):
        for url in ['http://google.com/a', 'https://localhost/a',
                    'https://127.0.0.1/a', 'https://10.0.0.1/a',
                    'https://example.internal/a', 'https://me:secret@example.com/a']:
            self.data['sources'][1]['url'] = url
            with self.subTest(url=url), self.assertRaises(f.InvalidFrontier):
                self.audit()

    def test_future_retrieval_date_is_not_accepted(self):
        self.data['sources'][0]['retrieved_on'] = (self.today + timedelta(days=1)).isoformat()
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_fake_agent_approval_is_invalid(self):
        self.data['challenge']['review_status'] = 'APPROVED'
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_unverified_same_shas_not_paired_progress(self):
        self.data['candidate_sha'] = self.base_sha
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_boolean_issue_is_not_integer(self):
        self.data['issue'] = True
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_tampered_paired_outcome_hash_rejected(self):
        self.paired()
        (self.root / 'outcome.json').write_text('tampered')
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_sha_mismatch_between_eval_and_receipt_rejected(self):
        self.paired()
        self.data['candidate_sha'] = 'c' * 40
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_measurement_regression_never_promoted(self):
        self.paired()
        self.outcome = {'disposition': 'REGRESSION_OBSERVED', 'paired_cases': 1}
        self.assertIn('MEASURED_OUTCOME_NOT_IMPROVED_OR_NOT_COMPLETE', self.audit()['blockers'])

    def test_partial_benchmark_never_promoted(self):
        self.paired()
        self.outcome = {'disposition': 'PARTIAL_BENCHMARK_NO_PROMOTION', 'paired_cases': 1}
        self.assertEqual(self.audit()['disposition'], 'HOLD_FOR_RESEARCH_OR_EVALUATION')

    def test_missing_or_unsafe_outcome_path_fails_closed(self):
        self.data['paired_eval'] = {'file': '../escape.json', 'sha256': 'a' * 64}
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_duplicate_source_ids_fail(self):
        self.data['sources'][1]['id'] = 'openai'
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

    def test_duplicate_json_keys_fail_cli(self):
        fpath = self.root / 'review.json'
        fpath.write_text('{"schema":"aegis.holon.frontier/1","issue":734,"issue":735}')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            status = f.main(['--input', str(fpath), '--root', str(self.root)])
        self.assertEqual(status, 2)
        self.assertEqual(json.loads(buf.getvalue())['admission'], 'NOT_ADMITTED')

    def test_invalid_nan_fail_cli(self):
        fpath = self.root / 'review.json'
        fpath.write_text('{"value":NaN}')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            status = f.main(['--input', str(fpath), '--root', str(self.root)])
        self.assertEqual(status, 2)


if __name__ == '__main__':
    unittest.main()