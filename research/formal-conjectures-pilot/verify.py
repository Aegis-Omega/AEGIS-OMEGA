"""Fail closed on unexpected dependencies in the selected target proof terms."""
import hashlib
import json
import os
import subprocess
from pathlib import Path
import re
import sys

log = Path(sys.argv[1]).read_text()
names = ['PellNumbers.pellNumber_sq_add_pellNumber_succ_sq',
         'PellNumbers.coe_pellNumber_eq', 'AegisBench.green72_bound_counterexample',
         'AegisBench.transcendental_sum_or_product',
         'AegisBench.pi_exp_sum_or_product_of_transcendental_pi',
         'AegisBench.Vega.bfs_false_positive',
         'AegisBench.Vega.missing_margin_counterexample',
         'AegisBench.Vega.balance_counts', 'AegisBench.Vega.run_balance_binding',
         'AegisBench.Vega.checkClauses_correct', 'AegisBench.Vega.reciprocal_margin_iff']
allowed = {'propext', 'Classical.choice', 'Quot.sound'}
results = {}
for name in names:
    match = re.search(re.escape("'" + name + "' depends on axioms:") + r'\s*\[([^\]]*)\]', log)
    if not match:
        raise SystemExit(f'Missing axiom report: {name}')
    axioms = {a.strip() for a in match[1].split(',') if a.strip()}
    if not axioms <= allowed:
        raise SystemExit(f'Unapproved axioms in {name}: {axioms - allowed}')
    results[name] = {'status': 'KERNEL_CHECKED', 'axioms': sorted(axioms)}
root = Path(sys.argv[2]).resolve()
def git_head(path):
    return subprocess.check_output(['git', '-C', str(path), 'rev-parse', 'HEAD'], text=True).strip()
benchmark_sha = git_head(root)
mathlib_sha = git_head(root / '.lake/packages/mathlib')
if benchmark_sha != '7a41db3d761324599812d6ca6cb6a9f311046dc7':
    raise SystemExit('Wrong benchmark revision')
if mathlib_sha != 'a3a10db0e9d66acbebf76c5e6a135066525ac900':
    raise SystemExit('Wrong mathlib revision')
if (root / 'lean-toolchain').read_text().strip() != 'leanprover/lean4:v4.27.0':
    raise SystemExit('Wrong Lean toolchain specification')
paths = ['FormalConjectures/Wikipedia/Pell.lean',
         'FormalConjectures/GreensOpenProblems/72.lean', 'AegisAudit.lean',
         'lean-toolchain', 'lake-manifest.json']
print(json.dumps({'schema': 'AEGIS_FORMAL_CONJECTURES_PILOT_V1',
    'candidate_sha': os.environ.get('GITHUB_SHA'), 'run_id': os.environ.get('GITHUB_RUN_ID'),
    'benchmark_sha': benchmark_sha, 'mathlib_sha': mathlib_sha,
    'source_sha256': {p: hashlib.sha256((root / p).read_bytes()).hexdigest() for p in paths},
    'axiom_log_sha256': hashlib.sha256(Path(sys.argv[1]).read_bytes()).hexdigest(),
    'results': results,
    'unconditional_pi_exp_benchmark_status': 'NOT_PROVEN',
    'external_astra_receipt_status': 'UNVERIFIED', 'rh_status': 'NOT_PROVEN', 'authority_effect': 'NONE'}, indent=2))
