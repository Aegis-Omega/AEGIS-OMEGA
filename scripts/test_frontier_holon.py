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

    def test_paired_outcome_never_reopens_after_integrity_check(self):
        self.paired()
        # A stale digest cannot protect a second read of mutable path bytes.
        with patch.object(Path, 'read_bytes', side_effect=AssertionError('TOCTOU reopen')):
            receipt = self.audit()
        self.assertEqual(receipt['disposition'], 'CANDIDATE_FOR_INDEPENDENT_REPLAY')
        self.assertFalse(receipt['external_sources_authenticated'])

    def test_outcome_changed_before_pinned_read_rejected(self):
        self.paired()
        (self.root / 'outcome.json').write_text('{"candidate_sha":"altered"}')
        with self.assertRaises(f.InvalidFrontier):
            self.audit()

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

    def test_github_raw_alias_same_publisher_cannot_count_twice(self):
        self.data['sources'][0]['url'] = 'https://github.com/openai/openai-agents-python'
        self.data['sources'][1]['url'] = (
            'https://raw.githubusercontent.com/openai/openai-agents-python/main/README.md')
        self.paired()
        with self.assertRaisesRegex(f.InvalidFrontier, 'publisher groups'):
            self.audit()

    def test_percent_encoded_github_owner_cannot_bypass_duplicate_check(self):
        self.data['sources'][0]['url'] = 'https://github.com/%6fpenai/openai-agents-python'
        self.data['sources'][1]['url'] = 'https://raw.githubusercontent.com/openai/openai-agents-python/main/README.md'
        self.paired()
        with self.assertRaisesRegex(f.InvalidFrontier, 'publisher groups'):
            self.audit()

    def test_github_pages_and_github_repository_same_owner_is_one_source(self):
        self.data['sources'][0]['url'] = 'https://openai.github.io/openai-agents-python/'
        self.data['sources'][1]['url'] = 'https://github.com/openai/openai-agents-python'
        self.paired()
        with self.assertRaisesRegex(f.InvalidFrontier, 'publisher groups'):
            self.audit()

    def test_different_github_owners_remain_distinct_unattested_sources(self):
        self.paired()
        result = self.audit()
        self.assertEqual(result['disposition'], 'CANDIDATE_FOR_INDEPENDENT_REPLAY')
        self.assertEqual(result['source_publisher_groups'],
                         ['github-owner:google', 'github-owner:openai'])
        self.assertIs(result['source_publisher_ownership_authenticated'], False)

    def test_github_gist_and_api_mirrors_are_not_independent_publishers(self):
        self.data['sources'][0]['url'] = 'https://github.com/openai/openai-agents-python'
        self.paired()
        aliases = [
            'https://gist.github.com/openai/abcde',
            'https://gist.githubusercontent.com/openai/abcde/raw/readme.md',
            'https://api.github.com/repos/openai/openai-agents-python',
        ]
        for url in aliases:
            self.data['sources'][1]['url'] = url
            with self.subTest(url=url), self.assertRaisesRegex(
                    f.InvalidFrontier, 'publisher groups'):
                self.audit()

    def test_other_github_api_owner_still_counts_as_distinct_claim(self):
        self.data['sources'][0]['url'] = 'https://github.com/openai/openai-agents-python'
        self.data['sources'][1]['url'] = 'https://api.github.com/repos/google/adk'
        self.paired()
        result = self.audit()
        self.assertEqual(result['source_publisher_groups'],
                         ['github-owner:google', 'github-owner:openai'])
        self.assertFalse(result['source_publisher_ownership_authenticated'])

    def test_unresolvable_github_owner_never_becomes_independent_evidence(self):
        self.paired()
        self.data['sources'][0]['url'] = 'https://raw.githubusercontent.com/openai/repo/main/README.md'
        for url in ('https://github.com/%256fpenai/repo',
                    'https://gist.github.com/',
                    'https://api.github.com/gists/123456'):
            self.data['sources'][1]['url'] = url
            with self.subTest(url=url), self.assertRaisesRegex(
                    f.InvalidFrontier, 'publisher owner cannot be identified'):
                self.audit()

    def test_github_organization_api_alias_matches_same_publisher(self):
        self.paired()
        self.data['sources'][0]['url'] = 'https://github.com/openai/openai-agents-python'
        self.data['sources'][1]['url'] = 'https://api.github.com/orgs/openai'
        with self.assertRaisesRegex(f.InvalidFrontier, 'publisher groups'):
            self.audit()

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

    def test_iana_special_use_https_names_are_not_public_evidence(self):
        # IANA registry and RFC 6761 reserve these and all subdomains.
        invalid = [
            'https://docs.example',
            'https://a.research.invalid',
            'https://a.test',
            'https://a.onion',
            'https://a.alt',
            'https://workflow.home.arpa',
            'https://sample.example.com',
            'https://sample.example.net',
            'https://sample.example.org',
            'https://example.com', 'https://example.net', 'https://example.org',
            'https://localhost.localdomain',
        ]
        for url in invalid:
            with self.subTest(url=url), self.assertRaises(f.InvalidFrontier):
                f.public_https(url)

    def test_real_external_domain_remains_syntactically_valid(self):
        # This proves only URL structure, never that the page was inspected.
        self.assertEqual(
            f.public_https('https://docs.temporal.io/workflow-definition'),
            'docs.temporal.io')
        self.assertEqual(
            f.public_https('https://learn.microsoft.com/en-us/agent-framework/'),
            'learn.microsoft.com')
        self.assertEqual(f.public_https('https://notexample.com/research'), 'notexample.com')

    def test_frontier_receipt_rejects_special_use_second_source(self):
        self.data['sources'][1]['url'] = 'https://research.invalid/claims'
        with self.assertRaises(f.InvalidFrontier):
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

    def test_reject_with_observed_regression_still_records_falsification(self):
        self.paired()
        self.data['decision']['kind'] = 'REJECT'
        self.outcome = {'disposition': 'REGRESSION_OBSERVED', 'paired_cases': 1}
        result = self.audit()
        self.assertEqual(result['disposition'], 'RESEARCH_ONLY_NO_ADOPTION')
        self.assertEqual(result['paired_evaluation_disposition'], 'REGRESSION_OBSERVED')
        self.assertEqual(result['admission'], 'NOT_ADMITTED')

    def test_cli_successful_rejection_is_not_authorization(self):
        self.data['decision']['kind'] = 'REJECT'
        path = self.root / 'reject.json'
        path.write_text(json.dumps(self.data), encoding='utf-8')
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), patch.object(f, 'datetime') as clock:
            clock.now.return_value.date.return_value = self.today
            status = f.main(['--input', str(path), '--root', str(self.root)])
        self.assertEqual(status, 0)
        self.assertEqual(json.loads(buf.getvalue())['admission'], 'NOT_ADMITTED')

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