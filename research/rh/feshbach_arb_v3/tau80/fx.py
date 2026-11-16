"""Shared integer-interval fixed point (scale 2^P, P from env FX_P) and rigorous constants for the tau80/diag80 mirrors."""
import os, math
from fractions import Fraction as F
P = int(os.environ["FX_P"])
ONE = 1 << P
def fl(fr): return (fr.numerator << P) // fr.denominator
def ce(fr): return -((-fr.numerator << P) // fr.denominator)
class I:
    __slots__ = ('lo', 'hi')
    def __init__(s, lo, hi): assert lo <= hi; s.lo, s.hi = lo, hi
    @staticmethod
    def q(fr): fr = F(fr); return I(fl(fr), ce(fr))
    def __add__(s, o): o = o if isinstance(o, I) else I.q(o); return I(s.lo + o.lo, s.hi + o.hi)
    __radd__ = __add__
    def __neg__(s): return I(-s.hi, -s.lo)
    def __rsub__(s, o): return I.q(o) - s
    def __sub__(s, o): return s + (-(o if isinstance(o, I) else I.q(o)))
    def __mul__(s, o):
        if not isinstance(o, I):
            o = F(o)
            if o.denominator == 1:
                k = o.numerator; return I(s.lo * k, s.hi * k) if k >= 0 else I(s.hi * k, s.lo * k)
            o = I.q(o)
        p = (s.lo * o.lo, s.lo * o.hi, s.hi * o.lo, s.hi * o.hi)
        return I(min(p) >> P, -((-max(p)) >> P))
    __rmul__ = __mul__
    def recip(s):
        assert s.lo > 0; return I((ONE * ONE) // s.hi, -((-ONE * ONE) // s.lo))
    def __truediv__(s, o):
        if isinstance(o, int): assert o > 0; return I(s.lo // o, -((-s.hi) // o))
        if isinstance(o, F): return s * (1 / o)
        return s * o.recip()
    def half(s): return I(s.lo >> 1, -((-s.hi) >> 1))
    def w(s): return s.hi - s.lo
    def pm(s, e): return I(s.lo - e.hi, s.hi + e.hi)          # widen by a nonnegative bound e
    def mid(s): return F(s.lo + s.hi, 2 * ONE)

# --- constants with rigorous rational enclosures ---------------------------------------------------------------
def atan_rec(x, terms):           # alternating series for 0 < x <= 1/2; returns enclosure of atan(1/x)? no: atan(x)
    s = F(0); t = x
    for k in range(terms): s += (-1) ** k * t / (2 * k + 1); t *= x * x
    r = t / (2 * terms + 1)                                   # |remainder| <= next term
    return I(fl(s - r), ce(s + r))
def atanh_q(x, terms):            # 0 < x < 1/2, positive series, remainder <= geometric
    s = F(0); t = x
    for k in range(terms): s += t / (2 * k + 1); t *= x * x
    r = t / (2 * terms + 1) / (1 - x * x)
    return I(fl(s), ce(s + r))
NT = P // 2 + 10
PI = atan_rec(F(1, 5), NT) * 16 - atan_rec(F(1, 239), NT) * 4
LN2 = atanh_q(F(1, 3), NT) * 2; LN3 = LN2 + atanh_q(F(1, 5), NT) * 2; LN5 = LN2 * 2 + atanh_q(F(1, 9), NT) * 2
def isqrt_iv(fr):                 # enclosure of sqrt(fr) * 2^P
    lo = math.isqrt(fl(fr) << P); hi = math.isqrt(ce(fr) << P) + 1; return I(lo, hi)
L = F(9, 5)
def exp_neg(x, terms=None):       # e^{-x}, rational x > 0, via e^{-x} = (e^{-x/2^m})^{2^m}
    m = 4; y = x / 2 ** m; s = F(0); t = F(1)
    for k in range(P // 4 + 20): s += t; t = -t * y / (k + 1)
    r = abs(t); e = I(fl(s - r), ce(s + r))
    for _ in range(m): e = e * e
    return e
EHALF = exp_neg(L / 2); E2L = exp_neg(2 * L)
W = {2: LN2 * isqrt_iv(F(1, 2)), 3: LN3 * isqrt_iv(F(1, 3)), 4: LN2 * F(1, 2), 5: LN5 * isqrt_iv(F(1, 5))}
LOGQ = {2: LN2, 3: LN3, 4: LN2 * 2, 5: LN5}
BETA = [F(-1, 12), F(7, 720), F(-31, 30240), F(127, 1209600), F(-73, 6842880)]
COEF = [2 * BETA[k] * math.factorial(2 * k + 1) for k in range(5)]   # k index 0..4 -> 2 beta (2k+1)!, power 2(k+1)

def atan_iv(x):                   # x interval, x > 0
    def ser(y, terms=P // 2 + 8):  # |y| <= 1/2 (interval), alternating Taylor
        s = I(0, 0); t = y; y2 = y * y
        for k in range(terms): s = s + (t / (2 * k + 1) if k % 2 == 0 else -(t / (2 * k + 1))); t = t * y2
        e = I(0, max(abs(t.lo), abs(t.hi)) // (2 * terms + 1) + 1); return s.pm(e)
    if x.hi <= ONE // 2: return ser(x)
    if x.lo >= 2 * ONE: return PI.half() - ser(x.recip())
    return PI.half().half() + ser((x - 1) / (x + 1))        # (x-1)/(x+1) in [-1/3, 1/3]
def sin_iv(x):
    m = round(float(x.mid()) / (2 * float(PI.mid())))
    y = x - PI * (2 * m)                                   # |y| <= pi + tiny
    s = I(0, 0); t = y; y2 = y * y; f = 1
    for j in range(1, 2 * (P // 3) + 40, 2):
        s = s + (t / f if (j // 2) % 2 == 0 else -(t / f)); t = t * y2; f *= (j + 1) * (j + 2)
    e = I(0, max(abs(t.lo), abs(t.hi)) // f + 1); return s.pm(e)

