"""Exact-integer certificate of S = A11 - mu G11 - C_B/(c_inf - mu) > 0, independent of Arb's Cholesky.

Soundness uses only integer arithmetic:
  1. every block entry is a printed Arb ball "[m +/- r]" (an enclosure); it is read as exact rationals m, r;
  2. S_mid, S_rad are computed exactly (mu >= 0, d = c_inf - mu > 0 rational), scaled by 2^s and rounded outward:
     2^s S_true lies entrywise in Sm +/- R (integers, lower triangle mirrored; the two triangles must overlap);
  3. T is ANY lower-triangular integer matrix with positive diagonal (so invertible). Here it is round(2^t L^-1) for
     L an approximate 320-bit Cholesky factor of S_mid, but T is untrusted: only steps 4-5 decide;
  4. D = T Sm T^T and W = |T| R |T|^T exactly (FLINT fmpz_mat), so 2^s T S_true T^T lies entrywise in D +/- W;
  5. if D_ii - W_ii > sum_{j != i} (|D_ij| + W_ij) for every i, every symmetric matrix in that box is strictly
     diagonally dominant with positive diagonal, hence positive definite (Gershgorin); so T S T^T > 0 and S > 0.
c_inf is bound as in schur_mid.py: c_inf <= m_lower - trPTP_upper, computed exactly from the printed balls.

usage: cert_congr.py --manifest manifest.json mu...   exit 0 iff every mu is CERTIFIED, 1 if one fails, 2 if blocked.
"""
import sys, json, hashlib, os, re
from fractions import Fraction as F
from flint import arb, arb_mat, fmpz_mat, ctx

S_BITS, T_BITS = 160, 64


def blocked(msg):
    print('BLOCKED: ' + msg, flush=True); sys.exit(2)


def sha256(path):
    with open(path, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()


BALL = re.compile(r'^\[\s*(?:([-+0-9.eE]+)\s*)?\+/-\s*([0-9.eE+-]+)\s*\]$')
def ball(s):   # printed Arb ball or exact decimal -> (mid, rad) as exact rationals
    s = s.strip(); m = BALL.match(s)
    if m: return F(m.group(1) or 0), F(m.group(2))
    return F(s), F(0)


if len(sys.argv) < 4 or sys.argv[1] != '--manifest': print(__doc__); sys.exit(2)
mf = sys.argv[2]; base = os.path.dirname(os.path.abspath(mf)); mus = sys.argv[3:]
Mn = json.load(open(mf)); src = Mn['c_inf_source']
p = lambda k: os.path.join(base, Mn[k]); q = lambda k: os.path.join(base, src[k])
if sha256(p('blocks')) != Mn['blocks_sha256']: blocked('blocks sha256 mismatch')
if sha256(q('trace_arb')) != src['trace_arb_sha256']: blocked('trace_arb sha256 mismatch')
if sha256(q('krein_log')) != src['krein_log_sha256']: blocked('krein_log sha256 mismatch')
mlines = [l.split('m = ', 1)[1].strip() for l in open(q('krein_log')) if l.startswith('CERTIFIED: F(xi) >= 0 for all real xi, m = ')]
if not mlines: blocked('krein log has no CERTIFIED line')
mm, mr = ball(mlines[-1])
if abs(mm - F(src['m'])) > mr: blocked('krein log does not certify m = ' + src['m'])
tm, tr = ball(json.load(open(q('trace_arb')))['trPTP_upper'])
cinf = F(Mn['c_inf']); bound = (mm - mr) - (tm + tr)
if not cinf <= bound: blocked(f"c_inf {Mn['c_inf']} > m - trPTP_upper = {float(bound)!r}")

P = json.load(open(p('blocks')))
def M(name):
    out = []
    for row in P[name]:
        r_ = []
        for re_, im in row:
            if ball(im) != (0, 0): blocked(name + ': imaginary part not exactly 0')
            r_.append(ball(re_))
        out.append(r_)
    return out
A, G, C = M('A11'), M('G11'), M('CB'); k = len(A)


def cert(mu_s):
    mu = F(mu_s); d = cinf - mu
    if not (mu >= 0 and d > 0): blocked('need 0 <= mu < c_inf')
    sc = 1 << S_BITS
    Sm = [[0] * k for _ in range(k)]; R = [[0] * k for _ in range(k)]; mids = [[F(0)] * k for _ in range(k)]
    for i in range(k):
        for j in range(i + 1):
            def ent(a, b):
                (am, ar), (gm, gr), (cm, cr) = A[a][b], G[a][b], C[a][b]
                return am - mu * gm - cm / d, ar + mu * gr + cr / d
            m1, r1 = ent(i, j); m2, r2 = ent(j, i)
            if abs(m1 - m2) > r1 + r2: blocked(f'S not symmetric at ({i},{j})')
            x = m1 * sc; lo = x.numerator // x.denominator                      # floor
            rr = r1 * sc; rad = -((-rr.numerator) // rr.denominator) + 1        # ceil + floor error
            Sm[i][j] = Sm[j][i] = lo; R[i][j] = R[j][i] = rad; mids[i][j] = mids[j][i] = m1
    # untrusted T = round(2^t L^-1), L ~ chol(S_mid) at 320 bits
    ctx.prec = 320
    X = [[arb(mids[i][j].numerator) / mids[i][j].denominator for j in range(k)] for i in range(k)]
    L = [[arb(0)] * k for _ in range(k)]
    for j in range(k):
        dd = (X[j][j] - sum((L[j][t] ** 2 for t in range(j)), arb(0))).mid()
        if not dd > 0: return False, f'approximate Cholesky of S_mid breaks at {j} (S_mid not PD)'
        L[j][j] = dd.sqrt().mid()
        for i in range(j + 1, k): L[i][j] = ((X[i][j] - sum((L[i][t] * L[j][t] for t in range(j)), arb(0))) / L[j][j]).mid()
    Linv = arb_mat(L).solve(arb_mat([[1 if i == j else 0 for j in range(k)] for i in range(k)]), nonstop=True, algorithm='approx')
    def toint(a):
        man, ex = (a * arb(2) ** T_BITS).mid().man_exp(); man, ex = int(man), int(ex)
        return man << ex if ex >= 0 else (man >> -ex) if man >= 0 else -((-man) >> -ex)
    T = [[toint(Linv[i, j]) if j <= i else 0 for j in range(k)] for i in range(k)]
    if not all(T[i][i] > 0 for i in range(k)): return False, 'T has a non-positive diagonal entry'
    Tm, Ta = fmpz_mat(T), fmpz_mat([[abs(x) for x in row] for row in T])
    D = Tm * fmpz_mat(Sm) * Tm.transpose(); W = Ta * fmpz_mat(R) * Ta.transpose()
    worst = None
    for i in range(k):
        off = sum(abs(int(D[i, j])) + int(W[i, j]) for j in range(k) if j != i)
        marg = F(int(D[i, i]) - int(W[i, i]) - off, int(D[i, i]))
        if marg <= 0: return False, f'row {i} not diagonally dominant (relative margin {float(marg):.3e})'
        worst = marg if worst is None or marg < worst else worst
    return True, f'min relative Gershgorin margin {float(worst):.6f}'


allok = True
for mu in mus:
    ok, msg = cert(mu); allok &= ok
    print(f"mu={mu}: " + ('CERTIFIED (exact integer congruence + Gershgorin), ' if ok else 'FAILED: ') + msg, flush=True)
sys.exit(0 if allok else 1)
