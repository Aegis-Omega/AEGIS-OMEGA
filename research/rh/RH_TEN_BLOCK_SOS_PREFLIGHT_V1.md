# RH Ten-Block Hermitian/SOS Preflight V1

Status: **EXACT_RATIONAL_PREFLIGHT_ONLY**

This artifact is intentionally downstream of the kernel-GREEN finite inputs and does **not**
assert an actual ten-packet theorem.

## Exact inputs

- diagonal candidate: `D = 5671/3200`;
- gaps 1–8 off-diagonal norm envelope: `c = 1/100`;
- gap 9 off-diagonal norm envelope: `c9 = 57/100`;
- gap-nine exact-source producer: `414a0120517fa3ae3354a31780c09e03a7fa5ff1`;
- gap-nine 42-module hosted replay: GREEN, axiom audit GREEN, `sorryAx` absent;
- fine-diagonal producer remains separately bound to its own exact source.

No receipt is transferred across theorem-source identities by this document.

## Comparison problem

For real coefficient magnitudes `x0,...,x9`, define

[
E_{10} = \sum_{i=0}^{9} x_i^2,
]

and the worst-case Hermitian cross envelope

[
C_{10}
=
2\left(
\frac1{100}
\sum_{\substack{0\le i<j\le9\\(i,j)\ne(0,9)}}x_i x_j
+
\frac{57}{100}x_0x_9
\right).
]

The proposed diagonal is

[
D=\frac{5671}{3200}.
]

## Exact SOS certificate

Set

[
m=\frac{3591}{3200}.
]

Then coefficient-by-coefficient over `Q`:

[
\boxed{
D E_{10} - C_{10} - mE_{10}
=
\frac1{100}\sum_{0\le i<j\le9}(x_i-x_j)^2
+
\frac{14}{25}
\left(
(x_0-x_9)^2+\sum_{i=1}^{8}x_i^2
\right)
}
]

and therefore the right-hand side is nonnegative.

Equivalently,

[
D E_{10}-C_{10}\ge \frac{3591}{3200}E_{10}.
]

The arithmetic is transparent:

[
\frac{5671}{3200}-\frac{3591}{3200}
=\frac{13}{20},
qquad
\frac{57}{100}-\frac1{100}
=\frac{14}{25}.
]

Endpoint row budgets are `13/20`; interior row budgets are only `9/100`.
The SOS certificate above uses the stronger common endpoint budget and leaves an
extra `14/25` square contribution on each interior coordinate.

## Boundary

This certificate proves only the exact rational **comparison matrix** is positive with margin
`3591/3200`, assuming the listed diagonal/cross envelopes.

It does **not** yet prove:

- translation of the gap-nine `57/100` bound to the concrete ten-packet endpoint pair;
- the actual 10×10 repository-`B` expansion;
- ten-packet coercivity for the concrete translated family;
- density/globalization;
- universal Weil sign;
- RH.

```
TEN_BLOCK_RATIONAL_SOS = PASS
CANDIDATE_MARGIN = 3591/3200
ACTUAL_TEN_PACKET_BINDING = NOT_PROVEN
GLOBAL_WEIL_SIGN = NOT_PROVEN
RH = NOT_PROVEN
AUTHORITY_EFFECT = NONE
```
