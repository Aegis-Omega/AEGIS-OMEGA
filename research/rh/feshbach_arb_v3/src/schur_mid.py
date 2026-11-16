"""Rigorous Schur step by midpoint + radius norm (Rump): S = A11 - mu G11 - C_B/(c_inf - mu) with real ball entries.

The true S is symmetric and lies entrywise in the lower-triangle balls. Write S = S_mid + E with S_mid the exact
midpoints of those balls and |E_ij| <= rad_ij (mirrored). Then lambda_min(S) >= lambda_min(S_mid) - ||E||_2 and
||E||_2 <= r := max_i sum_j rad_ij. S > 0 is certified when the interval Cholesky of S_mid - r I (zero-radius inputs,
320 bits) has every pivot ball > 0. The printed minimum pivot is information only: the certificate is the shift by r
before the factorization, not a comparison of a pivot with r.

c_inf must be a certified lower bound of the complement form. Bound mode reads it from a manifest and checks
  c_inf <= m - trPTP_upper   (Krein slack m from krein_slack.log, trPTP_upper from trace_arb.json),
with the SHA-256 of the blocks and both provenance files pinned.

usage: schur_mid.py --manifest manifest.json mu...   exit 0 only if every mu is POSITIVE DEFINITE; 1 if one fails;
                                                      2 if an input check fails (fail closed).
       schur_mid.py blocks.json c_inf mu...           experiment mode: c_inf is not bound, exit 3 instead of 0.
"""
import sys, json, hashlib, os
from flint import arb, ctx
ctx.prec = 320


def blocked(msg):
    print('BLOCKED: ' + msg, flush=True); sys.exit(2)


def sha256(path):
    with open(path, 'rb') as f: return hashlib.sha256(f.read()).hexdigest()


if len(sys.argv) >= 3 and sys.argv[1] == '--manifest':
    mf = sys.argv[2]; base = os.path.dirname(os.path.abspath(mf)); mus = sys.argv[3:]
    Mn = json.load(open(mf)); p = lambda k: os.path.join(base, Mn[k])
    src = Mn['c_inf_source']; q = lambda k: os.path.join(base, src[k])
    if sha256(p('blocks')) != Mn['blocks_sha256']: blocked('blocks sha256 mismatch')
    if sha256(q('trace_arb')) != src['trace_arb_sha256']: blocked('trace_arb sha256 mismatch')
    if sha256(q('krein_log')) != src['krein_log_sha256']: blocked('krein_log sha256 mismatch')
    m = arb(src['m'])
    if not any(line.startswith('CERTIFIED: F(xi) >= 0 for all real xi, m = ') and arb(line.split('m = ', 1)[1].strip()).overlaps(m)
               for line in open(q('krein_log'))): blocked('krein log does not certify m = ' + src['m'])
    bound = m - arb(json.load(open(q('trace_arb')))['trPTP_upper'])
    cinf = arb(Mn['c_inf'])
    if not cinf <= bound: blocked(f"c_inf {Mn['c_inf']} is not <= m - trPTP_upper = {bound.str(15)}")
    blocks, bound_mode = p('blocks'), True
elif len(sys.argv) >= 4:
    blocks, cinf, mus, bound_mode = sys.argv[1], arb(sys.argv[2]), sys.argv[3:], False
else:
    print(__doc__); sys.exit(2)
if not mus: blocked('no mu')
P = json.load(open(blocks))
def M(name): return [[arb(re) for re, im in row] for row in P[name]]
for name in ('A11', 'G11', 'CB'):
    if not all(arb(im) == 0 for row in P[name] for re, im in row): blocked(name + ': imaginary parts must be exactly 0')
A, G, C = M('A11'), M('G11'), M('CB'); k = len(A)
if not all(len(X) == k and all(len(row) == k for row in X) for X in (A, G, C)): blocked('block shapes differ')


def cert(mu):
    d = cinf - mu
    if not (mu >= 0 and d > 0): blocked('need 0 <= mu < c_inf')
    S = [[A[i][j] - mu * G[i][j] - C[i][j] / d for j in range(k)] for i in range(k)]
    for i in range(k):
        for j in range(i):
            if not S[i][j].overlaps(S[j][i]): blocked(f'S not symmetric at ({i},{j})')
    L = lambda i, j: S[i][j] if i >= j else S[j][i]          # the lower-triangle balls, mirrored
    r = max(sum((L(i, j).rad() for j in range(k)), arb(0)) for i in range(k))
    r = arb(r.upper()) + arb(r.upper()) * arb('1e-6')        # outward
    X = [[arb(L(i, j).mid()) - (r if i == j else 0) for j in range(k)] for i in range(k)]
    Lm = [[arb(0)] * k for _ in range(k)]; mp = None
    for j in range(k):
        dd = X[j][j] - sum((Lm[j][t] ** 2 for t in range(j)), arb(0))
        if not dd > 0: return False, j, dd, r
        mp = dd if mp is None or dd < mp else mp; Lm[j][j] = dd.sqrt()
        for i in range(j + 1, k): Lm[i][j] = (X[i][j] - sum((Lm[i][t] * Lm[j][t] for t in range(j)), arb(0))) / Lm[j][j]
    return True, None, mp, r


allok = True
for mu in mus:
    ok, j, d, r = cert(arb(mu)); allok &= ok
    print(f"mu={mu}: " + (f"POSITIVE DEFINITE (midpoint - radius norm), min Cholesky pivot {d.str(12)}" if ok else f"FAILED at pivot {j}: {d.str(12)}")
          + f"  radius norm r = {r.str(5)}" + ('' if bound_mode else '  [UNBOUND c_inf: experiment only]'), flush=True)
sys.exit((0 if bound_mode else 3) if allok else 1)
