"""alpha_n = -(S_n + sigma_n) for |n| <= NP at L = 9/5, in integer fixed point (scale 2^P) with directed rounding:
the arithmetic a Lean kernel check would run, mirrored in Python. Every quantity is an integer interval [lo, hi]
with lo <= 2^P x <= hi.
  S_n     = (1/2) sum_j 2w/(c_j^2+w^2) - w g(n),  c_j = 1/2 + 2j, w = 2 pi n / L          (n >= 1; S_0 = 0)
            sum_j = head_{j<J} + phi10(w, c_J - 1) +- 20480 arctan(w/(c_J-1)) / (c_J^2+w^2)^6  (tail10_bracket)
            phi10(w, a) = arctan(w/a) + sum_{k<=5} 2 beta_k (2k-1)! Im[(a+iw)^{2k}] / (a^2+w^2)^{2k}
  g(n)    = sum_k e^{-c_k L} / (c_k^2 + w^2), remainder <= e^{-c_K L} / (c_K^2 (1 - e^{-2L}))
  sigma_n = sum_{q in 2,3,4,5} log(p) q^{-1/2} sin(w log q)
Checked against the Arb balls of feshbach_blocks (cvs_entries, 192 bits).  usage: tau80.py NP P TAILBITS [ARB_SRC_DIR]"""
import sys, math, time
from fractions import Fraction as F
NP = int(sys.argv[1]); P = int(sys.argv[2]); T = int(sys.argv[3]); DO_ARB = len(sys.argv) > 4
import os; os.environ['FX_P'] = str(P); sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fx import *
TWO_PI_OVER_L = PI * 2 * F(5, 9)
TAILC = 20480
def S_of(n):
    if n == 0: return I(0, 0)
    w = TWO_PI_OVER_L * n; w2 = w * w; wf = float(w.mid())
    # head length J: smallest J with c_J >= 2.5 and bound 20480 (pi/2) / (c_J^2 + w^2)^6 <= 2^-T
    J = 1
    while TAILC * 1.5708 / ((0.5 + 2 * J) ** 2 + wf * wf) ** 6 > 2.0 ** -T: J += 1
    head = I(0, 0)
    for j in range(J): head = head + (w * 2) / (w2 + F(1 + 4 * j, 2) ** 2)
    cJ = F(1 + 4 * J, 2); a = cJ - 1; a2 = a * a
    at = atan_iv(w / a)
    # Im[(a + i w)^{2k}] / (a^2+w^2)^{2k} = Im[u^{2k}], u = 1/(a - i w) = (a + i w)/(a^2 + w^2)
    rden = (w2 + a2).recip(); ur, ui = rden * a, w * rden
    pr, pi_ = I.q(1), I(0, 0); corr = I(0, 0)
    for k in range(5):
        for _ in range(2): pr, pi_ = pr * ur - pi_ * ui, pr * ui + pi_ * ur
        corr = corr + pi_ * COEF[k]
    d = w2 + cJ * cJ; d6 = d * d * d; d6 = d6 * d6
    err = (at * TAILC) / d6
    total = (head + at + corr).pm(I(0, err.hi))
    # geometric remainder g(n) = sum_k e^{-c_k L}/(c_k^2 + w^2)
    g = I(0, 0); ek = EHALF; K = 0
    while True:
        ck = F(4 * K + 1, 2); g = g + ek / (w2 + ck * ck); ek = ek * E2L; K += 1
        if ek.hi < (1 << 4): break
    ck = F(4 * K + 1, 2); gr = (ek / (I.q(1) - E2L)) * (1 / (ck * ck))   # e^{-c_K L}/(c_K^2 (1-e^{-2L}))
    g = g.pm(I(0, gr.hi + 1))
    return total.half() - w * g, J
def sigma_of(n):
    w = TWO_PI_OVER_L * n; return sum((W[q] * sin_iv(w * LOGQ[q]) for q in (2, 3, 4, 5)), I(0, 0))

t0 = time.time(); alpha = {}; Jmax = 0; wmax = 0; Jsum = 0
for n in range(NP + 1):
    S, J = S_of(n) if n else (I(0, 0), 0); a_ = -(S + sigma_of(n)); alpha[n] = a_
    Jmax = max(Jmax, J); Jsum += J; wmax = max(wmax, a_.w())
print(f'P={P} NP={NP}: {time.time() - t0:.1f}s, head terms max {Jmax}, total {Jsum}; max width 2^{math.log2(wmax) - P:.1f}')
if DO_ARB:
    sys.path.insert(0, sys.argv[4]); from flint import arb, acb, ctx
    import cvs_entries as gw
    ctx.prec = 192; Lb = arb(9) / 5; pi = arb.pi(); quarter = arb('0.25')
    Wb = {q: arb(p).log() * arb(q) ** arb('-0.5') for q, p in ((2, 2), (3, 3), (4, 2), (5, 5))}
    bad = 0; worst = 0
    for n in range(NP + 1):
        omega = 2 * pi * n / Lb; z = acb(quarter, pi * n / Lb)
        g_s = gw._geometric_remainders(n, Lb, ctx.prec)[0]
        S = arb('0.5') * z.digamma().imag - omega * g_s if n else arb(0)
        sig = sum((Wb[q] * (2 * pi * n * arb(q).log() / Lb).sin() for q in (2, 3, 4, 5)), arb(0))
        ab = -(S + sig); lo, hi = alpha[n].lo, alpha[n].hi
        al = arb(lo) / arb(2) ** P; ah = arb(hi) / arb(2) ** P
        if not ((ab.upper() >= al) and (ab.lower() <= ah)): bad += 1
        worst = max(worst, float(abs(ab.mid() - (al + ah) / 2).upper()))
    print(f'Arb (192 bits) vs integer intervals: non-overlapping {bad}/{NP + 1}; max |mid difference| {worst:.3e}')
import os, json
if os.environ.get('ALPHA_OUT'):
    with open(os.environ['ALPHA_OUT'], 'w') as fo:
        json.dump({'P': P, 'L': '9/5', 'tail_bits': T, 'lo': [str(alpha[n].lo) for n in range(NP + 1)], 'hi': [str(alpha[n].hi) for n in range(NP + 1)]}, fo)
    print('wrote', os.environ['ALPHA_OUT'])
