# QUANTUMMANIFOLD_SCHEDULER_PHASE1_DELTA_V1

Status: **NORMATIVE_DELTA / IMPLEMENTATION_OPEN**  
Parent spec: `docs/superpowers/specs/QUANTUMMANIFOLD_SCHEDULER_SPEC_V1.md`  
Architecture: **AEGIS Thread-as-QuantumManifold Core v0.1**  
Repository: `Aegis-Omega/AEGIS-OMEGA`  
Original design base: `6eb2ac201bbe60ebaa9cebad714b8696683772e8`  
Pre-restack scheduler head: `8764d401379fd66f3295b0a51c51807eb0613481`  
MHP derivation substrate head: `b40163d19a1967db9ecafe8bd172556c21e8ef75`  
Audited two-parent restack commit: `8b675a2535f499557e2accc84b5c1e1d7db19108`  
AEGIS Master Notebook v0.4 baseline digest: `457f4566cb932d3f91e2265632fad9931c709645e520471095c23000a85c6404`

This delta narrows the first executable QuantumManifold slice. It does not replace the parent V1 spec. Where this document is more specific for Phase 1/2, this document is normative for that slice.

## 1. Audited ancestry and merge boundary

The executable scheduler branch is a two-parent descendant of:

1. `8764d401379fd66f3295b0a51c51807eb0613481` — the existing QuantumManifold design lineage rooted in current `main`;
2. `b40163d19a1967db9ecafe8bd172556c21e8ef75` — the exact-head GREEN MHP derivation-composition lineage.

The merge-base of the two pre-restack lineages is `1e4a75786304af8f09e034ba1a2b86dd2a534401`.

From that merge-base, the only path modified on both sides is `.claude.json`. The restack therefore uses this deterministic rule:

```text
all non-overlapping paths = union of both parent trees
.claude.json              = first-parent scheduler/main blob, byte-for-byte
manual cognitive merge    = FORBIDDEN
```

The retained `.claude.json` blob at the restack boundary is `9d1f6d7927c0f7f98bbb52b94b5fba262185cd2d` and carries `source_ref = "main"`.

This is deliberately not claimed to be the current branch cognitive anchor. Authorized cognitive refresh is a separate transition controlled by `.github/workflows/cognitive-manifest-refresh.yml`.

At the audited boundary, the latest required `Main branch enforcement` publisher check on `main@6eb2ac201bbe60ebaa9cebad714b8696683772e8` is not GREEN, so cognitive refresh must remain fail-closed:

```text
COGNITIVE_ANCHOR_REFRESH = BLOCKED_PENDING_MAIN_ENFORCEMENT_GREEN
TRUSTED_COGNITIVE_ADMISSION = EXPECTED_DENY_UNTIL_AUTHORIZED_REFRESH
```

No Phase-1 scheduler commit may manually rewrite `.claude.json` or `skill-hashes.sha256` to bypass that boundary.

## 2. MHP substrate is inherited code, not transported authority

The restacked branch inherits these exact MHP runtime surfaces:

```text
harness/sdk/meaning_heritage.py
harness/sdk/morphisms.py
harness/sdk/heritage_composition_base.py
harness/sdk/heritage_composition.py
```

The common hashing dependency `harness/sdk/sovereign_execution.py` is byte-identical across the two pre-restack lineages at the audit boundary. MHP roots therefore retain the same repo-native `canonical_hash(domain, value)` semantics through the restack.

The scheduler is a read-only consumer of already defined verified-store ports. It must not introduce a parallel semantic-lineage or proof-store system.

Required existing ports include:

```python
TrustedClaimSetReceiptStore.fetch_verified(receipt_root)
TrustedSemanticProofStore.fetch_preservation(proof_root)
TrustedSemanticProofStore.fetch_derivation(proof_root)
TrustedDerivationCompositionProofStore.fetch_derivation_verified(receipt_root)
TrustedDerivationCompositionProofStore.fetch_derivation_verified_for(receipt_root, ...)
```

`TrustedHeritageCompositionProofStore` remains the existing combined composition trust surface.

A scheduler read from these ports can establish structural/provenance inputs for ranking. It cannot increase the authority class of the underlying MHP receipt. MHP wire authority remains `NONE` / `NONE_BY_CONSTRUCTION`.

## 3. Dedicated integration lane is mandatory

The inherited MHP workflows are branch-scoped to their original proofline branches and do not automatically re-run merely because their code becomes an ancestor of the QuantumManifold branch.

Therefore Phase 1 must add a dedicated exact-head QuantumManifold integration workflow. It must:

1. checkout the exact candidate SHA;
2. assert `git rev-parse HEAD == CANDIDATE_SHA`;
3. assert both audited substrate ancestors are ancestors of the candidate:
   - `8764d401379fd66f3295b0a51c51807eb0613481`;
   - `b40163d19a1967db9ecafe8bd172556c21e8ef75`;
4. compile the QuantumManifold modules and inherited MHP modules;
5. run the focused QuantumManifold RED/GREEN suite;
6. run inherited MHP regression suites directly on the same candidate head;
7. emit a content-addressed receipt even when the focused suite is RED;
8. upload the evidence bundle;
9. preserve the actual RED/GREEN job conclusion.

Historical MHP workflow receipts remain evidence for their original exact heads. They are not silently reclassified as integrated current-head receipts.

## 4. Repository-native scheduler policy location

Phase 1 must not create a new top-level `configs/` policy namespace. Existing governance policy lives under `harness/policies/`.

The scheduler policy path is therefore:

```text
harness/policies/quantummanifold-scheduler.v1.json
```

The policy is content-addressed and must include at least:

```json
{
  "schema_version": "1.0.0",
  "policy_kind": "AEGIS_QUANTUMMANIFOLD_SCHEDULER_POLICY_V1",
  "authority_effect": "NONE",
  "ppm": 1000000,
  "max_safe_canonical_int": 9007199254740991,
  "alpha_ppm": 1000000,
  "beta_ppm": 1000000,
  "gamma_ppm": 1000000,
  "mu_ppm": 1000000,
  "eta_ppm": 1000000,
  "epsilon_ppm": 1
}
```

These initial coefficients are deterministic neutral defaults for the bounded implementation contract, not empirically calibrated scientific priors.

## 5. Digest identity is not arithmetic

SHA-256 digests are content identities and bindings. They are never converted into numeric utility, probability, centrality, information gain, cost, or authority values.

Canonical scheduler arithmetic operates only on non-negative exact integers in the fixed-point domain specified by the parent V1 spec.

Digests may participate only in:

- identity validation;
- content-addressed lookups;
- snapshot/candidate/policy binding;
- deterministic lexicographic tie-breaking where explicitly specified.

Invariant:

```text
DIGEST_AS_NUMERIC_SCORE = FORBIDDEN
FLOATING_POINT_CANONICAL_METRIC = FORBIDDEN
```

## 6. Phase-1 typed kernel surface

The first production module surface is intentionally small:

```python
RealityThreadV1
OpenObligationV1
CandidateActionV1
ClosurePriorV1
DispatchProposalV1
QuantumManifoldSchedulerV1
TrustedClosurePriorStore
```

Every serialized digest is lowercase hexadecimal of the declared length. Every scheduler receipt carries:

```text
authority_effect = NONE
can_admit_claim = false
can_advance_authority = false
```

The scheduler emits a recommendation only. It has no execution, canonical-control, claim-admission, repository-merge, theorem, or empirical-truth authority.

## 7. Centrality anti-Sybil rule

The parent spec's downstream-priority-mass centrality is refined for Phase 1 to prevent graph-sharding inflation.

A downstream contribution is counted at most once per **verified lineage class**. A lineage class is content-addressed from verified MHP identities, not from graph labels or semantic similarity.

For Phase 1, the canonical lineage-class preimage is the ordered tuple:

```text
claim_digest
semantic_fingerprint
verified_heritage_or_derivation_root
```

and the class identifier is:

```text
canonical_hash("qm-lineage-class-v1", canonical_tuple)
```

Rules:

1. aliases or child nodes with the same verified lineage class do not multiply downstream priority mass;
2. a node without a verified lineage root contributes zero positive centrality mass;
3. two nodes are never deduplicated merely because their prose or semantic embedding is similar;
4. an identifier collision with non-identical canonical content fails closed.

Phase-1 falsifier:

```text
QM-RED-025 / QM-RED-FALSIFIER-01 = CENTRALITY_SYBIL_INFLATION
```

A 100-child split of one lineage class must not increase canonical centrality relative to the unsplit graph.

## 8. Closure-prior provenance and generator/verifier separation

A candidate action may not self-declare trusted `p_close_ppm`.

Closure leverage may consume only a verified `ClosurePriorV1` resolved through a separate read-only store port:

```python
class TrustedClosurePriorStore(Protocol):
    def fetch_verified(self, prior_root: str) -> ClosurePriorV1: ...
```

Normative `ClosurePriorV1` fields:

```text
prior_root
obligation_digest
candidate_action_digest
p_close_ppm
estimator_kind
estimator_root
policy_digest
source_head_sha
verification_receipt_root
```

`prior_root` is computed over canonical content excluding the root field itself.

The proposal generator may carry only the `closure_prior_root`. It may not provide a trusted inline probability.

The scheduler verifies that the fetched prior binds the exact:

- obligation digest;
- candidate action digest;
- scheduler policy digest;
- source head SHA.

Missing, untrusted, stale, or splice-mismatched prior data fails closed with:

```text
UNVERIFIED_CLOSURE_PRIOR
```

Phase-1 falsifier:

```text
QM-RED-026 / QM-RED-FALSIFIER-02 = UNVERIFIED_CLOSURE_PRIOR
```

No new durable database is introduced. `TrustedClosurePriorStore` is a port only.

## 9. Stale exact-head semantics

Phase 1 reuses the parent V1 stale-result boundary rather than creating a second stale mechanism.

A candidate or returned result bound to a source head that no longer matches its current evaluation coordinate is not automatically invalidated as historical evidence, but is blocked from active dispatch/reprojection:

```text
STALE_RESULT_REQUIRES_REBASE
```

The #356 ancestry-divergence episode is a real-world conformance example, not a hard-coded special case.

Phase-1 falsifier mapping:

```text
QM-RED-FALSIFIER-03 -> existing QM-RED-018
```

The production scheduler must accept externally established current-head/ancestry facts as explicit inputs; it must not perform hidden network I/O.

## 10. Authority-tunneling semantics at the actual Automaton-3 boundary

The Phase-1 authority falsifier is defined against the real authority-client contract.

A scheduler receipt cannot substitute for:

- `AEGIS_EXECUTION_IDENTITY_JSON`;
- the exact action digest bound into that execution identity;
- required approval/policy inputs;
- an Automaton-3 evaluation.

A scheduling proposal presented alone to the execution boundary must receive no positive authority.

If a later action legitimately references a scheduler proposal and Automaton-3 independently validates a matching execution identity and policy, any `ADMIT` originates from Automaton-3. The scheduler still has `authority_effect = NONE`.

Therefore the invariant is not "Automaton-3 may never see a scheduler receipt". The invariant is:

```text
SCHEDULER_RECEIPT_ALONE_CANNOT_SATISFY_POSITIVE_AUTHORITY
SCHEDULER_RECEIPT_CANNOT_REPLACE_EXECUTION_IDENTITY
SCHEDULER_RECEIPT_CANNOT_REPLACE_APPROVAL_OR_POLICY
```

Phase-1 falsifier mapping:

```text
QM-RED-FALSIFIER-04 -> existing QM-RED-015 plus execution-boundary regression
```

Failure classification for an attempted direct promotion remains:

```text
AUTHORITY_TUNNELING_ATTEMPT
```

## 11. Focused Phase-1 RED contract

Before production ranking logic exists, the exact-head RED lane must observe these four failures/violations:

| Focused ID | Master ID | Required invariant |
|---|---|---|
| `QM-RED-FALSIFIER-01` | `QM-RED-025` | 100 graph aliases/children of one verified lineage class cannot inflate centrality |
| `QM-RED-FALSIFIER-02` | `QM-RED-026` | generator-supplied or unverified closure probability cannot contribute closure leverage |
| `QM-RED-FALSIFIER-03` | `QM-RED-018` | stale coordinate returns `STALE_RESULT_REQUIRES_REBASE` |
| `QM-RED-FALSIFIER-04` | `QM-RED-015` | scheduler proposal alone cannot create positive Automaton-3/admission authority |

The focused four do not replace the parent spec's full 24-case matrix. They are the first executable slice; `QM-RED-025` and `QM-RED-026` extend that matrix to 26 cases.

## 12. RED receipt requirements

The dedicated workflow must still emit a receipt artifact when the focused contract is RED.

Minimum receipt fields:

```text
receipt_kind = AEGIS_QUANTUMMANIFOLD_PHASE1_ATTESTATION_V1
source_commit
scheduler_design_parent = 8764d401379fd66f3295b0a51c51807eb0613481
mhp_substrate_parent = b40163d19a1967db9ecafe8bd172556c21e8ef75
parent_ancestry_asserted
policy_sha256
qm_contract_sha256
mhp_kernel_sha256 map
pytest_log_sha256
tests_passed
tests_failed
status = RED_FAILURE_OBSERVED | GREEN_PASS
authority_class = NONE
ledger_authority_classification = NONE_BY_CONSTRUCTION
```

`receipt_sha256` is computed over canonical receipt content before the self-hash field is inserted.

The workflow uploads the receipt and pytest log before preserving the pytest exit code.

## 13. GREEN acceptance criteria

Phase 1 is GREEN only at one exact candidate head where all of the following are simultaneously true:

1. both audited restack parents remain ancestors;
2. focused four scheduler falsifiers pass;
3. inherited MHP regression suites pass on that same head;
4. scheduler policy digest is bound into the receipt;
5. scheduler implementation and test hashes are bound into the receipt;
6. inherited MHP kernel hashes are bound into the receipt;
7. scheduling proposals remain `authority_effect = NONE`;
8. direct scheduler-to-admission/positive-authority use remains impossible in the bounded tested surface;
9. no floating-point canonical scheduling arithmetic is used;
10. deterministic repeated input produces byte-identical proposal serialization.

A GREEN Phase-1 receipt supports only:

```text
QUANTUMMANIFOLD_PHASE1_RUNTIME = MACHINE_TESTED_AT_EXACT_HEAD
NO_POSITIVE_SCHEDULER_AUTHORITY_PATH = MACHINE_TESTED_IN_BOUNDED_SURFACE
```

It does not establish zero global risk, production persistence, repository-wide merge enforcement, Trusted Cognitive Admission, physical quantum semantics, scientific truth, or canonical claim admission.

## 14. Explicit external blockers

The following remain separate from the Phase-1 scheduler implementation:

```text
MAIN BRANCH PROTECTION           = FALSE
MAIN REQUIRED STATUS CHECKS      = OFF
LIVE AEGIS RULESET ENFORCEMENT   = NOT_ACTIVE
REPOSITORY MERGE ENFORCEMENT     = NOT_ACTIVE
GLOBAL FAIL-CLOSED ADMISSION     = NOT_ESTABLISHED
COGNITIVE ANCHOR REFRESH         = BLOCKED_PENDING_MAIN_ENFORCEMENT_GREEN
TRUSTED COGNITIVE ADMISSION      = NOT A PHASE-1 GREEN PRECONDITION
```

A Phase-1 GREEN receipt must report these boundaries rather than over-promote around them.
