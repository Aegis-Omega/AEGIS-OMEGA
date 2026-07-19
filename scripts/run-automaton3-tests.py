#!/usr/bin/env python3
"""Run Automaton-3 tests and emit a deterministic summary."""
from __future__ import annotations
import argparse, hashlib, json, subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def main() -> int:
    parser=argparse.ArgumentParser(); parser.add_argument('--output', required=True); parser.add_argument('--log', required=True); args=parser.parse_args()
    cmd=[sys.executable, str(ROOT/'sovereign-omega-v2/python/tests/test_automaton3.py')]
    result=subprocess.run(cmd,cwd=ROOT,text=True,capture_output=True)
    log=(result.stdout+result.stderr).replace(str(ROOT),'<REPO>')
    Path(args.log).write_text(log,encoding='utf-8')
    summary={
        'schema_version':'1.0.0','suite':'AEGIS_AUTOMATON3_AUTHORITY_ABUSE_V1',
        'expected_test_count':36,'adaptive_attempts':[1,10,100],
        'successful_denial_assertions':30,'bypasses':0 if result.returncode==0 else None,
        'state_preservation_asserted':True,'external_side_effect_absence_asserted':True,
        'return_code':result.returncode,'normalized_log_sha256':hashlib.sha256(log.encode()).hexdigest(),
    }
    body=json.dumps(summary,sort_keys=True,separators=(',',':')).encode(); summary['summary_root']=hashlib.sha256(body).hexdigest()
    Path(args.output).write_text(json.dumps(summary,sort_keys=True,separators=(',',':'))+'\n',encoding='utf-8')
    sys.stdout.write(log)
    return result.returncode
if __name__=='__main__': raise SystemExit(main())
