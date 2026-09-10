# MHP-1 Derivation Composition V1

Status: DRAFT / RED-first / evidence-only.

This slice addresses one deliberately narrow transitive-composition case: a final
claim in `A13` introduced by the right predecessor may be admitted into the
mechanically constructed composed lineage only when every source of the right
`DerivationProofReceiptV1` is authenticated in `C2` and has an authenticated
preservation path from `C1` through `P1`.

The caller does not author `A13`, the composed envelope, or a composed derivation.
`A13` remains mechanically derived as `C3 \\ ran(P13*)`.

A trusted `DerivationCompositionProofReceiptV1` must bind:

- the exact right predecessor derivation proof root;
- every chosen `C1 -> C2` preservation proof root;
- source and midpoint claim digests and semantic fingerprints;
- the final derived claim digest and semantic fingerprint;
- both predecessor envelope roots;
- both predecessor transform roots;
- the mechanically computed composed transform root;
- composition verifier and policy roots;
- wire authority `NONE`.

V1 does **not** recursively compose derivations through claims introduced as
intermediate additions. Such ancestry remains fail-closed. Mixed original-source
and intermediate-addition ancestry remains prohibited by the existing TC-05
`COMPOSITION_MIXED_ANCESTRY` boundary.

No proof object in this slice grants execution, admission, canonical control
state, or mathematical theorem authority.
