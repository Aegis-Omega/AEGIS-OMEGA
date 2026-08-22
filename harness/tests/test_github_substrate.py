from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from harness.sdk.github_substrate import (
    build_manifest,
    classify_action_ref,
    scan_workflow_text,
    validate_manifest,
)


WORKFLOW = r'''name: Example Agent Runtime
on:
  pull_request:
  workflow_dispatch:
permissions:
  contents: read
  id-token: write
  models: read
jobs:
  run:
    runs-on: [self-hosted, linux, gpu]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/ai-inference@v1
      - uses: actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6
      - uses: actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02
'''


class GitHubSubstrateTests(unittest.TestCase):
    def test_runner_requirement_is_not_live_runner_inventory(self):
        surface = scan_workflow_text('.github/workflows/example.yml', WORKFLOW)
        self.assertEqual(surface.declared_runner_requirements, ['gpu', 'linux', 'self-hosted'])
        self.assertFalse(hasattr(surface, 'live_runners'))

    def test_action_ref_classification_distinguishes_mutable_from_commit(self):
        self.assertEqual(classify_action_ref('actions/checkout@v4'), 'MUTABLE_REF')
        self.assertEqual(
            classify_action_ref('actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683'),
            'IMMUTABLE_COMMIT',
        )

    def test_retired_github_models_surface_is_detected(self):
        surface = scan_workflow_text('.github/workflows/example.yml', WORKFLOW)
        self.assertIn('RETIRED_GITHUB_MODELS_SURFACE', surface.findings)
        self.assertIn('github-models-retired', surface.provider_model_surfaces)

    def test_workflow_surface_extracts_triggers_permissions_and_execution_features(self):
        surface = scan_workflow_text('.github/workflows/example.yml', WORKFLOW)
        self.assertEqual(surface.name, 'Example Agent Runtime')
        self.assertEqual(surface.triggers, ['pull_request', 'workflow_dispatch'])
        self.assertEqual(
            surface.permissions,
            {'contents': 'read', 'id-token': 'write', 'models': 'read'},
        )
        self.assertTrue(surface.uses_oidc)
        self.assertTrue(surface.uses_attestations)
        self.assertTrue(surface.uses_artifacts)
        refs = {dep.reference: dep.pin_class for dep in surface.action_dependencies}
        self.assertEqual(refs['actions/checkout@v4'], 'MUTABLE_REF')
        self.assertEqual(
            refs['actions/attest@1e69f48acb82d1966a394da916b4c1698aa569d6'],
            'IMMUTABLE_COMMIT',
        )

    def test_historical_workflow_observation_never_becomes_current_tree_workflow(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'current.yml').write_text('name: Current\njobs:\n  x:\n    runs-on: ubuntu-latest\n', encoding='utf-8')
            manifest = build_manifest(
                root,
                candidate_sha='abc123',
                historical_observations=[
                    {
                        'workflow_path': '.github/workflows/smoke-test-provider-agnostic.yml',
                        'source': 'operator-screenshot',
                        'observed_as': 'HISTORICAL_WORKFLOW_UI',
                    }
                ],
            )
        current_paths = [item['path'] for item in manifest['current_tree_workflows']]
        self.assertEqual(current_paths, ['.github/workflows/current.yml'])
        self.assertEqual(
            manifest['historical_workflow_observations'][0]['workflow_path'],
            '.github/workflows/smoke-test-provider-agnostic.yml',
        )
        self.assertNotIn('.github/workflows/smoke-test-provider-agnostic.yml', current_paths)

    def test_registered_runner_inventory_is_explicitly_not_checked(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'gpu.yml').write_text(
                'name: GPU\njobs:\n  x:\n    runs-on: [self-hosted, linux, gpu]\n',
                encoding='utf-8',
            )
            manifest = build_manifest(root, candidate_sha='subject-sha')
        self.assertEqual(manifest['candidate_sha'], 'subject-sha')
        self.assertEqual(manifest['registered_runner_inventory_status'], 'NOT_CHECKED')
        self.assertEqual(
            manifest['authority'],
            'EVIDENCE_ONLY_NOT_RUNNER_REGISTRATION_AUTHORITY',
        )

    def test_manifest_is_deterministic_and_current_paths_sorted(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'z.yml').write_text('name: Z\njobs:\n  x:\n    runs-on: ubuntu-latest\n', encoding='utf-8')
            (workflows / 'a.yaml').write_text('name: A\njobs:\n  x:\n    runs-on: windows-latest\n', encoding='utf-8')
            one = build_manifest(root, candidate_sha='same')
            two = build_manifest(root, candidate_sha='same')
        self.assertEqual(one, two)
        self.assertEqual(
            [item['path'] for item in one['current_tree_workflows']],
            ['.github/workflows/a.yaml', '.github/workflows/z.yml'],
        )

    def test_validator_blocks_current_retired_github_models_surface(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'summary.yml').write_text(WORKFLOW, encoding='utf-8')
            manifest = build_manifest(root, candidate_sha='subject')
        result = validate_manifest(manifest)
        self.assertIn(
            'RETIRED_GITHUB_MODELS_SURFACE:.github/workflows/summary.yml',
            result['violations'],
        )

    def test_validator_reports_inherited_mutable_authority_actions_as_debt(self):
        text = '''name: Deploy\npermissions:\n  contents: write\njobs:\n  x:\n    runs-on: ubuntu-latest\n    steps:\n      - uses: actions/checkout@v4\n'''
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            workflows = root / '.github' / 'workflows'
            workflows.mkdir(parents=True)
            (workflows / 'deploy.yml').write_text(text, encoding='utf-8')
            manifest = build_manifest(root, candidate_sha='subject')
        result = validate_manifest(manifest)
        self.assertIn(
            'MUTABLE_ACTION_REF_AUTHORITY_SENSITIVE:.github/workflows/deploy.yml',
            result['warnings'],
        )


if __name__ == '__main__':
    unittest.main()
