import contextlib, importlib.util, io, pathlib, subprocess, sys, unittest
from unittest.mock import patch
SOURCE=pathlib.Path(__file__).parent/'contribution.py'
spec=importlib.util.spec_from_file_location('aegis_contribution',SOURCE)
mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
class ContributionTruth(unittest.TestCase):
    def test_git_failure_must_not_return_empty_success(self):
        bad=subprocess.CompletedProcess(['git','fetch'],128,'','fatal: could not resolve host')
        with patch.object(mod.subprocess,'run',return_value=bad):
            with self.assertRaises(RuntimeError):mod.git('fetch','origin','main')
    def test_human_coauthor_not_model(self):
        self.assertEqual(mod.agent_of('Co-Authored-By: Alice Smith <a@example.com>',[]),'unattributed')
    def test_claims_are_not_presented_as_verified_identity(self):
        with patch.object(mod,'git',side_effect=['','', '', '']),patch.object(sys,'argv',['contribution.py']):
            with io.StringIO() as buf, contextlib.redirect_stdout(buf):
                mod.main();out=buf.getvalue()
        self.assertIn('unverified',out.lower())
    def test_model_coauthor_still_detected(self):
        self.assertEqual(mod.agent_of('Co-Authored-By: Claude Opus <x@example.com>',[]),'Claude Opus')
        self.assertEqual(mod.agent_of('Co-Authored-By: GPT-6 <x@example.com>',[]),'GPT-6')
    def test_valid_git_output_not_modified(self):
        good=subprocess.CompletedProcess(['git','log'],0,'abc\n','')
        with patch.object(mod.subprocess,'run',return_value=good):
            self.assertEqual(mod.git('log','--format=%H'),'abc\n')
if __name__=='__main__':unittest.main()
