# PR #698 scope-clean restricted-Weil v13 lane

- **authority_effect:** NONE
- **RH_PROVEN:** false
- **active canonical PR:** #698
- **active branch:** `proof/rh-restricted-weil-v13-scope-clean-20260928`
- **verified proof-payload head:** `b6ec25c76f0c92b1fd52371b46311e3762866ec7`
- **historical source PR:** #679
- **historical source exact head:** `2676c3bf40b0a196e3dc0ec52180c25c35ab9e7f`
- **clean base main:** `495bfd85d79abcb2b4f6898fe9c156488492426a`
- **root producer:** `WeilRHImpliesFinalSignV13.lean`
- **AEGIS local import closure:** 91 Lean source files
- **external proof source:** `nicholasbulka/li-criterion-rh-equivalence-lean@35df682f3b709ffe5fbcfdd452dfa964bd622b87`
- **Lean:** `leanprover/lean4:v4.33.1`
- **Mathlib:** `0df444a360eaa60ab8c11dca51a86af692955474`

PR #698 is the active scope-clean successor lane. It is a content-addressed extraction from historical PR #679, not a rebase or history rewrite. Every Lean source in the 91-module closure is reused by exact Git blob SHA from `2676c3bf40b0a196e3dc0ec52180c25c35ab9e7f`. No `sovereign-omega-v2` runtime, schemas, harness, product code, research certificates, or unrelated workflows are carried over.

The headline theorem surface is:

```text
final_sign_implies_rh_v13
rh_implies_final_sign_residual_v13
rh_iff_universal_v13
millennium_moment_iff_rh_v13
restricted_weil_criterion_kernel_bridge_v13
```

These are criterion/equivalence results. They do **not** prove RH.

## Independent exact-head replay

The proof payload at `b6ec25c76f0c92b1fd52371b46311e3762866ec7` was independently replayed by `tarikskalic33/formal-conjectures` PR #49 at verifier head `0583a8e8ff8a84aeee2c69b8b2f0f6b28121cd4a`.

- workflow run: `36477556808`
- job: `109114957858` (`exact-head`) — **SUCCESS**
- manifest/source-blob binding: 91/91
- compiled local closure: 91/91
- headline `#print axioms`: `[propext, Classical.choice, Quot.sound]`
- `sorryAx`: absent from the compiled-module outputs and headline audit
- extraction-manifest SHA-256: `1d872022b07694e9658f69d0538eb1aff7214d50ed16c6f59e2fe6c270fc147d`
- axiom-log SHA-256: `d13e70d729feed04ad732203e23c6cf7da7dd770a9055f0d1d19f97fce9a3fb2`
- emitted replay-receipt SHA-256: `0214cad96364c5eff46d9a895ebcc5d27be39b387012cfa2a9cdfe3fbaa76ab0`
- artifact: `10994711868`
- artifact SHA-256: `de35bf5a7adae0b9d56ea73f2f315ce4f58f8b034185edf1cffa3bc06ec31367`

Machine-readable provenance is split deliberately:

- `sovereign-omega-v2/formal/receipts/rh-pr679-scope-clean-v1.json` is the immutable extraction manifest and retains PR #679 as historical source provenance.
- `sovereign-omega-v2/formal/receipts/rh-pr698-independent-replay-v1.json` is the canonical independent replay binding for active PR #698.

Evidence/status commits after `b6ec25c76f0c92b1fd52371b46311e3762866ec7` are metadata-only. They do not change the 91 Lean proof-source blobs or extend the theorem semantics.
