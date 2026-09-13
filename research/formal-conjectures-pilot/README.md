# AEGIS Formal Conjectures pilot

This pilot targets `google-deepmind/formal-conjectures` release
`bench-v1-lean4.27.0`, commit `7a41db3d761324599812d6ca6cb6a9f311046dc7`,
Lean `4.27.0`, mathlib `a3a10db0e9d66acbebf76c5e6a135066525ac900`.

## Exact tasks

| Target | Scope | Construction |
|---|---|---|
| `PellNumbers.pellNumber_sq_add_pellNumber_succ_sq` | Original textbook statement, unchanged | Simultaneous induction on odd/even double-index identities |
| `PellNumbers.coe_pellNumber_eq` | Original textbook statement, unchanged | Two-step induction; the roots `1 ± sqrt(2)` satisfy the recurrence |
| `AegisBench.green72_bound_counterexample` | Negates the `k=N=1` instance of `Green72.allowedSetSize_le` | The formal `AllowedSet` predicate admits a singleton, whose size contradicts the claimed zero upper bound |

The first two are known mathematical identities with missing proof bodies in the
selected snapshot. Filling their Lean proof bodies is formal proof engineering,
not a claim to new mathematics.

The third result concerns the benchmark's formalization. Its field named
`not_collinear` concludes `Collinear` and refers to the whole set `s` rather than
the selected subset `t`. The counterexample does not refute the intended geometric
no-three-in-line conjecture, and does not claim this issue was previously unknown.

The pilot also includes `AegisBench.transcendental_sum_or_product`: for real
numbers `a,b`, transcendence of `a` implies transcendence of `a+b` or `a*b`.
The proof uses `(a-b)^2 = (a+b)^2 - 4ab` and closure of algebraic numbers.
`pi_exp_sum_or_product_of_transcendental_pi` specializes this bridge with the
explicit hypothesis `Transcendental ℚ Real.pi`. A checked implication is not a
proof of that hypothesis and is not counted as another solved benchmark task.

The original candidate was
`Transcendental.exp_add_pi_or_exp_add_mul_transcendental`. This pilot does not
provide a checked proof of it. No unresolved premise is introduced as an axiom.

## Reproduction

1. Clone the exact benchmark commit and install Lean 4.27.0.
2. Run `python prepare.py /path/to/benchmark` from this directory.
3. In the benchmark directory, run:

```sh
lake exe cache get
lake build FormalConjectures/Wikipedia/Pell.lean FormalConjectures/GreensOpenProblems/72.lean
lake env lean AegisAudit.lean > axioms.log
python /path/to/this/directory/verify.py axioms.log /path/to/benchmark
```

`prepare.py` changes only the two selected Pell proof bodies. It preserves their
original names, quantifiers, conclusions and definitions. The Green source stays
unchanged. `Audit.lean` imports the resulting modules and requests a transitive
axiom report for each target. Other unresolved benchmark declarations may still
exist in those modules; the targets must not depend on them.

`verify.py` rejects missing reports and any axiom outside `propext`,
`Classical.choice`, and `Quot.sound`. In particular, `sorryAx` and native evaluation
trust axioms are rejected. These ordinary Lean/mathlib assumptions are disclosed,
not described as an axiom-free foundation.

The workflow compiles selected modules, not the entire 2,615-statement benchmark.
These selected tasks do not define a representative benchmark score.

RH remains NOT_PROVEN. External ASTRA evidence is untouched. No merge, release,
claim promotion or expansion of authority is part of this pilot.

## Vega argument counterexamples

These are supporting audit results, not additional Formal Conjectures benchmark solutions.
`AegisBench.Vega.bfs_false_positive` transcribes the state transitions and acceptance
condition from Theorem 2, page 4, of Frank Vega's *Note for the P versus NP Problem*,
version 10, DOI 10.20944/preprints201908.0037.v10:
https://www.preprints.org/manuscript/201908.0037/v10/download
The printed f/g definitions use OR notation despite the XOR problem definition;
we interpret them as the intended counts of incident XOR clauses. On edges
(1,2), (1,3), (1,4), (2,3), assignment (0,1,1,0) reaches (4,2,0,0).
The formula itself is unsatisfiable. This checks the mathematical recurrence,
not execution of the unavailable ALMA implementation. No state merging is needed.

`missing_margin_counterexample` refutes the abstract inference from A>0, E>1,
and A<EA to 1+A<EA using A=1 and E=3/2. It addresses the inference on pages
8–9 of *Note for the Millennium Prize Problems*, version 6, DOI
10.33774/coe-2024-xjsk1-v6. It does not refute the prime-specific inequality
or RH. Version 6 no longer contains the BFS algorithm and uses K-CLOSURE,
so the earlier Dominating Set counterexample must not be attributed to its Lemma 3.

### Structural explanation and valid replacement checks

`balance_counts` proves for every list of Boolean endpoint pairs that the summed
per-edge r contribution equals count(11) minus count(00). Thus zero total balance
allows equally many violations of opposite kinds. `run_balance_binding` binds this
edge sum (and its negative for t) to the four-variable recurrence for all 16
assignments. This binding is specific to that graph; the arbitrary-graph
vertex-sum/edge-sum equivalence is not claimed as a Lean theorem here.
`checkClauses_correct` proves an executable clause-by-clause checker accepts
exactly when every endpoint pair differs. This is a certificate checker, not a
completeness proof for a modified search or a P-versus-NP result.
`reciprocal_margin_iff` proves the exact equivalence, for real E>1,
1/(E-1)<A iff 1+A<E*A. Establishing this inequality for the manuscript's
prime-dependent quantities remains a separate obligation.


## Complete reference solver

`solve` enumerates all Boolean assignments to `Fin n` and uses `checkAssignment`
to check every XOR clause and the at-most-k count. `solve_correct` proves for
arbitrary n, clause list and k that the result is true if and only if a valid
assignment exists. This closes soundness and completeness for the reference
solver, including empty instances, isolated variables, repeated edges and loops.
It is an exhaustive 2^n-assignment baseline; no polynomial-time complexity is
claimed. It is intended for small instance cross-checks, not large inputs.
The executable examples reject the Vega false-positive graph and check empty
instances and budgets of zero and one. The theorem does not certify any external
solver implementation or resolve P versus NP.

`degree_balance_counts` now proves the forward/backward endpoint-count sum equals
count(11)-count(00) for any finite indexed vertex set and edge list. The proof
passes through `vertexSumR`, an algebraic sum of per-vertex increments, and proves
its equality to the per-edge sum. This generalizes the earlier four-variable
algebraic binding. A theorem equating an arbitrary operational fold with that
terminal sum has not been added; the existing concrete fold binding is retained.
Edge lists are counted with multiplicity in this identity; the manuscript's
simple graph convention is included when each ordered edge occurs once.
