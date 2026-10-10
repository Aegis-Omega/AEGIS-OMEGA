# RH_SIGNED_FOUR_BLOCK_V1 — preformalization gate

Status: **PREFLIGHT COMPLETE / DO NOT FORMALIZE THE LEGACY 103/100 ROUTE**

Base: `4f1b52a454be9779bf39245cb4343d8d8e4b7270`

This artifact checks the proposed signed four-block continuation before spending
Lean proof-engineering effort.

## Actual matrix structure

For
`g_j = translatePacket g (j * log 2)`, `j=0,1,2,3`,
the already-proved translation-gap identity and Hermitian symmetry reduce the
actual complex matrix to the Hermitian Toeplitz form

```text
[ b0       b1       b2       b3      ]
[ conj b1  b0       b1       b2      ]
[ conj b2  conj b1  b0       b1      ]
[ conj b3  conj b2  conj b1  b0      ].
```

Thus the finite compression is determined by one real diagonal and three
complex gap values, not sixteen independent entries.

## Signed prime centers

The exact prime-source theorems already give real positive centers

```text
p1 = log(2)/sqrt(2)          (gap log 2)
p2 = log(2)/2                (gap 2 log 2)
p3 = log(2)*sqrt(2)/4        (gap 3 log 2).
```

The separated Archimedean theorem gives a complex residual of norm at most
`1/100 * E` at each nonzero gap.

Therefore, after normalizing by energy `E`, the nonzero-gap entries are
`p_k + δ_k`, with `|δ_k| <= 1/100`.

## Reversal-sector reduction

The real prime center commutes with reversal.  On the reversal-even sector its
2×2 matrix is

```text
[ p3      p1+p2 ]
[ p1+p2  p1    ].
```

Its largest eigenvalue is

```text
λ+ = (p1+p3 + sqrt((p1-p3)^2 + 4(p1+p2)^2))/2.
```

Numerically this is approximately `1.2132240865`.

The Python preflight does not rely on this decimal for authority.  Using only
existing rational enclosures

```text
693/1000 < log 2 < 7/10
7/5 < sqrt 2 < 10/7
```

it proves

```text
λ+(prime center) < 247/200 = 1.235.
```

The three Archimedean gap residuals have Hermitian perturbation operator norm
at most `3/100`, hence

```text
λmax(signed off-diagonal block) < 253/200 = 1.265.
```

## Gate result

### Legacy diagonal 103/100

The current `103/100` certificate does **not** force four-block negativity.

A stronger falsifier uses the all-ones Rayleigh direction.  Existing lower
bounds imply

```text
Rayleigh(prime center; 1,1,1,1) > 47817/40000 = 1.195425.
```

Even subtracting the full `3/100` Archimedean operator envelope and the
`103/100` diagonal leaves a positive certified margin

```text
5417/40000 = 0.135425 > 0.
```

This does **not** say the actual diagonal can never be stronger than 103/100.
It says the existing 103/100 certificate plus current signed gap information is
insufficient to prove the four-block compression negative.

Therefore formalizing `RH_SIGNED_FOUR_BLOCK_V1` on top of the unchanged
103/100 diagonal theorem is low-value.

### Narrow diagonal 32/25

The existing narrow-support lane gives `32/25 = 1.28`.  This clears the robust
signed threshold:

```text
32/25 - 253/200 = 3/200 > 0.
```

So the signed preflight passes there, but that lane already has a four-packet
coercivity theorem.  Re-formalizing the same fact through inertia would not
advance the global RH boundary by itself.

## Highest-value consequence

Do **not** spend the next proof cycle merely replacing absolute values by a
signed 4×4 matrix at the old 103/100 diagonal.

The useful next producer must change at least one of:

1. strengthen the generic diagonal certificate beyond the signed threshold;
2. obtain substantially sharper **signed** Archimedean information than the
   current norm disk;
3. change packet spacing/family so the prime Toeplitz center has a smaller
   largest eigenvalue;
4. use the already-closed finite family as an ingredient in the separate
   arbitrary-window / universal producer.

This is a preformalization falsifier, not an RH claim.

`AUTHORITY_EFFECT = NONE`
