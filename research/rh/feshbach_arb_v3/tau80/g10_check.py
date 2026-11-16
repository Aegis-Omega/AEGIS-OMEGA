"""Independent check of G10 in arbport/tail10/CvSArctanTail10V1.lean.
phi10(w, a) = arctan(w/a) - sum_{k<=5} beta_k f^(2k-1)(a), f(a) = 2w/(a^2+w^2) = 2 Im[(a - i w)^-1],
so f^(m)(a) = 2 Im[(-1)^m m! (a - i w)^(-m-1)] and the correction is sum_k 2 beta_k (2k-1)! Im[(a+iw)^(2k)]/(a^2+w^2)^(2k).
The Lean file claims it equals w a G10(a^2, w^2) / (3465 (a^2+w^2)^10).  usage: g10_check.py LEANFILE"""
import re, sys, sympy as sp
a, w, X, Y = sp.symbols('a w X Y', positive=True)
with open(sys.argv[1]) as f: src = f.read()
body = re.search(r'def G10 \(X Y : ℝ\) : ℝ :=\n(.*?)\n\n', src, re.S).group(1)
G10 = sp.sympify(body.replace('^', '**').replace('\n', ' '), locals={'X': X, 'Y': Y})
beta = [sp.Rational(-1, 12), sp.Rational(7, 720), sp.Rational(-31, 30240), sp.Rational(127, 1209600), sp.Rational(-73, 6842880)]
# beta_k = B_2k(1/2) 2^(2k-1)/(2k)!
assert all(beta[k - 1] == sp.bernoulli(2 * k, sp.Rational(1, 2)) * 2 ** (2 * k - 1) / sp.factorial(2 * k) for k in range(1, 6))
corr = sum(2 * beta[k - 1] * sp.factorial(2 * k - 1) * sp.im(sp.expand((a + sp.I * w) ** (2 * k))) / (a ** 2 + w ** 2) ** (2 * k) for k in range(1, 6))
claim = w * a * G10.subs({X: a ** 2, Y: w ** 2}) / (3465 * (a ** 2 + w ** 2) ** 10)
d = sp.simplify(sp.together(corr - claim))
print('beta_k = B_2k(1/2) 2^(2k-1)/(2k)!: OK;  correction - Lean R10 =', d)
