# Holon × Meaning Heritage Bridge V1

**Status:** candidate; evidence-only; no authority, deployment, or semantic-truth claim.  
**Canonical references:** `docs/ONTOLOGY.md`, `docs/CORPUS_MINDMAP.md`, `sovereign-omega-v2/src/core/types.ts` (`HolonMetadata`), `harness/sdk/meaning_heritage.py` (MHP-1 v1.3), `harness/sdk/heritage_composition.py`.  
**Research ancestor:** AEGIS Ω Meaning Heritage Protocol MHP-1 / ULC-1, 2026-08-21; source Drive document `1BsjFB_9_nmTp3_VzscrSuUO-yFGWVOFp`.

## Problem

A token or number is not a context-free meaning. The same bytes can originate in distinct artifacts, at distinct offsets, and be interpreted under different explicitly admitted contexts. `HolonMetadata` captures parent/child structure, tier, ontology name and research-document references; MHP-1 captures the semantics of verified derived claims, losses, additions and transitive ancestry. Neither type on its own connects **source occurrence** to **multiple competing verified-lineage readings**.

## Source-bound vertical slice

- `HolonSnapshotV1.from_typescript_record` parses exactly the nine `HolonMetadata` fields (lowercase scale values). Undeclared extra fields, self-edges, parent-child overlap and missing T0–T2 research references fail. `provenance` is **a declaration**; presence does not independently authenticate documents or the epistemic tier.
- `SourceOccurrenceV1` binds the exact byte span of an independently trusted original artifact to the SHA-256 root of the selected carrier bytes. The same carrier may have multiple distinct occurrence roots.
- `ContextualReadingV1` binds each candidate to context bytes, an existing MHP `SemanticLineageEnvelopeV1`, and an existing independently trusted `HeritageReceiptV1`. Multiple candidate readings of one occurrence are retained, including multiple readings in one context.
- `ContextBindingReceiptV1` must resolve from an **additional independent trusted store**. It binds the holon metadata root, source occurrence, reading ID, context root, MHP envelope, exact transform root, and derived payload. Without it, swapping a plausible context or holon still fails closed.
- `HolonMeaningVerifierV1` obtains original/context/derived bytes, source/derived ClaimSet, envelope and heritage receipts, plus trusted context-binding receipts **from trusted external stores**. It verifies content hashes, source span, envelope/receipt pairings, and exact MHP source/derived references. It issues `authority_class=NONE` evidence only; no effect or canonical admission.
- Roots use the repository's `canonical_hash` domain separation. Reading order is canonicalized by reading ID; no interpretation is picked as inherently correct.

## Distinctions that must not be collapsed

| Distinction | Rule |
| --- | --- |
| Glyph / occurrence | Byte-equal signs can come from different origin artifacts or spans; distinct occurrence roots |
| Occurrence / meaning | A carrier root does not pick one reading; all readings require context and proof-lineage refs |
| Holon tier / truth | `T0` / `T1` / `T2` and Drive IDs are metadata claims, not proof of correctness |
| MHP receipt / validity of interpreted proposition | A trusted receipt certifies authenticated transformation and declared loss, not empirical truth |
| Hash / actual trust | A correct 64-hex root without a trusted-store readback is insufficient |
| Local holon edges / global holarchy | Local self-edge checks do not prove graph closure or acyclicity of an external registry |
| Canonical ontology / context-dependent readings | Canonical terms remain unique; readings remain separate contextual hypotheses |

## Acceptance and falsifiers

The exact-head workflow runs the new native Python integration tests and three existing MHP suites. It checks two interpretations of `A` with distinct context and derived payloads; identical `A` in two original artifacts; reading-order canonicalization; missing/mismatched source span, artifact, context, context-binding attestation, holon metadata, envelope, receipt, claimset and derived bytes; self-edges, invalid spans, duplicate reading IDs, schema extension, and unbacked high-tier labels. Test-provided stores are deliberately finite fixtures, **not a claim of deployed trust infrastructure**.

## Whole-graph verifier V1: bounded closed-world holarchy

Added the strictly read-only \`harness/sdk/holon_graph_verifier.py\` with native falsifiers in \`harness/tests/test_holon_graph_verifier.py\`. It consumes the existing \`HolonSnapshotV1\`, \`HolonMeaningLensV1\`, and verified \`HolonMeaningReceiptV1\` from this bridge. It does **not** invent an alternative meaning/proof engine or modify \`HolonMetadata\` or the merged MHP kernels.

- **Bounded inventory:** \`HolonGraphManifestV1\` is a content-addressed enumeration of claimed nodes and their claimed meaning receipts. The verifier retrieves the manifest independently from a trusted store and retrieves every declared node by its exact \`HolonSnapshotV1.root\`. At most 4096 nodes, 32768 declared parent edges, 16384 meaning receipts and 16384 research document references are permitted. It checks only **closure relative to this supplied manifest**, not whether every holon in every AEGIS repository or Drive exists in that manifest.
- **Bidirectional topology:** each declared \`part_of\` must point to a listed parent with the reciprocal \`composed_of\`; each \`composed_of\` must point to a listed child with the reciprocal \`part_of\`. Missing targets or asymmetry fail closed. Multiple parents are explicitly permitted; the holarchy is a DAG, not necessarily a tree.
- **Acyclicity / scale direction:** deterministic, iterative Kahn traversal rejects cycles without recursive-stack exhaustion. A parent must not be at a *lower* HolonicScale than its child. Equal-scale parent/child relations are currently permitted; whether they should be forbidden requires a separate ontology-level policy.
- **Research provenance:** every referenced research-document identifier must resolve through a separate trusted source-attestation store to an exact nonempty byte artifact; digest mismatches fail closed. Each T0/T1/T2 holon requires at least one attested T0/T1/T2 research source. **Trust-store integrity, actual independent review and document semantics are environmental assumptions**, not inferred from a review hash or a string in \`provenance\`.
- **Contextual meaning:** for every **declared** meaning receipt, the verifier fetches an authenticated \`HolonMeaningLensV1\`, re-runs \`HolonMeaningVerifierV1\` against its MHP-1 and context-binding stores, and checks that the new receipt is byte-for-byte the trusted prior receipt. A holon edit cannot inherit a receipt tied to an older holon root.
- **No semantic collapse:** all context-dependent readings remain separate. The metric \`competing_reading_count\` counts additional alternative reading candidates, **not logical contradictions, proven non-equivalence or mutually exclusive propositions**. Incompatibility requires independently verified semantic premises and an explicit proof of incompatibility under a stated shared scope, which is **not established** by V1.
- **Epistemic/authority boundary:** \`PASS_STRUCTURAL_ONLY\` and \`authority_class=NONE\` certify an authenticated, internally coherent *declared* graph only. Neither mathematical validity, cultural intent, author identity, formal semantic soundness, deployed provenance infrastructure, full corpus completeness nor execution authority follows from a passing graph receipt.

The dedicated exact-head workflow includes the new graph falsifiers and the inherited MHP suites. The first graph-enabled commit \`5a157b2afee01d6a086661d25aef24d6dbcba65a\` passed **77/77 tests** in [Holon Meaning Bridge V1 run 43846595295](https://github.com/Aegis-Omega/AEGIS-OMEGA/actions/runs/43846595295). This receipt binds only to that exact commit; subsequent commits must obtain fresh CI evidence.

## Open work

1. A real authenticated document/byte store for research provenance and context references, with access controls and revocation.
2. Extend **declared-graph verification** to corpus-wide completeness backed by an authenticated holon registry, independent ontology-term membership and review-policy verification, and cross-runtime TypeScript/Python canonical parity.
3. Independently checked proof witnesses for genuinely incompatible readings within the same declared scope; human/independent validation of competing interpretations, cultural origin and speaker intent. Counting alternatives does not prove contradiction or truth.
4. Separate constitutional admission for any use in decisions or execution. No merge, deployment, authority elevation or changes to existing MHP/constitutional kernels are part of this draft.
