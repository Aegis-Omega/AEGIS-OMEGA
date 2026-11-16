"""Regression tests for schur_mid.py and cert_congr.py (run: python -I tests/test_certifiers.py [--real]).

Includes the counterexample from the OPTIMUS V2 audit: A_M = [[1, M], [M, M^2 + 1]], M = 1e14. Both Cholesky pivots
of A_M are exactly 1, yet det(A_M - eps I) = 1 - eps (M^2 + 2) + eps^2 < 0 for eps >= ~1e-28. A checker that compared
the smallest pivot with the radius would accept eps = 1e-28; both checkers must reject it, and must still accept
eps = 5e-29 (every member of that interval matrix is PD).
"""
import json, os, shutil, subprocess, sys, tempfile
from fractions import Fraction as F

HERE = os.path.dirname(os.path.abspath(__file__)); SRC = None
INP = os.path.join(HERE, '..', 'inputs_L18')
PY = sys.executable; ok_all = True


def ball(x, r='0'): return [f'[{x} +/- {r}]' if r != '0' else str(x), '0']


def write_blocks(d, A, G=None, C=None, name='b.json'):
    k = len(A); Z = [[ball(0)] * k for _ in range(k)]
    json.dump({'A11': A, 'G11': G or Z, 'CB': C or Z}, open(os.path.join(d, name), 'w')); return os.path.join(d, name)


def manifest(d, blocks, c_inf='0.97991957971', m='1.05'):
    import hashlib
    h = lambda p: hashlib.sha256(open(p, 'rb').read()).hexdigest()
    for f in ('trace_arb.json', 'krein_slack.log'): shutil.copy(os.path.join(INP, f), d)
    mf = {'blocks': os.path.basename(blocks), 'blocks_sha256': h(blocks), 'c_inf': c_inf,
          'c_inf_source': {'trace_arb': 'trace_arb.json', 'trace_arb_sha256': h(os.path.join(d, 'trace_arb.json')),
                           'krein_log': 'krein_slack.log', 'krein_log_sha256': h(os.path.join(d, 'krein_slack.log')), 'm': m}}
    json.dump(mf, open(os.path.join(d, 'm.json'), 'w')); return os.path.join(d, 'm.json')


def run(args, want, label):
    global ok_all
    p = subprocess.run([PY, '-I', SRC] + args, capture_output=True, text=True, timeout=3600)
    good = p.returncode == want; ok_all &= good
    print(('PASS' if good else 'FAIL') + f'  {label}: exit {p.returncode} (want {want})  {p.stdout.strip().splitlines()[-1][:110] if p.stdout.strip() else p.stderr[-200:]}')


def AM(eps):
    M = 10 ** 14; e = '0' if eps == 0 else eps
    return [[ball(1, e), ball(M)], [ball(M), ball(M * M + 1, e)]]


# exact facts behind the counterexample
M = 10 ** 14; det = lambda e: (1 - e) * (M * M + 1 - e) - M * M
assert det(F(1, 10 ** 28)) < 0 < det(F(5, 10 ** 29)), 'counterexample arithmetic'
print('exact: det(A_M - 1e-28 I) =', float(det(F(1, 10 ** 28))), ' det(A_M - 5e-29 I) =', float(det(F(5, 10 ** 29))))

t = tempfile.mkdtemp(prefix='certifier_test_')
try:
    for SRC in (os.path.join(HERE, '..', 'src', 'schur_mid.py'), os.path.join(HERE, '..', 'src', 'cert_congr.py')):
        print('==', os.path.basename(SRC))
        for eps, want in ((0, 0), ('5e-29', 0), ('1e-28', 1), ('2e-28', 1)):
            d = tempfile.mkdtemp(dir=t); run(['--manifest', manifest(d, write_blocks(d, AM(eps))), '0'], want, f'A_M, diagonal radius {eps}')
        d = tempfile.mkdtemp(dir=t); run(['--manifest', manifest(d, write_blocks(d, AM(0)), c_inf='1000'), '0'], 2, 'c_inf = 1000 (unbound)')
        d = tempfile.mkdtemp(dir=t); run(['--manifest', manifest(d, write_blocks(d, AM(0)), m='1.2'), '0'], 2, 'Krein m not certified')
        d = tempfile.mkdtemp(dir=t); mf = manifest(d, write_blocks(d, AM(0)))
        write_blocks(d, AM('1e-28')); run(['--manifest', mf, '0'], 2, 'blocks changed after manifest')
        d = tempfile.mkdtemp(dir=t); A = AM(0); A[0][1] = ball(M + 1)
        run(['--manifest', manifest(d, write_blocks(d, A)), '0'], 2, 'asymmetric S')
        d = tempfile.mkdtemp(dir=t)
        if SRC.endswith('schur_mid.py'): run([write_blocks(d, AM(0)), '1', '0'], 3, 'experiment mode never exits 0')
        else: run([write_blocks(d, AM(0)), '1', '0'], 2, 'no experiment mode (manifest required)')
        if '--real' in sys.argv:
            mf = os.path.join(HERE, '..', 'manifests', 'L18_even_renorm_g0.json')
            run(['--manifest', mf, '4.23e-17'], 0, 'L=9/5 even sector, mu = 4.23e-17')
            run(['--manifest', mf, '4.24e-17'], 1, 'L=9/5 even sector, mu = 4.24e-17')
finally:
    shutil.rmtree(t)
print('ALL PASS' if ok_all else 'SOME FAILED'); sys.exit(0 if ok_all else 1)
