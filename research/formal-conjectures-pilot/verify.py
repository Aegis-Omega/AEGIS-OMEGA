"""Fail closed on unexpected dependencies in the three target proof terms."""
import json
from pathlib import Path
import re
import sys

log = Path(sys.argv[1]).read_text()
names = ['PellNumbers.pellNumber_sq_add_pellNumber_succ_sq',
         'PellNumbers.coe_pellNumber_eq', 'AegisBench.green72_bound_counterexample']
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
print(json.dumps({'results': results, 'rh_status': 'NOT_PROVEN', 'authority_effect': 'NONE'}, indent=2))
