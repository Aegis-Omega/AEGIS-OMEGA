"""Replace exactly two proof bodies in an exact benchmark snapshot."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys

HERE = Path(__file__).resolve().parent
root = Path(sys.argv[1]).resolve()
expected = '7a41db3d761324599812d6ca6cb6a9f311046dc7'
actual = subprocess.check_output(['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip()
if actual != expected:
    raise SystemExit(f'Benchmark mismatch: {actual}')
p = root / 'FormalConjectures/Wikipedia/Pell.lean'
original = p.read_text()
updated = original
names = ['pellNumber_sq_add_pellNumber_succ_sq', 'coe_pellNumber_eq']
for name, source in zip(names, ['PellIdentity.proof', 'PellBinet.proof']):
    start = updated.index('theorem ' + name)
    end = updated.index('\n  sorry', start)
    body = (HERE / source).read_text().rstrip()
    if 'sorry' in body or 'native_decide' in body:
        raise SystemExit('Forbidden proof placeholder or native trust shortcut')
    updated = updated[:end] + '\n' + body + updated[end + len('\n  sorry'):]
p.write_text(updated)
(root / 'AegisAudit.lean').write_text((HERE / 'Audit.lean').read_text())
print(json.dumps({'benchmark_commit': actual, 'original_pell_sha256': hashlib.sha256(original.encode()).hexdigest(),
                  'patched_pell_sha256': hashlib.sha256(updated.encode()).hexdigest(),
                  'replaced_proof_bodies': names, 'statement_changes': 0}))
