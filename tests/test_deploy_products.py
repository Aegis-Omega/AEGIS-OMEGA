"""Execute the real release shell against isolated fake npm/vercel commands."""
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/deploy-products.sh'

class ReleaseTests(unittest.TestCase):
    def run_release(self, extra=None):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root/'scripts').mkdir(); (root/'bin').mkdir()
            shutil.copy(SCRIPT, root/'scripts/deploy-products.sh')
            (root/'scripts/prepare-deployment.sh').write_text('#!/bin/bash\nexit 0\n')
            (root/'scripts/product_surface_gate.py').write_text('import os,sys\nsys.exit(int(os.environ.get("GATE_EXIT", "0")))\n')
            for name in ['hub','platform-picker','hook-generator','content-calendar','packages/shared']:
                (root/name).mkdir(parents=True)
                (root/name/'package-lock.json').write_text('{}')
            for name in ['npm','vercel']:
                p=root/'bin'/name
                p.write_text('#!/bin/bash\nprintf "%s\\n" "'+name+' $*" >> "$CALL_LOG"\n'
                             'if [[ "${1:-}" == "--prod" ]]; then exit "${DEPLOY_EXIT:-0}"; fi\n'
                             + ('exit "${NPM_EXIT:-0}"\n' if name=='npm' else 'exit 0\n'))
                p.chmod(0o755)
            env={k:v for k,v in os.environ.items() if not k.startswith('VITE_')}
            env.update(PATH=str(root/'bin')+':'+env['PATH'], CALL_LOG=str(root/'calls'))
            env.update(extra or {})
            result=subprocess.run(['bash',str(root/'scripts/deploy-products.sh')],env=env,capture_output=True,text=True)
            calls=(root/'calls').read_text() if (root/'calls').exists() else ''
            return result,calls

    def test_release_never_forwards_provider_secret(self):
        r,c=self.run_release({'DASHSCOPE_KEY':'TEST_SECRET_SENTINEL'})
        self.assertEqual(r.returncode,0,r.stderr)
        self.assertEqual(c.count('vercel --prod --yes'),4)
        self.assertNotIn('TEST_SECRET_SENTINEL',c+r.stdout+r.stderr)
        self.assertNotIn('VITE_DASHSCOPE_API_KEY=',c)
        self.assertIn('All products deployed!',r.stdout)

    def test_public_provider_key_stops_before_build_or_deploy(self):
        r,c=self.run_release({'VITE_DASHSCOPE_API_KEY':'TEST_SECRET_SENTINEL'})
        self.assertNotEqual(r.returncode,0)
        self.assertNotIn('npm ',c); self.assertNotIn('--prod',c)
        self.assertNotIn('TEST_SECRET_SENTINEL',r.stdout+r.stderr)

    def test_failed_build_does_not_deploy(self):
        r,c=self.run_release({'NPM_EXIT':'1'})
        self.assertNotEqual(r.returncode,0); self.assertNotIn('--prod',c)

    def test_failed_upload_never_claims_complete(self):
        r,c=self.run_release({'DEPLOY_EXIT':'1'})
        self.assertNotEqual(r.returncode,0); self.assertNotIn('All products deployed!',r.stdout)

    def test_wrong_public_surface_never_claims_complete(self):
        r,c=self.run_release({'GATE_EXIT':'1'})
        self.assertNotEqual(r.returncode,0); self.assertNotIn('All products deployed!',r.stdout)

if __name__=='__main__': unittest.main()
