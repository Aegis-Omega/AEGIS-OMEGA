# Verified Semantic Quotient Consensus V1

Exact claim identity is safe but intentionally conservative.

This lane permits two different exact claim digests to participate in the same
consensus class only when AEGIS already carries a trusted MHP
`SEMANTIC_EQUIVALENCE` preservation receipt from the claim to a canonical
representative.

`PARAPHRASE_ABSTRACTION` is deliberately insufficient.

## Runtime rule

For each source claim digest:

- exact self-identity may project to itself with the same semantic fingerprint;
- any different canonical representative requires a trusted
  `PreservationProofReceiptV1` with relation `SEMANTIC_EQUIVALENCE`;
- receipt claim/fingerprint bindings must exactly match;
- every input claim must be covered by exactly one projection membership.

The projection receipt is content-addressed and authority-neutral.

Consensus then operates on verified semantic class IDs:

- class intersection;
- minimum authority;
- maximum loss uncertainty.

An unproved similarity can cause two truly-equivalent claims to remain separate
(false negative). It may not create a false semantic merge.

## Formal target

For a generic projection `q` and semantic relation `SemEq`, assume:

`q(a) = q(b) -> SemEq(a,b)`.

Then every class retained in the quotient consensus has:
- a representative in the left input;
- a representative in the right input;
- a pair of representatives related by `SemEq`.

This is the exact soundness boundary needed before lifting exact-claim consensus
to quotient classes.

The mathematics of quotient/image intersections is standard. Novelty is not
claimed. The AEGIS application of MHP-bound projection receipts is
`NOT_ESTABLISHED` as novel.

authority_effect = NONE.
