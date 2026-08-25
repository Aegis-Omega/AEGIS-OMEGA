# Shard-Closure Sharding Deadlocks on Real Dependency Graphs

**A measured refutation of the cut-set admissibility protocol, and the cost of the
partition that repairs it.**

Status: **VERIFIED_NUMERICAL** (T1 — empirically validated, single platform).
Reproduction harness and raw results ship alongside this document.

---

## Abstract

Holonic and multi-agent architecture proposals routinely specify that a task graph
be partitioned into shards, and that a shard becomes executable once its
cross-shard dependencies are resolved. We state that rule as a checkable
predicate, implement it, and run it against four real module-dependency graphs
extracted from this repository (n = 666 nodes, m = 887 edges across TypeScript,
Rust, and Python).

The protocol does not merely underperform. **It deadlocks.** All four source graphs
are acyclic, yet a uniformly random k-partition produced a schedulable quotient in
**0 of 200 draws at every k ∈ {2, 4, 8, 16, 32, 39, 64, 128}** on the largest
TypeScript graph, and 0 of 200 at eight of nine k values on the largest Rust graph.
The mechanism is elementary and we give a three-node witness: *the quotient of a DAG
by an arbitrary partition need not be a DAG.* No paper we are aware of that
specifies this predicate states the acyclic-quotient requirement that makes it
well-posed.

Repairing the protocol with a topological-order oracle partition eliminates
deadlock by construction and then costs, at an identical parallelism budget k,
between **1.33× and 7.56×** the makespan of ordinary node-level list scheduling on
the same graph. At k = 39 — the deployed department count in this repository —
node-level scheduling reaches the critical-path optimum exactly (T = D = 10) while
the shard protocol needs 65 units, a **6.50× penalty**. As k → n the protocol
converges to node-level scheduling precisely because the decomposition has
disappeared.

We also report two closed-form models we derived for the deadlock probability and
**both are refuted as bounds by our own measurement**, with the failure diagnosed.

---

## 1. The claim under test

Stated in the source literature as: *"the matrix must identify 'leaky' boundary
nodes — nodes whose dependencies span across shard boundaries. These cross-shard
dependencies must be resolved before a shard can be executed in isolation."*

We formalize it. Let `G = (V, E)` be the dependency graph, edge `p → q` meaning
*p must finish before q*. Let `S : V → {0..k−1}` be a partition into k shards.
Define the quotient `G/S` with an edge `S_a → S_b` iff some `p ∈ S_a`, `q ∈ S_b`,
`a ≠ b`, `p → q ∈ E`.

> **Cut-set admissibility.** Shard `s` may execute iff every shard it depends on in
> `G/S` has finalized.

This is the only load-bearing formal object in the source material: everything else
in those proposals is either a definition restated in matrix notation or a citation.

**H₁ (the proposals' implicit hypothesis).** Under cut-set admissibility, sharding a
task graph into k shards yields parallel speedup over sequential execution.

**Falsifier, pre-committed.** H₁ fails if, at the same parallelism budget k,
cut-set admissibility does not beat ordinary node-level list scheduling on the same
graph. It fails *catastrophically* if the predicate is unsatisfiable.

## 2. Method

### 2.1 Data — four real graphs, no synthetic input

Node = source file. Edge `u → v` = *u imports v*, extracted by static parse
(`extract.py`): TypeScript `import/export … from` plus dynamic `import()` with the
repository's `.js`-suffix convention resolved; Rust `use crate::…` resolved against
the module tree by longest matching prefix; Python `import` / `from … import`.

| graph | root | n | m | density | critical path D | cyclic nodes |
|---|---|---:|---:|---:|---:|---:|
| `ts_sovereign` | `sovereign-omega-v2/src` | 193 | 559 | 2.90 | 10 | 0 |
| `rust_cl_psi` | `aegis-cl-psi/src` | 423 | 277 | 0.65 | 12 | 0 |
| `rust_runtime` | `aegis-runtime/src` | 14 | 8 | 0.57 | 2 | 0 |
| `py_sovereign` | `sovereign-omega-v2/python` | 36 | 43 | 1.19 | 4 | 0 |

**All four are acyclic.** This matters: every deadlock reported below is created by
the partition, not inherited from the graph.

### 2.2 Cost model — deliberately favourable to H₁

Unit cost per node. Unlimited workers within a round. **Zero** communication cost,
**zero** serialization cost, **zero** orchestrator cost. A perfect scheduler with
full global knowledge. Every one of these assumptions favours the sharding thesis,
so a negative result under them is stronger than one under realistic costs.

Four quantities, all in the same units:

| symbol | meaning |
|---|---|
| `T₁ = n` | monolith, sequential |
| `T_dag(k)` | node-level list scheduling, k workers, **no shard protocol** |
| `T_shard(k)` | cut-set admissibility, k shards, shard atomic; round cost = largest shard in the round |
| `T_∞ = D` | critical-path depth — the unit-cost lower bound |

`T_dag(k)` is the control. It spends the same parallelism budget k on the same
graph and is what any ordinary work queue already does.

### 2.3 Partition strategies

`random` (uniform, seeded), `block` (contiguous in file order), `topo` (contiguous
blocks in a global topological order — an **oracle**, see §5).

Determinism: all randomness from `numpy.default_rng(seed)`, `seed = 20260825`
recorded in the harness. No wall-clock anywhere; nothing in this measurement reads
a system time.

## 3. Result 1 — the predicate is unsatisfiable on real graphs

**Minimal witness.** `a → b → c`, acyclic. Partition `{a, c}` and `{b}`. Shard 0
depends on shard 1 (c needs b); shard 1 depends on shard 0 (b needs a). Neither is
ever admissible. `supplement.py` asserts the source graph is acyclic and reports
`DEADLOCK`.

> **The quotient of a DAG by an arbitrary partition need not be a DAG.**

`P[a uniformly random k-partition yields a schedulable quotient]`, 200 draws per
cell:

| k | 2 | 4 | 8 | 16 | 32 | 39 | 64 | 128 | 256 |
|---|---|---|---|---|---|---|---|---|---|
| `ts_sovereign` (n=193) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | — |
| `rust_cl_psi` (n=423) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.050 |
| `py_sovereign` (n=36) | 0.000 | 0.000 | 0.005 | 0.030 | 0.355 | — | — | — | — |
| `rust_runtime` (n=14) | 0.750 | 0.840 | 0.930 | — | — | — | — | — | — |

`rust_runtime` is the control that proves the mechanism: at n = 14 with m = 8 edges
there is almost nothing to coordinate, and the protocol works. Everywhere a real
dependency structure exists, it does not.

`block` partitioning — the naive structural strategy — deadlocked in every cell
tested on the three larger graphs.

### 3.1 Scaling: the collapse is governed by edge count, not node count

Induced subgraphs drawn uniformly, k = 8 fixed, 300 draws per size, cyclic draws
discarded:

| `ts_sovereign` n | 9 | 19 | 28 | 38 | 57 | 77 | 115 | 154 | 193 |
|---|---|---|---|---|---|---|---|---|---|
| mean edges | 1.0 | 5.1 | 11.3 | 21.5 | 50.6 | 87.2 | 199.4 | 352.1 | 559.0 |
| P[schedulable] | 0.990 | 0.920 | 0.660 | 0.263 | 0.023 | 0.000 | 0.000 | 0.000 | 0.000 |

| `rust_cl_psi` n | 21 | 42 | 63 | 84 | 126 | 169 | 253 | 338 | 423 |
|---|---|---|---|---|---|---|---|---|---|
| mean edges | 0.6 | 2.6 | 6.2 | 10.6 | 24.6 | 43.9 | 97.1 | 175.4 | 277.0 |
| P[schedulable] | 1.000 | 0.933 | 0.763 | 0.483 | 0.073 | 0.003 | 0.000 | 0.000 | 0.000 |

Both graphs cross P = 0.5 at roughly **m ≈ 10–20 edges** despite a 4× difference in
node count at that point. The binding variable is m, not n.

## 4. Result 2 — the repaired protocol is strictly dominated

The `topo` oracle partition — contiguous blocks of a global topological order —
cannot produce a cyclic quotient, so deadlock is eliminated by construction. What
it costs, at the same k:

| graph | k | `T_shard` | `T_dag` | D | **protocol penalty** | `T_dag` off optimum |
|---|---:|---:|---:|---:|---:|---:|
| `ts_sovereign` | 8 | 169 | 27 | 10 | **6.26×** | 2.70× |
| | 16 | 121 | 16 | 10 | **7.56×** | 1.60× |
| | 32 | 67 | 11 | 10 | **6.09×** | 1.10× |
| | **39** | **65** | **10** | **10** | **6.50×** | **1.00×** |
| | 64 | 52 | 10 | 10 | **5.20×** | 1.00× |
| `rust_cl_psi` | 16 | 159 | 33 | 12 | **4.82×** | 2.75× |
| | 32 | 121 | 22 | 12 | **5.50×** | 1.83× |
| | **39** | **76** | **20** | **12** | **3.80×** | 1.67× |
| | 64 | 48 | 17 | 12 | **2.82×** | 1.42× |
| `py_sovereign` | 8 | 32 | 5 | 4 | **6.40×** | 1.25× |
| | 16 | 24 | 4 | 4 | **6.00×** | 1.00× |
| `rust_runtime` | 8 | 4 | 3 | 2 | **1.33×** | 1.50× |

Penalty range across all cells: **1.33× to 7.56×**. The protocol never wins.

The k = 39 row is the operationally relevant one — that is the deployed department
count. On `ts_sovereign`, node-level scheduling at k = 39 attains the critical-path
optimum exactly (`T_dag = D = 10`); the shard protocol needs 65.

### 4.1 The protocol converges to the baseline only by dissolving

At `k = n` (identity partition, one node per shard):

| graph | `T_shard` | `T_dag` | D |
|---|---:|---:|---:|
| `ts_sovereign` | 10 | 10 | 10 |
| `rust_cl_psi` | 12 | 12 | 12 |
| `py_sovereign` | 4 | 4 | 4 |
| `rust_runtime` | 2 | 2 | 2 |

`T_shard = T_dag = D` exactly, on all four. The protocol becomes safe and optimal
at precisely the point where the decomposition it exists to implement no longer
exists.

### 4.2 Robustness: the charitable reading collapses into the control

Shard atomicity could be read as optional — perhaps a shard may be entered, blocked
mid-execution, and resumed. But a non-atomic shard whose nodes are individually
gated on their own dependencies **is** node-level list scheduling, which is exactly
our `T_dag` control. Under the atomic reading the protocol deadlocks (§3); under
the non-atomic reading it *is* the baseline and contributes nothing. There is no
third reading in which it adds value.

## 5. What survives: a corrected, checkable invariant

The predicate is not unsalvageable — it is under-specified. What the source
material omits, and what makes it well-posed:

> **Admissible-partition invariant.** A partition `S` is admissible for
> `G` iff the quotient `G/S` is acyclic.

This is checkable in `O(n + m)` by Kahn's algorithm on the quotient, and it catches
a real, silent, currently-unstated failure class. Our recommendation is therefore
**split**:

- **Keep it as a safety gate.** It is cheap, it is decidable, and without it the
  protocol admits partitions that can never run. Any system implementing shard
  closure should reject a partition whose quotient is cyclic at admission time, not
  discover it as a hang at run time.
- **Drop it as a performance mechanism.** §4 measures the cost of the only
  partitions that satisfy it, and they lose to an ordinary work queue at the same
  budget in every cell we ran.

One further consequence deserves naming. The only non-deadlocking strategy we found
requires a **global topological order of the entire dependency graph**. An
orchestrator that can compute that already holds the complete global dependency
structure — the monolithic global view that decomposition was introduced to avoid.
The repair is available only to a coordinator that does not need the decomposition.

## 6. Two models we derived, and both are refuted

We attempted a closed form for `P[schedulable]`, treating reciprocated shard pairs
as Poisson with rate λ and predicting `P ≤ exp(−λ)`.

**Model 1 (uniform).** Each of m edges lands on a uniformly random ordered pair of
distinct shards; `λ = m(m−1) / (2k(k−1))`.
**Refuted.** The bound was violated in **6 of 18** cells, worst case
`P_obs − P_pred = +0.305`.

**Model 2 (structure-aware).** Case analysis on shared endpoints: two edges sharing
a source, or sharing a target, can *never* reciprocate (both require
`part(p) = part(q)`, contradicting the cross-shard condition); 2-paths reciprocate
with probability `(k−1)/k²`, disjoint pairs with `(k−1)/k³`.
**Also refuted.** Violated in **7 of 18** cells, worst case `+0.279`. Directionally
correct — it lowered λ, and hub-heavy `ts_sovereign` gained more than sparse
`rust_cl_psi`, as predicted — but nowhere near sufficient.

**Diagnosis, measured not assumed.** We instrumented the true reciprocated-pair
count `N` directly (2000 draws per cell):

| graph | n | mean N | var N | var/mean | P[N=0] observed | exp(−mean N) |
|---|---:|---:|---:|---:|---:|---:|
| `ts_sovereign` | 28 | 0.456 | 0.599 | 1.31 | 0.6735 | 0.6338 |
| `ts_sovereign` | 38 | 1.101 | 1.436 | 1.30 | 0.3750 | 0.3325 |
| `ts_sovereign` | 57 | 3.755 | 4.668 | 1.24 | 0.0340 | 0.0234 |
| `rust_cl_psi` | 84 | 0.787 | 1.014 | 1.29 | 0.4990 | 0.4550 |
| `rust_cl_psi` | 126 | 2.584 | 3.458 | 1.34 | 0.1130 | 0.0754 |

Two independent errors, both now identified:

1. **The combinatorics over-count by saturation.** Model 2 predicted λ = 3.09 at
   `ts_sovereign` n = 38 where the measured mean is 1.10 (2.8× high), and λ = 17.1
   at n = 57 where the measured mean is 3.76 (4.6× high) — the ratio grows with m.
   Cause: many distinct reciprocating *edge pairs* collapse onto the same *shard
   pair*, and the observable is capped at `C(k,2) = 28`. We counted edge pairs; the
   deadlock depends on shard pairs.
2. **The Poisson step is mildly wrong.** `var/mean ∈ [1.01, 1.34]` — over-dispersed,
   because reciprocation events share edges and vertices and are positively
   correlated. Over-dispersion pushes `P[N = 0]` **above** `exp(−E[N])`, and indeed
   `P_obs ≥ exp(−mean N)` in every cell.

Given the *measured* λ, `exp(−λ)` predicts `P` to within 0.04 absolute. So the
Poisson skeleton is close to right and our combinatorial estimate of λ is what
failed. We report this rather than tuning a third model: the empirical result in
§3 and §4 does not depend on any of it.

## 7. Threats to validity

- **Unit costs.** Real nodes differ in cost. This is favourable to H₁ (unequal
  shard sizes make the atomic-round cost worse, not better), so correcting it can
  only strengthen the negative result.
- **Import graphs are a proxy** for agent task graphs. They are real, large, and
  independently sourced, but they are not agent workloads. The deadlock mechanism
  is structural and does not depend on what the nodes are; the *penalty magnitudes*
  in §4 do.
- **Single platform.** Deterministic and seeded, but run on one machine. T1, not
  T0; cross-platform byte-identical replay would be required for promotion.
- **`topo` is one oracle among many.** A better partitioner may reduce the penalty.
  It cannot eliminate it: shard atomicity forces every node in a shard behind the
  shard's slowest predecessor, which node-level scheduling does not.
- **Static import extraction** may miss dynamic or conditional dependencies. Missing
  edges would *raise* P[schedulable], so the true deadlock rate is at least what we
  report.

## 8. Conclusion

The cut-set admissibility predicate, as specified in the holonic-architecture
literature, is not a performance mechanism. On four real dependency graphs it is
unsatisfiable under every partition strategy except a global-topological-order
oracle, at a measured rate of 0 successes in 200 draws across eight partition
counts on the largest graph. Given the oracle, it is strictly dominated by ordinary
node-level list scheduling at an identical parallelism budget, by 1.33× to 7.56×,
and by 6.50× at the operationally deployed k = 39.

Its salvageable content is one line — *the quotient must be acyclic* — which is
worth keeping as an `O(n + m)` admission gate and is not stated in the source
material.

We note without further comment that the source proposals for this mechanism
contain no experiment, no baseline, and no n.

## 9. Reproduction

```bash
cd research/shard-closure
python extract.py graphs.json          # rebuild graphs from the live tree
python experiment.py graphs.json results.json
python supplement.py graphs.json supplement.json
python scaling.py   graphs.json scaling.json
python model.py     scaling.json       # Model 1 — refuted
python model2.py    graphs.json scaling.json   # Model 2 — refuted
python dispersion.py graphs.json       # Poisson diagnosis
```

Requires `numpy`. Seed `20260825` is recorded in `experiment.py`; every figure in
this document is reproducible from the committed `*.json` without re-parsing the
tree. `extract.py` re-derives the graphs from the working tree, so counts will move
if the repository changes — the committed `graphs.json` is the frozen input for the
numbers above.
