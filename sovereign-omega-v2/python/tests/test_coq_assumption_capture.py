import os
import shlex
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from coq_attestation import parse_print_assumptions


CAPTURE = Path(__file__).resolve().parents[1] / "coq_assumption_capture.py"


class AssumptionCaptureTests(unittest.TestCase):
    def run_capture(self, body, exit_code=0):
        with tempfile.TemporaryDirectory(prefix="coq capture ") as temporary:
            root = Path(temporary)
            query = root / "query.v"
            query.write_text("Print Assumptions fixture.\n")
            output = root / "assumptions.txt"
            verifier = root / "coqtop"
            verifier.write_text(
                f"#!{sys.executable}\n"
                "import os, sys\n"
                f"assert os.getcwd() == {str(root)!r}\n"
                f"assert sys.argv[1:] == ['-q', '-quiet', '-batch', '-l', {str(query)!r}]\n"
                f"sys.stdout.buffer.write({body!r})\n"
                f"sys.exit({exit_code})\n"
            )
            verifier.chmod(0o755)
            command = [sys.executable, str(CAPTURE), "--query", str(query),
                       "--directory", str(root), "--output", str(output)]
            # Reproduce an action wrapper that traces commands on stdout.
            script = "trap 'printf \"+ action shell trace\\n\"' DEBUG\n" + shlex.join(command)
            result = subprocess.run(
                ["bash", "-c", script], capture_output=True,
                env={**os.environ, "PATH": str(root) + os.pathsep + os.environ["PATH"]},
            )
            self.assertIn(b"+ action shell trace", result.stdout)
            return result, output.read_bytes()

    def test_closed_output_excludes_outer_trace(self):
        raw = b"Closed under the global context\n"
        result, captured = self.run_capture(raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(captured, raw)
        self.assertEqual(parse_print_assumptions(captured.decode())["parse_status"], "CLOSED")

    def test_real_assumption_is_preserved(self):
        raw = b"Axioms:\nHash.sha256 : nat -> nat\n"
        result, captured = self.run_capture(raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(captured, raw)
        self.assertEqual(parse_print_assumptions(captured.decode())["assumption_symbols"], ["Hash.sha256"])

    def test_verifier_failure_remains_failure(self):
        raw = b"Error: reference not found\n"
        result, captured = self.run_capture(raw, exit_code=1)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(captured, raw)

    def test_unexpected_verifier_output_is_not_filtered(self):
        raw = b"+ unexpected verifier output\nClosed under the global context\n"
        result, captured = self.run_capture(raw)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(captured, raw)
        parsed = parse_print_assumptions(captured.decode())
        self.assertEqual(parsed["parse_status"], "UNRECOGNIZED")
        self.assertFalse(parsed["closed_under_global_context"])
