# SOVEREIGN OMEGA — Formal Verification Programme
## EPISTEMIC TIER: T3 (ChatGPT Document 6)

Unified semantic object:
  SYSTEM := (S, E, step, hash, canon, mem, pin)

3-Way Bisimulation:
  ⟦s₀⟧JS ─σ→ ⟦s₁⟧JS, ⟦s₀⟧WASM ─σ→ ⟦s₁⟧WASM, ⟦s₀⟧PY ─σ→ ⟦s₁⟧PY
  ⇒ encode(⟦s₁⟧JS) = encode(⟦s₁⟧WASM) = encode(⟦s₁⟧PY)

Reality boundary: full ECMAScript/WASM/Python semantics require
JSCert + WasmCert + CompCert-scale effort (multi-year programme).
These stubs provide mechanically consistent scaffolding.

## Coq build binding

The global Coq attestation lane consumes `coq-targets.json` as a committed input.
Its 30 source hashes bind the full source bytes, including statements, proofs and
local definitions. Its 213 explicit names are declaration-presence targets.
This is not a complete inventory of compiler-generated constructors, projections
or declarations introduced through arbitrary Coq extensions. Target changes must
be reviewed with the corresponding source changes; CI never regenerates targets.
The manifest records no independent human-review or mathematical-validity claim.

`python/coq_build_binding.py freeze` runs before compilation, rejects existing
compiled artifacts, and records resolved `coqc`/`coqtop` executable hashes,
reported versions and hashes of compiled libraries/plugins found under
`coqc -where`. Compilation explicitly disables asynchronous proofs and startup
files. The subsequent `check` command requires `.vo` and `.glob` artifacts and
successful fully qualified `Check` queries for every explicit target. It retains
queries, logs and artifact digests, and rejects source, target, artifact or
verifier drift. Existing theorem `.glob` discovery and assumption-baseline checks
remain required. Query and discovery failures propagate to the workflow.

The receipt generator's `--build-binding` joins this evidence to the source
commit and source hashes, producing schema 1.2.0. The global workflow requires
this input and recomputes the final receipt digest. Legacy callers without it
retain schema 1.1.0 with `build_binding_status = NOT_BOUND`; old receipts are not
retroactively upgraded.

This is **same-job build evidence**, not authenticated external verification.
Content hashes do not authenticate a hostile producer. Native runtime/OS
dependencies and external load paths are not fully attested. Assumption traversal
semantics are recorded as `VERSION_BOUND_NOT_REGRESSION_CHARACTERIZED`:
Rocq [#21437](https://github.com/rocq-prover/rocq/pull/21437) adds traversal of
axiom types, while [#21825](https://github.com/rocq-prover/rocq/pull/21825) adds
definition types. Neither feature is inferred for historical Coq 8.20.1 evidence.
Declaration checking addresses the reported build-integrity failure in
[#22422](https://github.com/rocq-prover/rocq/issues/22422); the Python fault tests
simulate omitted declarations and do not reproduce that Rocq bug.

Unit verification:

```sh
PYTHONPATH=python python -m unittest python.tests.test_coq_attestation python.tests.test_coq_attestation_regressions python.tests.test_coq_attestation_diagnostics python.tests.test_coq_assumption_output_integrity python.tests.test_coq_build_binding
python scripts/coq_inventory.py --check
```

The build-binding fixtures use synthetic compiler artifacts. A real hosted Coq
run is required to validate the integrated lane. `kernel_replay = NOT_PERFORMED`,
`production = NOT_ADMITTED` and mathematical correspondence remains
`NOT_ESTABLISHED`; these checks do not establish the Riemann hypothesis.

### Codex H: meaning preserved by assumption projection

The baseline comparison projects captured assumptions onto symbol names and
admitted counts. It now reports `comparison_scope = SYMBOL_NAMES_AND_ADMITTED_COUNTS`
and `statement_equivalence = NOT_EVALUATED`. For example, `H : True` and
`H : False` have identical symbol projections, although the retained raw log
hashes differ. A zero regression count therefore does not establish equality of
assumption types or theorem statements. Source/build binding is a separate check;
no new semantic proof checker is introduced here. Existing comparison decisions
are unchanged. The regression witness is in `python/tests/test_coq_projection_scope.py`.

### Local validation checkpoint (2026-09-06)

The working patch based on `c49529d42e170d91a323978e1e0fdc8bb6da8724`
was exercised with Coq 8.20.1 and CoRN 9.0.0: 30 sources compiled,
213 manifest declarations passed explicit queries, and a separate `coqchk`
invocation checked all 30 modules and their dependencies. Captured
`Print Assumptions` outputs covered 116 theorems: 113 closed and three
assumption-bearing, with zero admitted sources and zero baseline regressions.
The content-addressed attestation digest was
`12d94747991f8c949e8c55a5c1189ac4fe10ccf2dcb2d9e27b3c6b3a5ad6866c`.

This is a historical local checkpoint, not a hosted CI result for this commit.
Coquelicot 3.4.2 was built from its original sources using `coq_makefile`
and `make` because its `remake` server could not start in the local environment;
it was manually installed and was not registered as installed by opam.
The sealed declaration-binding record retains `kernel_replay = NOT_PERFORMED`;
the later checker result is recorded separately in `coqchk-status.json` in
`AEGIS_Coq_820_Full_Local_Validation.zip`. Both checks ran on the same host.
No external independence, production admission, or RH closure follows.
