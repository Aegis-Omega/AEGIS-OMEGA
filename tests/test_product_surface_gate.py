"""Pure tests for the production UI surface gate; no Internet and no credentials."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from product_surface_gate import inspect_html, verify  # noqa: E402


class ProductSurfaceGateTest(unittest.TestCase):
    def test_valid_picker(self):
        h = '<title>Platform Picker — AI</title><script type="module" src="/assets/index-xyz.js"></script>'
        x = inspect_html(h, "Platform Picker", "https://platform.aegisomega.com/")
        self.assertTrue(x["ok"])
        self.assertEqual(x["bundle_url"], "https://platform.aegisomega.com/assets/index-xyz.js")

    def test_wrong_app_on_valid_domain(self):
        h = '<title>AEGIS-Ω — The AI system that governs itself.</title><script src="/assets/index.js"></script>'
        self.assertEqual(inspect_html(h, "Platform Picker", "https://platform.aegisomega.com/")["code"], "WRONG_PRODUCT")

    def test_auth_screen(self):
        h = '<title>Protected Deployment – Vercel</title>'
        self.assertEqual(inspect_html(h, "Hook Generator", "https://hooks.aegisomega.com/")["code"], "DEPLOYMENT_PROTECTED")

    def test_missing_bundle(self):
        self.assertEqual(inspect_html('<title>Hook Generator — AI</title>', "Hook Generator", "https://hooks.aegisomega.com/")["code"], "BUNDLE_REFERENCE_INVALID")

    def test_off_site_bundle(self):
        h = '<title>Hook Generator — AI</title><script src="https://other.example/assets/x.js"></script>'
        self.assertEqual(inspect_html(h, "Hook Generator", "https://hooks.aegisomega.com/")["code"], "CROSS_ORIGIN_BUNDLE")

    def test_two_projects_same_bundle_fail(self):
        xs = [{"product": x, "ok": True, "bundle_sha256": "1" * 64} for x in ("platform-picker", "hook-generator")]
        self.assertFalse(verify(xs))
        self.assertEqual(xs[0]["code"], "IDENTICAL_BUNDLE_FOR_DISTINCT_PRODUCTS")

    def test_distinct_bundles_pass(self):
        xs = [{"product": "platform-picker", "ok": True, "bundle_sha256": "a" * 64}, {"product": "hook-generator", "ok": True, "bundle_sha256": "b" * 64}]
        self.assertTrue(verify(xs))

    def test_incomplete_probe_fail(self):
        self.assertFalse(verify([{"product": "platform-picker", "ok": True, "bundle_sha256": "a" * 64}]))


if __name__ == "__main__":
    unittest.main()
