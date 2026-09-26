# Epstein lattice / Euler-product Weil control V1

Status: **T1 numerical diagnostic only**. No global Weil positivity and no RH
claim is made by this experiment.

## Why the D = -20 same-discriminant control is the clean comparison

For the principal binary quadratic form

[
Q_1(x,y)=x^2+5y^2,qquad D=-20,
]

the Epstein zeta is not itself an Euler product. The class-sum / Dedekind
control

[
A(s)=zeta(s)L(s,chi_{-20})
]

*is* an Euler product. Both have the same discriminant and therefore the same
completed degree-two conductor/gamma factor. This removes the conductor and
Archimedean term as explanations of a spectral difference.

Coefficientwise, the class-number-two decomposition is

[
E_{Q_1}(s)=A(s)+B(s),qquad
B(s)=L(s,chi_{-4})L(s,chi_5).
]

The test suite independently reconstructs the coefficients from lattice-point
counts and verifies this identity on a finite prefix.

## Exact finite arithmetic falsifier

Normalize (E_{Q_1}/2) so its first Dirichlet coefficient is one. Its first
coefficients include

- (a(2)=0),
- (a(3)=0),
- (a(4)=1),
- (a(5)=1),
- (a(6)=2).

For

[
-rac{F'}{F}(s)=sum_{nge 2}rac{Lambda_F(n)}{n^s},
]

the exact Dirichlet-convolution recurrence gives

[
Lambda_F(6)=2log 6
e0.
]

Because 6 is not a prime power, this is a finite certificate that the
principal Epstein zeta lacks an Euler product. By contrast, the same
finite-prefix checker finds prime-power-only support for
(zeta(s)L(s,chi_{-20})).

## Finite Galerkin control at L = 3.5

The probe uses the moment-zero family already used by the AEGIS
`krein_dual_beyond_log2.py` lane,

[
g=(1/4-D^2){sin(pi x/L)sin(kpi x/L)},
]

and the completed degree-two critical-line symbol

[
S_D(t)=2Repsi(1/2+it)
 +2lograc{sqrt{|D|}}{2pi}
 -2sum_{log n<L}rac{Lambda_F(n)}{sqrt n}cos(tlog n).
]

A CI-sized configuration (`basis_dim=24`, (T=600), (dt=0.05)) gives a
robust sign separation:

- principal (x^2+5y^2): minimum generalized eigenvalue < (-0.25);
- Euler class-sum (zeta L(chi_{-20})): minimum generalized eigenvalue > (+0.15);
- the principal negative minimizer evaluated on the Euler control is > (+1).

A stronger local stress run (not encoded as a CI threshold) with
`basis_dim=60`, (T=3000), (dt=0.02) gave approximately

- principal: (-0.4835724241);
- Euler class-sum: (+0.1958097947);
- same principal witness on Euler control: (+6.764880123).

These are floating-point finite-section diagnostics. The negative principal
witness is a concrete candidate for interval/ARB certification; the positive
Euler finite section is **not** a global positivity theorem.

## Independent zero-side check

Numerically, the principal (D=-20) Epstein zeta has an off-critical zero at

[
hoapprox
0.8231873164780866676470730774
+44.00011318023689727806224695,i.
]

At 80 decimal digits, evaluating

[
A(s)=zeta(s)L(s,chi_{-20}),qquad
B(s)=L(s,chi_{-4})L(s,chi_5)
]

via Hurwitz-zeta Dirichlet-(L) evaluation gives
(|A(ho)+B(ho)|<4	imes10^{-80}), while
(|A(ho)|=|B(ho)|approx0.7758158509) and
(A(ho)/B(ho)=-1) to the working precision. Thus the observed zero comes
from cancellation between two nonzero Euler-product components rather than a
zero of either component.

This numerical observation agrees with the classical
Davenport--Heilbronn/Voronin phenomenon for Epstein zeta functions of class
number greater than one.

## Next promotion step

Export the 60-dimensional negative principal witness and certify its quadratic
value with interval/ARB arithmetic, including a rigorous tail bound in (t).
Only that negative witness needs certification; no claim of positivity for the
Euler control is required for the falsifier.


## Optimizer-free seven-mode witness

A sparse integer witness removes generalized-eigensolver dependence from the
sign separation.  In the even modes

[
k=(4,6,8,10,12,16,18)
]

use the integer coefficient vector

[
c=(22,10,6,3,2,-2,-1).
]

For the committed CI-sized quadrature ((L,N,T,dt)=(3.5,24,600,0.05)), direct
Rayleigh evaluation gives approximately

- principal (x^2+5y^2): (-0.071782623);
- Euler class-sum (zeta(s)L(s,chi_{-20})): (+5.361928445).

The same vector therefore gives a large same-discriminant sign contrast without
calling an eigensolver during evaluation.  Independent stress checks show the
principal value moving toward roughly (-0.065) as (T) is increased from
600 to 20000, while halving the quadrature step from 0.05 to 0.0125 changes the
(T=600) value by only about (5.2	imes10^{-9}).

These stability checks are numerical, not interval bounds.  The next rigorous
promotion is now narrower: certify this fixed seven-mode quadratic value and an
upper bound for its omitted (t>T) tail.
