"""Ensure Azure Pipelines stays manual, non-deploying and credential-free."""
import pathlib
import re
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
PIPELINE = ROOT / 'azure-pipelines.yml'


class AzurePipelineContractTest(unittest.TestCase):
    def setUp(self):
        self.source = PIPELINE.read_text(encoding='utf-8')

    def test_never_auto_triggers(self):
        self.assertRegex(self.source, r'(?m)^trigger: none\s*$')
        self.assertRegex(self.source, r'(?m)^pr: none\s*$')

    def test_no_provisioning_or_deployment_tasks(self):
        self.assertNotRegex(
            self.source,
            r'(?im)^\s*(?:-\s*)?(?:deployment:|environment:|azureSubscription:|'
            r'(?:task:\s*)?(?:AzureCLI|AzurePowerShell|AzureResourceManagerTemplateDeployment)@)'
        )

    def test_read_only_checkout_without_persisted_credentials(self):
        self.assertIn('- checkout: self', self.source)
        self.assertRegex(self.source, r'persistCredentials:\s*false')

    def test_existing_offline_regressions_are_invoked(self):
        for snippet in (
            'test_devcontainer_config.py',
            'test/unit/provider-mesh.test.ts',
            'test/unit/provider-federation.test.ts',
            'test/unit/chat-provider-gate.test.ts',
            'test/unit/provider-azure-devops.test.ts',
            'npm run typecheck',
        ):
            self.assertIn(snippet, self.source)


if __name__ == '__main__':
    unittest.main()
