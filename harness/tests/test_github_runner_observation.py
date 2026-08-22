from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.sdk.github_substrate import build_manifest, build_runner_observation


class GitHubRunnerObservationTests(unittest.TestCase):
    def test_runner_observation_is_exact_run_bound_and_not_registration_authority(self):
        observation = build_runner_observation(
            candidate_sha='abc123',
            run_id='42',
            run_attempt='1',
            job='aegis / github-substrate-census',
            runner_name='GitHub Actions 7',
            runner_os='Linux',
            runner_arch='X64',
            runner_environment='github-hosted',
        )
        self.assertEqual(observation['observation_kind'], 'EXECUTED_RUNNER_OBSERVATION_V1')
        self.assertEqual(observation['candidate_sha'], 'abc123')
        self.assertEqual(observation['workflow_run_id'], '42')
        self.assertEqual(observation['runner_environment'], 'github-hosted')
        self.assertEqual(observation['authority'], 'EXECUTED_RUN_EVIDENCE_NOT_RUNNER_REGISTRATION_AUTHORITY')

    def test_manifest_keeps_executed_observation_separate_from_registered_inventory(self):
        observation = build_runner_observation(
            candidate_sha='subject',
            run_id='77',
            run_attempt='2',
            job='job',
            runner_name='runner',
            runner_os='Linux',
            runner_arch='ARM64',
            runner_environment='self-hosted',
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'x.yml').write_text(
                'name: X\njobs:\n  x:\n    runs-on: [self-hosted, linux, arm64]\n',
                encoding='utf-8',
            )
            manifest = build_manifest(
                root,
                candidate_sha='subject',
                executed_runner_observations=[observation],
            )
        self.assertEqual(manifest['registered_runner_inventory_status'], 'NOT_CHECKED')
        self.assertEqual(manifest['executed_runner_observations'], [observation])
        self.assertIn('self-hosted', manifest['declared_runner_requirements'])

    def test_runner_observation_rejects_subject_mismatch(self):
        observation = build_runner_observation(
            candidate_sha='other',
            run_id='77',
            run_attempt='1',
            job='job',
            runner_name='runner',
            runner_os='Linux',
            runner_arch='X64',
            runner_environment='github-hosted',
        )
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / '.github' / 'workflows').mkdir(parents=True)
            with self.assertRaises(ValueError):
                build_manifest(
                    root,
                    candidate_sha='subject',
                    executed_runner_observations=[observation],
                )


if __name__ == '__main__':
    unittest.main()
