"""Diagonal inputs CC_n, XC_n (|n| <= N) of feshbach_blocks at L = 9/5 in integer fixed point (fx.py).
  Re psi(1/4+it) - psi(1/4) = sum_j f1(c_j),  f1(c) = 2w^2/(c(c^2+w^2)) = 2/c - 2 Re[(c - i w)^-1]
  Re psi'(1/4+it)          = sum_j f2(c_j),  f2(c) = 4 Re[(c - i w)^-2]               (c_j = 1/2 + 2j, w = 2t)
  midpoint Euler-Maclaurin from a = c_J - 1, step 2, order 10 (u = 1/(a - i w)):
    sum_{j>=J} f1 = (1/2) log(1 + w^2/a^2) + sum_k 2 beta_k (2k-1)! (a^-2k - Re u^2k) +- 16/a^10
    sum_{j>=J} f2 = 2 Re u + sum_k 4 beta_k (2k)! Re u^(2k+1) +- 156/a^11
  with |R| <= |B_10| 2^9/10! int_a^oo |f^(10)|,  |f1^(10)| <= 4 10!/x^11,  |f2^(10)| <= 4 11!/x^12.
  CC = -(1/2) sum f1 + g_cc (n != 0; CC_0 = 0),  XC = (1/4) sum f2 - L g_x1 - g_x2, with (g_s, g_cc, g_x1, g_x2) =
  cvs_entries._geometric_remainders sums[0..3] as unpacked in v8 seqs: g_cc = sum e w^2/(c(c^2+w^2)), g_x1 = sum e c/(c^2+w^2)
usage: diag80.py N P TAILBITS [ARB_SRC_DIR]"""
import sys, os, math, time, json
N = int(sys.argv[1]); P = int(sys.argv[2]); T = int(sys.argv[3]); DO_ARB = len(sys.argv) > 4
os.environ['FX_P'] = str(P); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx import *
TWO_PI_OVER_L = PI * 2 * F(5, 9)
def log_iv(y):                     # y >= 1 interval: log y = k log 2 + 2 atanh((z-1)/(z+1)), z = y/2^k in [1, 2)
    k = 0
    while y.lo >= 2 * ONE: y = y.half(); k += 1
    x = (y - 1) / (y + 1); s = I(0, 0); t = x; x2 = x * x; terms = P // 2 + 8
    for j in range(terms): s = s + t / (2 * j + 1); t = t * x2
    s = s.pm(I(0, t.hi // (2 * terms + 1) * 2 + 1))      # remainder <= t/((2terms+1)(1-x^2)), x <= 1/3
    return s * 2 + LN2 * k
def em_sums(n, w, w2):
    J = 1
    while 16 / (0.5 + 2 * J - 1) ** 10 > 2.0 ** -T or 156 / (0.5 + 2 * J - 1) ** 11 > 2.0 ** -T: J += 1
    h1 = I(0, 0); h2 = I(0, 0)
    for j in range(J):
        c = F(1 + 4 * j, 2); d = (w2 + c * c).recip()
        h1 = h1 + (w2 * 2) * d * (1 / c)                 # 2 w^2 / (c (c^2 + w^2))
        h2 = h2 + ((I.q(c * c) - w2) * d * d) * 4      # 4 (c^2 - w^2)/(c^2 + w^2)^2
    a = F(1 + 4 * J, 2) - 1; rden = (w2 + a * a).recip(); ur, ui = rden * a, w * rden
    t1 = log_iv(I.q(1) + w2 * (1 / (a * a))).half(); t2 = ur * 2
    pr, pim = ur, ui                                    # u^1
    for k in range(1, 6):
        q2r, q2i = pr * ur - pim * ui, pr * ui + pim * ur   # u^(2k)
        t1 = t1 + (I.q(1 / a ** (2 * k)) - q2r) * (2 * BETA[k - 1] * math.factorial(2 * k - 1))
        q3r, q3i = q2r * ur - q2i * ui, q2r * ui + q2i * ur  # u^(2k+1)
        t2 = t2 + q3r * (4 * BETA[k - 1] * math.factorial(2 * k))
        pr, pim = q3r, q3i
    t1 = t1.pm(I.q(F(16) / a ** 10)); t2 = t2.pm(I.q(F(156) / a ** 11))
    return h1 + t1, h2 + t2, J
def geo(n, w2):
    gcc = I(0, 0); gx1 = I(0, 0); gx2 = I(0, 0); ek = EHALF; K = 0
    while True:
        c = F(4 * K + 1, 2); d = (w2 + c * c).recip()
        if n: gcc = gcc + ek * w2 * d * (1 / c)          # cvs_entries sums[1]: w^2/(c (c^2+w^2))
        gx1 = gx1 + ek * d * c                           # sums[2]: c/(c^2+w^2)
        gx2 = gx2 + ek * (I.q(c * c) - w2) * d * d
        ek = ek * E2L; K += 1
        if ek.hi < (1 << 4): break
    r = I(0, ((ek / (I.q(1) - E2L)) * 4).hi + 1)
    return gcc.pm(r), gx1.pm(r), gx2.pm(r)
t0 = time.time(); CC = {}; XC = {}; Jmax = 0; wmax = 0
for n in range(N + 1):
    w = TWO_PI_OVER_L * n; w2 = w * w
    s1, s2, J = em_sums(n, w, w2); gcc, gx1, gx2 = geo(n, w2)
    CC[n] = (gcc - s1.half()) if n else I(0, 0)
    XC[n] = (s2.half().half()) - gx1 * F(9, 5) - gx2
    Jmax = max(Jmax, J); wmax = max(wmax, CC[n].w(), XC[n].w())
print(f'P={P} N={N}: {time.time() - t0:.1f}s, head terms {Jmax}; max width 2^{math.log2(wmax) - P:.1f}')
if DO_ARB:
    sys.path.insert(0, sys.argv[4]); from flint import arb, acb, ctx
    import cvs_entries as gw
    ctx.prec = 192; Lb = arb(9) / 5; pi = arb.pi(); quarter = arb('0.25'); psi_q = quarter.digamma(); bad = 0; worst = 0
    for n in range(N + 1):
        z = acb(quarter, pi * n / Lb); psi = z.digamma(); g_s, g_cc, g_x1, g_x2 = gw._geometric_remainders(n, Lb, ctx.prec)
        cc = -arb('0.5') * (psi.real - psi_q) + g_cc if n else arb(0)
        xc = arb('0.25') * z.polygamma(acb(1)).real - Lb * g_x1 - g_x2
        for ref, iv in ((cc, CC[n]), (xc, XC[n])):
            lo = arb(iv.lo) / arb(2) ** P; hi = arb(iv.hi) / arb(2) ** P
            if not (ref.upper() >= lo and ref.lower() <= hi): bad += 1
            worst = max(worst, float(abs(ref.mid() - (lo + hi) / 2).upper()))
    print(f'Arb (192 bits) vs integer intervals: non-overlapping {bad}/{2 * (N + 1)}; max |mid difference| {worst:.3e}')
if os.environ.get('DIAG_OUT'):
    with open(os.environ['DIAG_OUT'], 'w') as fo:
        json.dump({'P': P, 'L': '9/5', 'tail_bits': T, 'CC': [[str(CC[n].lo), str(CC[n].hi)] for n in range(N + 1)],
                   'XC': [[str(XC[n].lo), str(XC[n].hi)] for n in range(N + 1)]}, fo)
    print('wrote', os.environ['DIAG_OUT'])
