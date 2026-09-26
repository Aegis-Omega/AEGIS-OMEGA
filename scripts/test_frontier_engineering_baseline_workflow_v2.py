from pathlib import Path
import unittest
S=(Path(__file__).parents[1]/".github/workflows/frontier-engineering-baseline.yml").read_text()
class T(unittest.TestCase):
 def test_exact_checkout_pinned(self):
  self.assertIn("actions/checkout@11d5960a326750d5838078e36cf38b85af677262",S)
 def test_receipt_uploaded_on_failure_path(self):
  self.assertIn("if: always()",S)
  self.assertIn("FRONTIER_ENGINEERING_BASELINE_V2.json",S)
  self.assertIn("actions/upload-artifact@ea165f8d65b6e75b540449e92b4886f43607fa02",S)
 def test_final_gate_uses_verifier_rc(self):
  self.assertIn('test "${{ steps.baseline.outputs.rc }}" = "0"',S)
if __name__=="__main__":unittest.main(verbosity=2)