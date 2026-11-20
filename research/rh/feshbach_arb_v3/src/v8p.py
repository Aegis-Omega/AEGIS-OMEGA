"""V8 candidate (V7 plus the two changes below): the blocks of feshbach_blocks_arb.py (A11, G11, C_B >= ||P_perp A v||^2 on V = moment-zero part of
span{e_m : |m| <= N}), with the same row model, tail bound and output format, in real Arb.

Changes against the V6 candidate (each is the same function of the true inputs, so each enclosure is valid):
 1. Rows. For n != m, pole - wr - wp = pole + (alpha_m - alpha_n) / (pi (n - m)) with
    alpha_n = -(sS(n) + sum_q w_q sin(2 pi n y_q / L)), the alpha of the tail bound. The sines are evaluated once per
    index, not twice per entry, and seqs once per |n|.
 2. V-perp = span{avec, bvec}: for v = e_m + v_0 e_0 + v_1 e_1, sum v_j/(j^2+beta^2) = 0 and sum v_j j/(j^2+beta^2) = 0.
    With M = [avec, bvec], P_V = I - M (M^T M)^{-1} M^T, and RR = Qb^T Qb + Rout^T Rout (Rout: rows N < |n| <= NP):
        C_B = Z^T (RR + Tail + Ib) Z - A11 G11^{-1} A11 = Z^T (Rout^T Rout + Tail + Ib) Z + W^T (M^T M)^{-1} W,
        W = M^T Qb Z  (2 x k).
    No k x k product A11 A11, no inverse, no subtraction of two large blocks.
 3. Z^T X Z, A11 = Z^T Qb Z and G11 = I + U^T U by the rank-two congruence of the V6 candidate.
 4. Tail = sum_i (c_i / p_i) u_i u_i^T is formed as one product; the 2K + 2 dense outer products are not stored.
Z, Qb, M and the tail are real, so everything is arb_mat (the imaginary parts of the output are 0).

V8:
 5. DROP_POLE=1 (default): the two pole terms of the tail split are dropped. For v in V, la(v) = <avec, v> = 0 and
    lb(v) = <bvec, v> = 0 (CvSPivotCongruenceV1.perp_a, perp_b), so pole_n(v) = Cc (beta^2 la - n lb)/(n^2+beta^2) = 0
    for every n and the weighted Cauchy-Schwarz runs over 2K + 1 terms instead of 2K + 3.
 6. TAIL_WEIGHTS=global: p_i proportional to sqrt(g_i), g_i = c_i b_i^T (A11 - mu G11)^{-1} b_i with b_i = Z^T u_i,
    and g = Eco1/(lambda_1 - mu) for the Eco G11 term, at mu = SCHUR_MU (GLOBAL_MIX of uniform added).
    This minimises sum_i g_i/p_i, and sum_i g_i/p_i + (rest) <= c_inf - mu is a sufficient condition for the
    Schur step (w b b^T <= (w b^T M^{-1} b) M for M > 0), so every direction of V counts, not one vector.
    TAIL_WEIGHTS=schur (diagnostic): p maximises the smallest eigenvalue of the Schur matrix projected on the bottom
    RITZ_R Ritz vectors. It starves terms that live outside that subspace; see the receipt.
    Any fixed rational p with sum p <= 1 gives a valid bound; the choice only affects sharpness."""
import sys, math, json, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from flint import arb, arb_mat, acb, fmpq, ctx
import cvs_entries as gw
ctx.prec = 192
T0 = time.perf_counter()
def tick(s): print('T', s, round(time.perf_counter() - T0, 2), flush=True)
def load_json(path):
    with open(path) as f: return json.load(f)
L = arb(sys.argv[1]); N = int(sys.argv[2]); NP = int(sys.argv[3])
pi = arb.pi(); quarter = arb('0.25')
def seqs(n):
    omega = 2 * pi * n / L; z = acb(quarter, pi * n / L)
    psi = z.digamma(); g_s, g_cc, g_x1, g_x2 = gw._geometric_remainders(n, L, ctx.prec)
    S = arb('0.5') * psi.imag - omega * g_s if n else arb(0)
    CC = -arb('0.5') * (psi.real - quarter.digamma()) + g_cc if n else arb(0)
    XC = arb('0.25') * z.polygamma(acb(1)).real - L * g_x1 - g_x2
    return S, CC, XC
cmax = int(math.exp(float(L.mid())))
primes = [(q, p) for q, p in gw.prime_powers_up_to(max(cmax, 2)) if arb(q).log() < L]
W = [arb(p).log() * arb(q) ** arb('-0.5') for q, p in primes]; Y = [arb(q).log() for q, _ in primes]
beta = L / (4 * pi); Cc = L * ((L.exp()).sqrt() + 1 / (L.exp()).sqrt() - 2) / (2 * pi * pi)
kappa = gw._kappa(L); jc = gw._J(L)
band = list(range(-N, N + 1))
# per |n| <= NP: S_n (signed below), and CC, XC for the diagonal (|n| <= N)
Sabs = {}; CXb = {}
AF = os.environ.get('ALPHA_FILE')   # V8i: alpha_n for |n| <= NP from integer fixed-point intervals (arbport/tau80)
DF = os.environ.get('DIAG_FILE')   # V8i: CC_n, XC_n for |n| <= N from integer fixed-point intervals (arbport/tau80/diag80)
def ball(lo, hi, sc): return arb(int(lo) + int(hi)) * sc / 2 + arb(0, arb(int(hi) - int(lo)) * sc / 2)
if DF:
    assert AF, 'DIAG_FILE needs ALPHA_FILE'
    DD = load_json(DF); scd = arb(2) ** (-DD['P']); assert DD['L'] == '9/5' and sys.argv[1] == '1.8' and len(DD['CC']) >= N + 1
    for n in range(N + 1): CXb[n] = (ball(*DD['CC'][n], scd), ball(*DD['XC'][n], scd))
    print('DIAG_FILE', DF, 'no digamma/polygamma evaluated', flush=True)
for n in range(NP + 1):
    if DF or (AF and n > N): continue   # no digamma: the integer layer supplies alpha_n (and CC, XC with DIAG_FILE)
    S_, CC_, XC_ = seqs(n); Sabs[n] = S_
    if n <= N: CXb[n] = (CC_, XC_)
sS = lambda m: Sabs[m] if m >= 0 else -Sabs[-m]
def sig(n): return sum((w * (2 * pi * n * y / L).sin() for w, y in zip(W, Y)), arb(0))
alph = {}
if AF:
    D = load_json(AF); sc = arb(2) ** (-D['P']); assert D['L'] == '9/5' and sys.argv[1] == '1.8' and L.overlaps(arb(9) / 5) and len(D['lo']) >= NP + 1
    for n in range(NP + 1):
        lo, hi = int(D['lo'][n]), int(D['hi'][n])
        a_ = arb(lo + hi) * sc / 2 + arb(0, arb(hi - lo) * sc / 2)
        if n <= N and not DF:  # cross-check against the Arb digamma value on the band
            ref = -(Sabs[n] + sig(n)); assert a_.overlaps(ref), n
        alph[n] = a_; alph[-n] = -a_
    print('ALPHA_FILE', AF, 'max radius', max(float(alph[n].rad()) for n in range(NP + 1)), flush=True)
else:
    for n in range(NP + 1):
        a_ = -(Sabs[n] + sig(n)); alph[n] = a_; alph[-n] = -a_
if os.environ.get('PARITY_BREAK'):  # negative control: perturb alpha_n for n > 0 only (alpha_{-n} untouched)
    for n in range(1, NP + 1): alph[n] = alph[n] + arb(os.environ['PARITY_BREAK'])
if os.environ.get('PARITY_BREAK_OUT'):  # negative control outside the band only (tail atoms use the band alphas, unaffected)
    for n in range(N + 1, NP + 1): alph[n] = alph[n] + arb(os.environ['PARITY_BREAK_OUT'])
invd = {n: 1 / (n * n + beta * beta) for n in range(-NP, NP + 1)}
tick('seqs')
def diag_entry(n):
    CCn, XCn = CXb[abs(n)]
    pole = Cc * (beta * beta - n * n) / ((n * n + beta * beta) * (n * n + beta * beta))
    wr = kappa + 2 * CCn + jc - (2 / L) * XCn
    wp = sum((w * 2 * (1 - y / L) * (2 * pi * n * y / L).cos() for w, y in zip(W, Y)), arb(0))
    return pole - wr - wp
def row(n):
    an = alph[n]; dn = Cc * invd[n]; b2 = beta * beta
    return [diag_entry(n) if n == m else
            dn * (b2 - n * m) * invd[m] + (alph[m] - an) / (pi * (n - m)) for m in band]
Qb = arb_mat([row(n) for n in band])
tick('Qb')
# Rout^T Rout = sum over blocks of CH rows (the same sum, without storing the (2 NP - 2 N) x (2N+1) matrix)
outs = [n for n in range(-NP, NP + 1) if abs(n) > N]
CH = int(os.environ.get('ROW_CHUNK', '2000'))
def parity_cols():  # E_j = e_j + e_-j - e_0/(2 d_j) (j = 1..N), O_j = (e_j - e_-j) - t_j (e_1 - e_-1) (j = 2..N)
    wj = lambda j: 2 * pi * j / L; dj = lambda j: quarter + wj(j) ** 2
    cE = []; cO = []
    for j in range(1, N + 1):
        c = [arb(0)] * (2 * N + 1); c[band.index(j)] = arb(1); c[band.index(-j)] = arb(1); c[band.index(0)] = -1 / (2 * dj(j)); cE.append(c)
    for j in range(2, N + 1):
        t = (wj(j) / dj(j)) / (wj(1) / dj(1)); c = [arb(0)] * (2 * N + 1)
        c[band.index(j)] = arb(1); c[band.index(-j)] = arb(-1); c[band.index(1)] = -t; c[band.index(-1)] = t; cO.append(c)
    return [arb_mat([[cols[c][r] for c in range(len(cols))] for r in range(2 * N + 1)]) for cols in (cE, cO)]
if os.environ.get('PARITY_STREAM'):
    # streamed parity Gram of the outside rows (ChatGPT streaming duel V3): with R_{-n}(P v) = R_n(v),
    # R_{-n} B_e = R_n B_e and R_{-n} B_o = -R_n B_o, so B^T Rout^T Rout B = 2 sum_{n=N+1}^{NP} (R_n B)^T (R_n B) per sector,
    # cross block 0. Only the rows n = N+1..NP are evaluated (half the row work); the full Rout is never formed.
    BeS, BoS = parity_cols(); RRe = arb_mat(N, N); RRo = arb_mat(N - 1, N - 1)
    # fail closed unless the reflection identities the streaming relies on hold on the in-band block and on sampled rows
    ix = {m: band.index(m) for m in band}
    # complete input-level guard: off-band rows depend only on alph (odd in n), invd (even, exact) and constants, so
    # row(-n) . B_e = row(n) . B_e and row(-n) . B_o = -row(n) . B_o for every |n| > N once alph is odd everywhere
    assert all((alph[n] + alph[-n]).contains(0) for n in range(NP + 1)), 'alpha not odd: streaming identity unproven'
    assert all((Qb[ix[n], ix[m]] - Qb[ix[-n], ix[-m]]).contains(0) for n in band for m in band), 'Qb not reflection invariant'
    for n in sorted({N + 1, N + 2, (N + NP) // 2, NP}):
        rp = arb_mat([row(n)]); rm_ = arb_mat([row(-n)])
        assert all(x.contains(0) for x in (rm_ * BeS - rp * BeS).entries()), ('even row identity fails', n)
        assert all(x.contains(0) for x in (rm_ * BoS + rp * BoS).entries()), ('odd row identity fails', n)
    pos = list(range(N + 1, NP + 1))
    for s in range(0, len(pos), CH):
        Rc = arb_mat([row(n) for n in pos[s:s + CH]]); Re = Rc * BeS; Ro = Rc * BoS
        RRe += (Re.transpose() * Re) * 2; RRo += (Ro.transpose() * Ro) * 2
    del Rc, Re, Ro
    RRout = None
else:
    RRout = arb_mat(2 * N + 1, 2 * N + 1)
    for s in range(0, len(outs), CH):
        Rc = arb_mat([row(n) for n in outs[s:s + CH]])
        RRout += Rc.transpose() * Rc
    del Rc
tick('rows+RRout')
# tail |n| > NP: the bound of feshbach_blocks_arb.py, unchanged.
KS = arb(0)
for kk in range(200):
    ck = 2 * kk + arb('0.5'); KS += (-ck * L).exp() / (2 * ck)
# V8i: omitted terms k >= 200 (all positive): sum <= e^{-c_200 L} / (2 c_200 (1 - e^{-2L})), c_200 = 400.5.
# K2 must be an upper bound, so the tail is added as a ball radius (found by ChatGPT HOLON parity duel V1).
c200 = arb(400) + arb('0.5'); KS += arb(0, ((-c200 * L).exp() / (2 * c200 * (1 - (-2 * L).exp()))).upper())
ymin = pi * NP / L
K2 = pi / 4 + 1 / (2 * ymin) + KS + sum(W, arb(0))
alpha = [alph[m] for m in band]
avec = [1 / (m * m + beta * beta) for m in band]; bvec = [m / (m * m + beta * beta) for m in band]
TAIL_ORDER = int(os.environ.get('TAIL_ORDER', '1'))
Amax = max(abs(a_) for a_ in alpha).upper()
K = TAIL_ORDER; f = 2 * K + 3
vecs = []; coefs = []
for j in range(K):
    cj = 2 / ((2 * j + 1) * pi * pi * arb(NP) ** (2 * j + 1))
    vecs.append([a_ * arb(m) ** j for a_, m in zip(alpha, band)]); coefs.append(cj)
    vecs.append([arb(m) ** j for m in band]); coefs.append(cj * K2 * K2)
if os.environ.get('DROP_POLE', '1') != '1':
    vecs.append(bvec); coefs.append(2 * Cc * Cc / NP)
    vecs.append(avec); coefs.append(2 * Cc * Cc * beta ** 4 / (3 * arb(NP) ** 3))
f = len(vecs) + 1
Eco1 = 2 * (Amax + K2) ** 2 * arb(N) ** (2 * K) * (2 * N + 1) / ((2 * K + 1) * pi * pi * arb(NP - N) ** (2 * K + 1))
# moment-zero basis: Z = e_m + v_0(m) e_0 + v_1(m) e_1, m not in {0, 1}
piv = [0, 1]; rest = [m for m in band if m not in piv]; k = len(rest)
fi = [band.index(m) for m in rest]; pii = [band.index(p) for p in piv]
omega2 = (2 * pi / L) ** 2
U2 = arb_mat(2, k)
for jj, m in enumerate(rest):
    d = arb(m * m) * omega2 + quarter
    U2[0, jj] = (arb(m) - 1) * quarter / d
    U2[1, jj] = -arb(m) * (omega2 + quarter) / d
U2t = U2.transpose()
def sub(X, I, J): return arb_mat([[X[i, j] for j in J] for i in I])
def proj(X):  # Z^T X Z for Z = [I_free; U2] after reordering rows
    return sub(X, fi, fi) + sub(X, fi, pii) * U2 + U2t * sub(X, pii, fi) + (U2t * sub(X, pii, pii)) * U2
A11 = proj(Qb)
G11 = U2t * U2
for i in range(k): G11[i, i] += 1
Mm_early = arb_mat([[avec[i], bvec[i]] for i in range(2 * N + 1)])
Wt_early = Mm_early.transpose() * Qb                                  # 2 x (2N+1)
Wm_early = sub(Wt_early, [0, 1], fi) + sub(Wt_early, [0, 1], pii) * U2  # M^T Qb Z
tick('A11G11')
def mid(M): return [[float(M[i, j].mid()) for j in range(M.ncols())] for i in range(M.nrows())]
import numpy as np
from scipy.linalg import eigh
WEIGHTS = os.environ.get('TAIL_WEIGHTS', 'uniform'); RITZ = os.environ.get('RITZ', '')
if RITZ or WEIGHTS not in ('uniform', 'fixed'):
    ev0, U0 = eigh(np.array(mid(A11)), np.array(mid(G11)))
def ztv(u):  # Z^T u (k-vector) for a band vector u
    zu = arb_mat([[u[i]] for i in fi]); up = arb_mat([[u[i]] for i in pii])
    return zu + U2t * up
if RITZ:  # diagnostic only: bottom pair of (A11, G11) by inverse iteration at working precision, from the float64 start
    u1 = arb_mat([[float(x)] for x in U0[:, 0]])
    for _ in range(6):
        u1 = A11.solve(G11 * u1, nonstop=True, algorithm='approx')
        nrm = max(abs(float(u1[i, 0].mid())) for i in range(k)); u1 = u1 * arb(1 / nrm)
    def rq(Mx): return (u1.transpose() * Mx * u1)[0, 0] / (u1.transpose() * G11 * u1)[0, 0]
    lam1 = rq(A11); print('ritz lam1', lam1.str(12), 'float64 eigh lam1', ev0[0], flush=True)
    tick('ritz')
if WEIGHTS == 'uniform':
    pw = [fmpq(1, f)] * f
elif WEIGHTS == 'fixed':  # V9 (ChatGPT HOLON V8/V9): exact rational weights from AEGIS_TAIL_WEIGHTS_JSON, order = vecs then Eco
    from fractions import Fraction
    raw = load_json(os.environ['AEGIS_TAIL_WEIGHTS_JSON'])
    if not isinstance(raw, list) or len(raw) != f or not all(isinstance(x, str) for x in raw):
        raise ValueError('tail weight schema: %d strings expected' % f)
    ex = [Fraction(x) for x in raw]
    if min(ex) <= 0 or sum(ex) > 1: raise ValueError('weights must be positive with sum <= 1')
    pw = [fmpq(x.numerator, x.denominator) for x in ex]
elif WEIGHTS == 'global':
    MU0 = arb(os.environ['SCHUR_MU']); MIX = float(os.environ.get('GLOBAL_MIX', '0'))
    Bm = arb_mat([[x for x in col] for col in zip(*[[ztv(u)[i, 0] for i in range(k)] for u in vecs])])   # k x (f-1)
    Mmu = A11 - G11 * MU0
    Xs = Mmu.solve(Bm, nonstop=True, algorithm='approx')
    g = [abs(float((coefs[i] * sum((Bm[r, i] * Xs[r, i] for r in range(k)), arb(0))).mid())) for i in range(f - 1)]
    lam1g = float(lam1.mid()) if RITZ else float(os.environ['LAMBDA1'])
    g.append(float(Eco1.mid()) / (lam1g - float(MU0.mid())))
    r = [math.sqrt(x) + 1e-300 for x in g]
    pw = [fmpq(int(1e9 * (MIX / f + (1 - MIX) * x / sum(r))) or 1, 10 ** 9) for x in r]
    print('global weights g', ['%.3g' % x for x in g], flush=True)
    del Bm, Mmu, Xs
elif WEIGHTS == 'schur':
    import mpmath as mp
    mp.mp.dps = 60
    RR_ = int(os.environ.get('RITZ_R', '12')); MU0 = float(os.environ['SCHUR_MU']); CI = float(os.environ['CINF'])
    def to_mp(Mx): return mp.matrix([[mp.mpf(Mx[i, j].mid().str(60, radius=False)) for j in range(Mx.ncols())] for i in range(Mx.nrows())])
    def rr(Y):  # Rayleigh-Ritz of (A11, G11) on span(Y): G-orthonormal Ritz vectors, ascending
        Am = to_mp(Y.transpose() * A11 * Y); Gm = to_mp(Y.transpose() * G11 * Y)
        Lc = mp.cholesky(Gm); Li = mp.inverse(Lc); E, Q = mp.eigsy(Li * Am * Li.T)
        order = sorted(range(len(E)), key=lambda i: E[i]); T = Li.T * Q
        Tm = arb_mat([[arb(mp.nstr(T[i, j], 55)) for j in order] for i in range(T.rows)])
        return Y * Tm, [E[i] for i in order]
    Y = arb_mat([[float(U0[i, j]) for j in range(RR_)] for i in range(k)])
    for _ in range(5):
        Y, lams = rr(A11.solve(G11 * Y, nonstop=True, algorithm='approx'))
    print('ritz', [mp.nstr(x, 6) for x in lams], flush=True)
    WtMi_ = Wm_early.transpose() * ((Mm_early.transpose() * Mm_early).inv() * Wm_early)
    def red(Mx): return np.array([[float(x) for x in row] for row in to_mp(Y.transpose() * Mx * Y).tolist()])
    scale = 1 / float(lams[0])
    Lam = np.diag([float(x) * scale for x in lams])
    PR_ = proj(RRout); Fix = red(PR_) * scale; del PR_
    Fix = Fix + red(WtMi_) * scale; del WtMi_
    # congruence by D = diag(lambda_i^{-1/2}): D S D is PSD iff S is, and its smallest eigenvalue is resolved in
    # float64 even when the Ritz values span many orders of magnitude
    Dg = np.diag(1 / np.sqrt(np.diag(Lam)))
    def colf(Mx): return np.array([float(Mx[i, 0].mid()) for i in range(Mx.nrows())])
    Bv = [colf(Y.transpose() * ztv(u)) for u in vecs]
    cf = np.array([float(c.mid()) for c in coefs] + [float(Eco1.mid())]) * scale
    terms_r = [np.outer(b, b) for b in Bv] + [np.eye(RR_)]
    def Smat(p, mu):
        C = Fix + sum(cf[i] / p[i] * terms_r[i] for i in range(f))
        return Dg @ (Lam - mu * scale * np.eye(RR_) - C / (CI - mu)) @ Dg
    from scipy.optimize import minimize
    BETA = 40.0
    def obj(z):
        p = np.exp(z - z.max()); p /= p.sum()
        ev, V_ = np.linalg.eigh(Smat(p, MU0))
        wgt = np.exp(-BETA * (ev - ev[0])); wgt /= wgt.sum()
        val = ev[0] - np.log(np.exp(-BETA * (ev - ev[0])).sum()) / BETA
        dl = np.array([sum(wgt[a] * cf[i] / p[i] ** 2 * ((Dg @ V_[:, a]) @ terms_r[i] @ (Dg @ V_[:, a])) for a in range(RR_)) / (CI - MU0) for i in range(f)])
        gz = p * (dl - p @ dl)
        return -val, -gz
    t1 = np.array([cf[i] * terms_r[i][0, 0] for i in range(f)]); r1 = np.sqrt(np.abs(t1)) + 1e-300
    best = None
    for start in (np.zeros(f), np.log(0.5 / f + 0.5 * r1 / r1.sum())):
        res = minimize(obj, start, jac=True, method='L-BFGS-B')
        if best is None or res.fun < best.fun: best = res
    pf = np.exp(best.x - best.x.max()); pf /= pf.sum()
    pw = [fmpq(max(1, int(1e9 * x * (1 - 1e-6))), 10 ** 9) for x in pf]
    lo, hi = 0.0, float(lams[0])
    for _ in range(60):
        mid_ = (lo + hi) / 2
        if np.linalg.eigvalsh(Smat([float(x) for x in pw], mid_))[0] > 0: lo = mid_
        else: hi = mid_
    print('schur weights: projected lambda_min at mu0', -best.fun / scale, ' projected max mu', lo, flush=True)
else:
    Zf = np.zeros((2 * N + 1, k)); Zf[fi, np.arange(k)] = 1; Zf[pii, :] = np.array(mid(U2))
    v0 = Zf @ (np.array([float(u1[i, 0].mid()) for i in range(k)]) if RITZ == 'weights' else U0[:, 0])
    t = [abs(float(c.mid())) * float(np.dot(np.array([float(x.mid()) for x in u]), v0)) ** 2 for u, c in zip(vecs, coefs)]
    t.append(float(Eco1.mid()) * float(np.dot(v0, v0)))
    r = [math.sqrt(x) + 1e-300 for x in t]
    pw = [fmpq(int(1e9 * (0.5 / f + 0.5 * x / sum(r))), 10 ** 9) for x in r]
assert sum(pw) <= 1 and all(x > 0 for x in pw)
if os.environ.get('PARITY_SPLIT'):
    # Parity-split certificate (Claude lab, parity duel V1). With reflection P (m -> -m): R_{-n}(Pv) = R_n(v) for every
    # row, so for v = v_e + v_o the exact row/tail sums satisfy tau(v) = tau(v_e) + tau(v_o) (the cross terms of the rows
    # n and -n cancel). Each tail atom u_i has a definite parity (alpha odd: alpha m^j has parity (-1)^(j+1), m^j has
    # (-1)^j), so on v_e only the even atoms are nonzero, and the weighted Cauchy-Schwarz for tau(v_e) may spend the
    # whole budget sum p <= 1 on the even atoms + Eco; likewise for the odd sector. Blocks are written in the parity basis
    # E_j / O_j and checked by the unchanged schur_arb.py, one block at a time.
    wj = lambda j: 2 * pi * j / L; dj = lambda j: quarter + wj(j) ** 2
    colsE = []; colsO = []
    for j in range(1, N + 1):
        c = [arb(0)] * (2 * N + 1); c[band.index(j)] = arb(1); c[band.index(-j)] = arb(1); c[band.index(0)] = -1 / (2 * dj(j)); colsE.append(c)
    for j in range(2, N + 1):
        t = (wj(j) / dj(j)) / (wj(1) / dj(1)); c = [arb(0)] * (2 * N + 1)
        c[band.index(j)] = arb(1); c[band.index(-j)] = arb(-1); c[band.index(1)] = -t; c[band.index(-1)] = t; colsO.append(c)
    def parity(u):
        e = all((u[band.index(m)] - u[band.index(-m)]).contains(0) for m in range(1, N + 1))
        o = all((u[band.index(m)] + u[band.index(-m)]).contains(0) for m in range(0, N + 1))
        assert e != o, 'tail atom without definite parity'; return 'e' if e else 'o'
    par = [parity(u) for u in vecs]
    Mmat = arb_mat([[avec[r], bvec[r]] for r in range(2 * N + 1)]); MMi = (Mmat.transpose() * Mmat).inv()
    PS = os.environ['PARITY_SPLIT']; MU0 = arb(os.environ.get('SCHUR_MU', '0'))
    for sec, cols in (('even', colsE), ('odd', colsO)):
        Bs = arb_mat([[cols[c][r] for c in range(len(cols))] for r in range(2 * N + 1)])
        assert all(x.contains(0) for x in (Mmat.transpose() * Bs).entries()), 'parity basis not moment-zero'
        idx = [i for i, p_ in enumerate(par) if p_ == sec[0]]; fs = len(idx) + 1
        As = Bs.transpose() * Qb * Bs; Gs = Bs.transpose() * Bs
        if PS == 'uniform':
            ps = [fmpq(1, fs)] * fs
        elif PS == 'fixed':   # PARITY_W_even / PARITY_W_odd: comma-separated exact fractions, atoms in order then Eco
            from fractions import Fraction
            ex = [Fraction(x) for x in os.environ['PARITY_W_' + sec].split(',')]
            assert len(ex) == fs, (sec, len(ex), fs)
            ps = [fmpq(x.numerator, x.denominator) for x in ex]
        else:   # 'global': p ~ sqrt(g), g_i = c_i b_i^T (As - mu0 Gs)^{-1} b_i, Eco: Eco1 tr-free bound via the bottom of (As, Gs)
            Mmu = As - Gs * MU0; bs = [Bs.transpose() * arb_mat([[x] for x in vecs[i]]) for i in idx]
            g = [abs(float((coefs[i] * (b.transpose() * Mmu.solve(b, nonstop=True, algorithm='approx'))[0, 0]).mid())) for i, b in zip(idx, bs)]
            lam = float(os.environ.get('LAMBDA1', '0')) or None
            evs = sorted(np.linalg.eigvalsh(np.linalg.solve(np.array(mid(Gs)), np.array(mid(As))))) if lam is None else None
            l1 = lam if lam is not None else evs[0]
            g.append(float(Eco1.mid()) / max(l1 - float(MU0.mid()), 1e-300))
            r_ = [math.sqrt(x) + 1e-300 for x in g]
            ps = [fmpq(max(1, int(1e9 * (1 - 1e-6) * x / sum(r_))), 10 ** 9) for x in r_]
        assert sum(ps) <= 1 and all(x > 0 for x in ps)
        Tail_s = arb_mat(2 * N + 1, 2 * N + 1)
        for w_, i in zip(ps[:-1], idx):
            col = arb_mat([[x] for x in vecs[i]]); Tail_s += (col * col.transpose()) * (coefs[i] / arb(w_))
        Eco_s = Eco1 / arb(ps[-1])
        W_s = Mmat.transpose() * Qb * Bs
        if RRout is None:   # streamed: B^T (Rout^T Rout) B from the sector Gram, B^T (Tail + Eco I) B directly
            C_s = (RRe if sec == 'even' else RRo) + Bs.transpose() * Tail_s * Bs + (Bs.transpose() * Bs) * Eco_s + W_s.transpose() * (MMi * W_s)
        else:
            X_s = RRout + Tail_s
            for i in range(2 * N + 1): X_s[i, i] += Eco_s
            C_s = Bs.transpose() * X_s * Bs + W_s.transpose() * (MMi * W_s)
        kk = len(cols)
        head = {"L": str(L), "N": N, "NP": NP, "sector": sec, "K2": K2.str(30), "Amax": Amax.str(30), "tail_order": K,
                "tail_atoms": idx, "tail_weights": [str(x) for x in ps], "Eco": Eco_s.str(30), "parity_split": PS}
        with open(f"blocks_{sec}_N{N}_NP{NP}.json", "w") as fo:
            fo.write(json.dumps(head)[:-1])
            for nm, Mx in (("A11", As), ("G11", Gs), ("CB", C_s)):
                fo.write(f', "{nm}": [\n')
                for i in range(kk):
                    fo.write(('' if i == 0 else ',\n') + json.dumps([(Mx[i, j].str(70), "0") for j in range(kk)]))
                fo.write(']')
            fo.write('}\n')
        print('PARITY_SPLIT', sec, 'dim', kk, 'atoms', idx, 'weights', [str(x) for x in ps], flush=True)
        del Tail_s, C_s, As, Gs, Bs, W_s
    tick('parity'); sys.exit(0)
Ut = arb_mat([list(col) for col in zip(*vecs)])                       # (2N+1) x (2K+2)
Us = arb_mat([[Ut[i, j] * (coefs[j] / arb(pw[j])) for j in range(Ut.ncols())] for i in range(Ut.nrows())])
Tail = Us * Ut.transpose()
Eco = Eco1 / arb(pw[-1])
print('K2', K2, 'Amax', Amax, 'Eco', Eco, 'weights', WEIGHTS, [str(x) for x in pw])
Xout = RRout + Tail
for i in range(2 * N + 1): Xout[i, i] += Eco
tick('Tail')
M = Mm_early; Wt = Wt_early; Wm = Wm_early
CB = proj(Xout) + Wm.transpose() * ((M.transpose() * M).inv() * Wm)
tick('CB')
if os.environ.get('PARITY_TEST'):
    # parity basis of ChatGPT parity duel V1: E_j = e_j + e_-j - e_0/(2 d_j), O_j = (e_j - e_-j) - t_j (e_1 - e_-1),
    # d_j = 1/4 + w_j^2, w_j = 2 pi j / L, t_j = (w_j/d_j)/(w_1/d_1); in band index space (row of m is band.index(m)).
    mu0 = arb(os.environ.get('PARITY_MU', '0')); cinf = arb(os.environ.get('CINF', '1'))
    wj = lambda j: 2 * pi * j / L; dj = lambda j: quarter + wj(j) ** 2
    cols = []
    for j in range(1, N + 1):
        c = [arb(0)] * (2 * N + 1); c[band.index(j)] = arb(1); c[band.index(-j)] = arb(1); c[band.index(0)] = -1 / (2 * dj(j)); cols.append(c)
    ne = len(cols)
    for j in range(2, N + 1):
        t = (wj(j) / dj(j)) / (wj(1) / dj(1)); c = [arb(0)] * (2 * N + 1)
        c[band.index(j)] = arb(1); c[band.index(-j)] = arb(-1); c[band.index(1)] = -t; c[band.index(-1)] = t; cols.append(c)
    Bm = arb_mat([[cols[c][r] for c in range(len(cols))] for r in range(2 * N + 1)])
    Mmat = arb_mat([[avec[r], bvec[r]] for r in range(2 * N + 1)])
    mres = Mmat.transpose() * Bm
    print('PARITY moment residual M^T B: all balls contain 0 =', all(mres[i, j].contains(0) for i in range(2) for j in range(Bm.ncols())),
          ' max |mid| =', max(abs(float(mres[i, j].mid())) for i in range(2) for j in range(Bm.ncols())))
    T = sub(Bm, fi, list(range(k)))                       # B = Z T since Z restricted to the free rows is I
    ZT_p = U2 * T; Bp = sub(Bm, pii, list(range(k)))
    print('PARITY B[pivot rows] overlaps U2 T:', all(ZT_p[i, j].overlaps(Bp[i, j]) for i in range(2) for j in range(k)))
    def congr(X): return T.transpose() * X * T
    Ap = Bm.transpose() * Qb * Bm; Gp = Bm.transpose() * Bm
    Wp = Mmat.transpose() * Qb * Bm
    Cp = Bm.transpose() * Xout * Bm + Wp.transpose() * ((Mmat.transpose() * Mmat).inv() * Wp)
    for nm, X1, X2 in (('A11', Ap, congr(A11)), ('G11', Gp, congr(G11)), ('CB', Cp, congr(CB))):
        ov = all(X1[i, j].overlaps(X2[i, j]) for i in range(k) for j in range(k))
        cross = [X1[i, j] for i in range(ne) for j in range(ne, k)]
        print(f'PARITY {nm}: B^T X B overlaps T^T X_Z T entrywise: {ov};  cross block (even x odd) all contain 0: {all(x.contains(0) for x in cross)}',
              f' max |cross mid| {max((abs(float(x.mid())) for x in cross), default=0):.3e}  max cross radius {max((float(x.rad()) for x in cross), default=0):.3e}')
    S = Ap - Gp * mu0 - Cp * (1 / (cinf - mu0))
    def chol_ok(Sm, idx):
        X = [[Sm[i, j] for j in idx] for i in idx]; n_ = len(idx); Lm = [[arb(0)] * n_ for _ in range(n_)]; mp_ = None
        for j in range(n_):
            dd = X[j][j] - sum((Lm[j][t] ** 2 for t in range(j)), arb(0))
            if not dd > 0: return False, j, dd
            mp_ = dd if mp_ is None or dd < mp_ else mp_; Lm[j][j] = dd.sqrt()
            for i in range(j + 1, n_): Lm[i][j] = (X[i][j] - sum((Lm[i][t] * Lm[j][t] for t in range(j)), arb(0))) / Lm[j][j]
        return True, None, mp_
    for nm, idx in (('even', list(range(ne))), ('odd', list(range(ne, k))), ('full parity basis', list(range(k)))):
        print(f'PARITY Schur at mu={mu0} c_inf={cinf} block {nm} ({len(idx)}):', chol_ok(S, idx))
    Sz = A11 - G11 * mu0 - CB * (1 / (cinf - mu0))
    print('PARITY Schur pivot basis (k):', chol_ok(Sz, list(range(k))))
    sys.exit(0)
if RITZ:
    WtMi = Wm.transpose() * ((M.transpose() * M).inv() * Wm)
    tot = rq(CB); print('C_B(u1)', tot.str(12), ' lam1 - C_B(u1)/0.98', (lam1 - tot / arb('0.98')).str(8))
    for nm, fn in (('Rout', lambda: proj(RRout)), ('Tail', lambda: proj(Tail)), ('Eco*G11', lambda: G11 * Eco), ('inband_rank2', lambda: WtMi)):
        Mx = fn(); print('  part', nm, rq(Mx).str(10), flush=True); del Mx
    del WtMi
del RRout, Tail, Xout, Qb, Wt, Wm, Us, Ut, M, Wt_early, Wm_early, Mm_early
# the JSON of feshbach_blocks_arb.py (same keys and entry strings), written one row at a time
head = {"L": str(L), "N": N, "NP": NP, "K2": K2.str(30), "Amax": Amax.str(30), "tail_order": K,
        "tail_weights": [str(x) for x in pw], "Eco": Eco.str(30)}
with open(f"blocks_N{N}_NP{NP}.json", "w") as fo:
    fo.write(json.dumps(head)[:-1])
    for nm, Mx in (("A11", A11), ("G11", G11), ("CB", CB)):
        fo.write(f', "{nm}": [\n')
        for i in range(k):
            fo.write(('' if i == 0 else ',\n') + json.dumps([(Mx[i, j].str(70), "0") for j in range(k)]))
        fo.write(']')
    fo.write('}\n')
A = np.array(mid(A11)); G = np.array(mid(G11)); C = np.array(mid(CB))
ev, U = eigh(A, G); print("A11 gen eig:", ev[:4])
u0 = U[:, 0]; print("C_B on bottom:", (u0 @ C @ u0))
print("max radius A11:", max(float(A11[i, j].rad()) for i in range(k) for j in range(k)),
      " CB:", max(float(CB[i, j].rad()) for i in range(k) for j in range(k)))
tick('end')
