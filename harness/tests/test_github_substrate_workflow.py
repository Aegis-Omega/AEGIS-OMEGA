from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
WORKFLOW = ROOT / '.github' / 'workflows' / 'github-substrate-census.yml'
INVENTORY = ROOT / 'scripts' / 'inventory-github-substrate.py'
VALIDATOR = ROOT / 'scripts' / 'validate-github-substrate.py'


class GitHubSubstrateWorkflowTests(unittest.TestCase):
    def test_dedicated_census_workflow_exists(self):
        self.assertTrue(WORKFLOW.is_file(), 'github-substrate-census.yml must exist')

    def test_census_workflow_is_exact_head_least_authority_and_immutable(self):
        self.assertTrue(WORKFLOW.is_file(), 'github-substrate-census.yml must exist')
        text = WORKFLOW.read_text(encoding='utf-8')
        self.assertIn('CANDIDATE_SHA:', text)
        self.assertIn('ref: ${{ env.CANDIDATE_SHA }}', text)
        self.assertIn('permissions:\n  contents: read', text)
        self.assertNotIn('id-token: write', text)
        self.assertNotIn('attestations: write', text)
        self.assertNotIn('artifact-metadata: write', text)
        self.assertIn(
            'actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683',
            text,
        )
        self.assertNotIn('actions/checkout@v4', text)
        self.assertIn('scripts/inventory-github-substrate.py', text)
        self.assertIn('scripts/validate-github-substrate.py', text)

    def test_cli_entrypoints_exist(self):
        self.assertTrue(INVENTORY.is_file(), 'inventory CLI must exist')
        self.assertTrue(VALIDATOR.is_file(), 'validator CLI must exist')


if __name__ == '__main__':
    unittest.main()
