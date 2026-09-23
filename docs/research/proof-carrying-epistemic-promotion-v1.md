# Proof-Carrying Epistemic Promotion V1

The conservative consensus meet is:

`M = (claim intersection, min authority, max loss uncertainty)`.

Any candidate stronger than `M` creates explicit proof obligations.

## Gain dimensions

### Claim gain

A candidate contains an exact canonical claim not present in the meet.

Required obligation:

`CLAIM_GAIN::<claim-id>`

### Authority gain

A candidate authority exceeds the meet authority.

Required obligation:

`AUTHORITY_GAIN::<baseline>-><candidate>`

### Uncertainty reduction

A candidate loss uncertainty is below the meet uncertainty.

Required obligation:

`UNCERTAINTY_REDUCTION::<baseline>-><candidate>`

## Receipt binding

Every promotion receipt is content-addressed and binds:

- both input state digests;
- candidate state digest;
- exact obligation ID;
- evidence digest;
- verifier root;
- policy root.

Receipts are fetched through a trusted store. Caller-authored PASS objects are
not accepted.

Exact obligation coverage is required; missing, duplicate, spliced, untrusted,
or extra receipts deny the promotion gate.

Even complete coverage yields only:

`ELIGIBLE_FOR_SEPARATE_PROMOTION_ONLY`

The receipt itself does not mutate claims or authority.

## Formal boundary

The Lean child theorem shows that any positive gain in claims, authority, or
uncertainty reduction makes the candidate cease to be a common lower bound of
the two inputs.

Thus the conservative meet is the strongest state obtainable without a separate
promotion transition.

Prior art exists for information fusion, bilattices, and proof-carrying data.
AEGIS application novelty is NOT_ESTABLISHED.

authority_effect = NONE
