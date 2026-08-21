# CrossPlaneTransferV1 preregistration

Status: preregistered experiment; no positive AEGIS result is claimed by this document.

Epistemic tier: T2. The strongest admissible conclusion is **classical causal
representation transfer across AEGIS planes**. A passing result does not establish
consciousness, phenomenal experience, a unified subject, physical quantum coherence,
or a new law of physics.

## Question

Does a representation derived on source plane A improve target-plane B performance
beyond what B can obtain from its own state, the same raw source data, or a mediator
whose task binding has been destroyed?

## Matched arms

Every task appears exactly once in each arm:

1. `B_ONLY` — plane B receives only its local task state.
2. `RAW_SHARED_DATA` — B receives the source record without a derived mediator.
3. `SHUFFLED_Z` — B receives the same multiset of derived mediators as `SHARED_Z`,
   but a derangement breaks every task-to-mediator binding.
4. `SHARED_Z` — B receives the task-bound representation derived by plane A.

The evaluator rejects a `SHARED_Z` mediator whose digest equals the raw source digest.
This mechanical check is necessary but not sufficient; discrimination comes from the
raw and shuffled outcome controls.

## Preregistered hypotheses

For target correctness `Y` and derived representation `Z_A`:

\[
\Delta_{raw}=E[Y\mid do(Z=Z_A)]-E[Y\mid do(Z=raw)]
\]

\[
\Delta_{shuffle}=E[Y\mid do(Z=Z_A)]-E[Y\mid do(Z=shuffle(Z_A))]
\]

The null is retained unless both primary contrasts satisfy all gates below.

## Primary gates

- At least 100 matched tasks per arm. The evaluator and hashed receipt enforce the
  same public floor, so a pilot run cannot be mislabeled as protocol-complete.
- Smallest effect size of interest: `100000 ppm` (10 percentage points) for the
  public canonical run.
- One-sided paired exact sign test: `p <= 50000 ppm` (0.05) against both
  `RAW_SHARED_DATA` and `SHUFFLED_Z`.
- `SHARED_Z` must also beat `B_ONLY` by the registered effect threshold and paired
  exact test.
- All arms must contain the identical trial-ID set.
- `SHUFFLED_Z` must be a complete derangement of exactly the `SHARED_Z` mediator set.
- The full run must replay twice at the same Git HEAD, dataset digest, policy digest,
  model ID, provider label, and provider-attestation state. Receipt hashes must match.

Failure of any gate produces a negative receipt. A local positive receipt with
`provider_attestation=ABSENT` is never promotion-eligible.

## Randomization and scoring

Task order and arm execution order are derived from a seed committed before outcome
inspection and bound into the dataset artifact. Correctness is determined by a fixed,
task-local oracle. No threshold may be tuned after outcomes are visible.

The primary estimator is integer accuracy in parts per million. The paired exact test
uses only discordant matched outcomes and is encoded in integer ppm, avoiding floating
point values in the hashed receipt.

## Privacy-minimal public evidence

Raw prompts, completions, source records, mediator contents, names, email addresses,
IP addresses, and free-form text are not accepted by the public evidence collector.
They remain local to the runner. The publishable record contains only:

- explicit consent version;
- experiment version and receipt hash;
- exact Git HEAD, dataset digest, and policy digest;
- provider/model labels and provider-attestation state;
- per-arm counts and integer accuracies;
- registered effect sizes, exact-test p-values, and pass/fail reasons.

## Execution

```bash
cd sovereign-omega-v2
python python/cross_plane_transfer.py INPUT.json RECEIPT.json
python python/cross_plane_transfer.py INPUT.json REPLAY_RECEIPT.json
cmp RECEIPT.json REPLAY_RECEIPT.json
```

The input contract is `.aegis/cross-plane-transfer-submission-v1.schema.json`.
The executable implementation is `sovereign-omega-v2/python/cross_plane_transfer.py`;
its falsification tests are `python/tests/test_cross_plane_transfer.py`.

## Interpretation table

| Outcome | Admissible interpretation |
|---|---|
| Shared fails to beat raw | No evidence that the derived mediator adds value beyond shared data |
| Shared fails to beat shuffled | No evidence that task-bound mediator content causes the gain |
| Shared beats both, replay fails | Non-deterministic or incompletely bound run; no admitted result |
| Shared beats both, replay matches, attestation absent | Local T2 causal-transfer evidence; not promotion-eligible |
| Shared beats both, replay matches, provider signed | Promotion candidate, still limited to classical causal transfer |
