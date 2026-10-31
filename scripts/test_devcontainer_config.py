"""Regression tests for the existing AEGIS Codespaces devcontainer configuration."""
import json
import pathlib
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
CONFIG = ROOT / '.devcontainer' / 'devcontainer.json'


class CodespacesConfigTests(unittest.TestCase):
    def test_strict_valid_json(self):
        conf = json.loads(CONFIG.read_text(encoding='utf-8'))
        self.assertIsInstance(conf, dict)
        self.assertIsInstance(conf.get('image'), str)
        self.assertTrue(conf['image'].strip())

    def test_aws_cli_feature_is_nested_under_features(self):
        conf = json.loads(CONFIG.read_text(encoding='utf-8'))
        features = conf.get('features')
        self.assertIsInstance(features, dict)
        self.assertEqual(features.get('ghcr.io/devcontainers/features/aws-cli:1'), {})


if __name__ == '__main__':
    unittest.main()
