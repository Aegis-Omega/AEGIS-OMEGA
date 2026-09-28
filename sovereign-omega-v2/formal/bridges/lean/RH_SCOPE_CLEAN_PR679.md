# PR #679 scope-clean extraction

- **authority_effect:** NONE
- **RH_PROVEN:** false
- **source PR:** #679
- **source exact head:** `2676c3bf40b0a196e3dc0ec52180c25c35ab9e7f`
- **clean base main:** `495bfd85d79abcb2b4f6898fe9c156488492426a`
- **root producer:** `WeilRHImpliesFinalSignV13.lean`
- **AEGIS local import closure:** 91 Lean source files
- **external proof source:** `nicholasbulka/li-criterion-rh-equivalence-lean@35df682f3b709ffe5fbcfdd452dfa964bd622b87`
- **Lean:** `leanprover/lean4:v4.33.1`
- **Mathlib:** `0df444a360eaa60ab8c11dca51a86af692955474`

This branch is a content-addressed extraction from PR #679, not a rebase or history rewrite.
Every Lean source in the closure is reused by exact Git blob SHA from `2676c3bf40b0a196e3dc0ec52180c25c35ab9e7f`.
No `sovereign-omega-v2` runtime, schemas, harness, product code, research certificates, or unrelated workflows are carried over.

The headline theorem surface is:

```text
final_sign_implies_rh_v13
rh_implies_final_sign_residual_v13
rh_iff_universal_v13
millennium_moment_iff_rh_v13
restricted_weil_criterion_kernel_bridge_v13
```

These are criterion/equivalence results. They do **not** prove RH. The CI lane compiles the exact local closure against the pinned external provider and Mathlib, then emits `#print axioms` output for the headline declarations and rejects `sorryAx`.

Machine-readable provenance is in `sovereign-omega-v2/formal/receipts/rh-pr679-scope-clean-v1.json`.
