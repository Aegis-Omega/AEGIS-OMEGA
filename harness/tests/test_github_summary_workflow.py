from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[2]
SUMMARY = ROOT / '.github' / 'workflows' / 'summary.yml'


class GitHubSummaryWorkflowTests(unittest.TestCase):
    def test_summary_keeps_issue_comment_function_without_retired_github_models(self):
        text = SUMMARY.read_text(encoding='utf-8')
        self.assertIn('issues:', text)
        self.assertIn('types: [opened]', text)
        self.assertIn('issues: write', text)
        self.assertIn("if: vars.PROXY_URL != ''", text)
        self.assertIn('PROXY_URL: ${{ vars.PROXY_URL }}', text)
        self.assertIn('ISSUE_TITLE: ${{ github.event.issue.title }}', text)
        self.assertIn('ISSUE_BODY: ${{ github.event.issue.body }}', text)
        self.assertIn('jq -n', text)
        self.assertIn('github_issue_opened', text)
        self.assertIn('gh issue comment', text)
        self.assertNotIn('models: read', text)
        self.assertNotIn('actions/ai-inference', text)
        self.assertNotIn('actions/checkout@', text)

    def test_untrusted_issue_text_is_passed_via_environment_not_inline_shell_expression(self):
        text = SUMMARY.read_text(encoding='utf-8')
        run_section = text.split('run: |', 1)[1]
        self.assertNotIn('${{ github.event.issue.title }}', run_section)
        self.assertNotIn('${{ github.event.issue.body }}', run_section)
        self.assertIn('--arg title "$ISSUE_TITLE"', run_section)
        self.assertIn('--arg body "$ISSUE_BODY"', run_section)


if __name__ == '__main__':
    unittest.main()
