# AEGIS Polyglot Frontier Watchlist — spike lane

Each line in the watchlist is a **RED→GREEN spike**: a named defect of standard
agent computation, a procedure that provably fails on it, and a procedure in a
language where the missing primitive is native.

A line is only claimed here once it runs. What follows is the measured state of
this machine, not a plan.

## EGRAPH-0 — equality saturation · **DELIVERED**

`egg 0.9.5`, Rust 1.94.1. `cargo test` → 7/7.

| | |
|---|---|
| expression | `(c · Λ(q)) / (c · √q)` — the shared-scale slice of the von Mangoldt amplitude |
| RED | greedy cost-decreasing rewriting takes **0 steps** and halts at tree size 11; no single rule, applied at every site it matches, lowers the cost |
| GREEN | equality saturation extracts `Λ(q)/√q` at tree size **5**, first reached at iteration 5 and held for every budget through 12 |
| falsifier 1 | `nz` is load-bearing: `(* (nz c) (inv (nz c)))` ≡ `1`, but `(* c (inv c))` ≢ `1` |
| falsifier 2 | saturation does not collapse distinct terms: `Λ(q)/√q` ≢ `Λ(q)`, `√q`, `1`, `√q/Λ(q)` |
| recorded limitation | the rule set **does not saturate** — `cancel-nz` puts `1` in an e-class holding a product, so `inv-distributes` keeps generating `inv` towers. Asserted in `the_rule_set_does_not_saturate` so it cannot quietly stop being true. |

Epistemic tier **T1**: measured behaviour of two procedures on one expression,
not a theorem about all expressions.

## The other five lines — blocked, with the blocking evidence

Probed on this machine, 2026-09-02:

| line | toolchain | probe | state |
|---|---|---|---|
| UNISON-0 | `ucm` | `command not found` | **BLOCKED** — no Unison runtime. Reimplementing content-addressing in Python would be the exact anti-pattern the watchlist exists to end, so it is not done here. |
| VERIF-RUN-0 | Verus, Kani | `verus: command not found`; `cargo kani` absent; `api.github.com/repos/verus-lang/verus/releases/latest` → **403** through the agent proxy | **BLOCKED** — Kani is installable from crates.io but `cargo kani setup` fetches CBMC from GitHub releases, which the 403 blocks. Bounded exhaustive testing in plain Rust is *not* SMT deductive proof and would misreport the tier, so it is not substituted. |
| PROB-SELF-0 | Julia + Gen.jl / Turing.jl | `julia: command not found`; julialang-s3 tarball → **200** | **REACHABLE, NOT RUN** — Julia downloads, but Turing's precompilation is a long unattended install. Not started without the operator's word on spending it. |
| NEURO-HOLON-0 | Intel Lava | `pypi.org/simple/lava-nc/` → **200** | **REACHABLE, NOT RUN** — installable; the spike needs a real asynchronous-process design, not a `pip install`. |
| AEGIS-MLIR-0 | MLIR dialect | `llvm-config` → 18.1.3, but `mlir-opt: command not found` | **BLOCKED** — LLVM is present without MLIR; building MLIR from source is hours of compute. |
| (also) SOUFFLE | Soufflé | `apt-get install souffle` → `E: Unable to locate package` | **BLOCKED** — not in this image's apt sources. |

## Elimination filter

Unchanged from the watchlist: a new tool is admitted only if it introduces a new
computational primitive, lowers verification debt, and can be isolated in a
RED→GREEN test. EGRAPH-0 passes all three. The five above are not rejected —
they are unrun, and each row says exactly what stands in the way.
