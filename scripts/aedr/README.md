# AEDR Multilayer DAG + Live Acquisition V1

AEDR models repository consolidation as five orthogonal relations over one freshly resolved exact-head observation:

- `E_git` — commit ancestry only;
- `E_sem` — semantic prerequisite/dependency only;
- `E_auth` — authority-domain overlap only;
- `E_evidence` — exact-head receipt/falsification bindings only;
- `E_conflict` — detected incompatible/divergent relations only.

No edge implies another edge. Mergeability is not proof, semantic dependency is not git ancestry, a workflow success is not a falsification surface, and evidence from a stale SHA cannot authorize a current-head claim.

## Live acquisition pipeline

V1 now provides the read-only acquisition path:

```text
GitHub REST
    |
    v
GitHubLiveOracle
    |  ETag / If-None-Match
    |  canonical pagination
    |  rate-limit observation
    |  exact-head workflow filtering
    v
DeterministicSnapshotBuilder
    |  optimistic double collect
    |  canonical JSON
    |  Merkle/content digest
    |  deep-freeze after digest
    v
MultilayerDAGSnapshot
    |
    v
acquisition_adapter
    |
    v
MultilayerDAGEvaluator
```

The acquisition layer is `READ_ONLY` and `authority_class = NONE`. It has no mutation, merge, close, rebase, push, deployment, admission, security-dismissal, or authority-granting surface.

## Consistency model

GitHub REST does not provide a transaction spanning main, the pull-request collection, workflow runs, and compare endpoints. AEDR therefore does **not** claim serializable API snapshot isolation.

V1 uses `OPTIMISTIC_DOUBLE_COLLECT`:

1. read the initial main SHA;
2. collect the complete initial open-PR observation;
3. acquire exact-head workflow and required ancestry records;
4. recollect the complete open-PR observation;
5. reread main;
6. reject the snapshot if either observed state changed.

Any detected main shift, PR-head movement, open-PR set movement, or other change in the canonicalized PR observation raises `CONCURRENT_MUTATION_DETECTED`. The result is fail-closed: no snapshot is emitted from a detected mixed observation.

## Deterministic content addressing

All digest-bearing payloads use canonical JSON with sorted keys, compact separators, ASCII encoding, and `allow_nan = false`. PRs, labels, workflow records, semantic dependencies, file paths, and ancestry records are deterministically sorted before hashing.

`snapshot_digest` is SHA-256 over a domain-separated canonical snapshot payload. The snapshot also contains a domain-separated Merkle root over node and ancestry leaves.

`captured_at_utc` is observational metadata and is intentionally excluded from `snapshot_digest`, so two independent acquisitions of identical observed repository/API state produce the same content digest.

After the digest is calculated, node and ancestry payloads are recursively frozen. Post-digest mutation of nested dictionaries or lists raises `TypeError`; a caller cannot mutate the payload while retaining the old digest.

Hash/Merkle integrity is not signer authenticity. V1 snapshots and advisory receipts remain unsigned unless a separate identity-bound signing layer is introduced.

## Conditional reads, pagination, and rate-limit state

`GitHubLiveOracle` uses ETag caching and sends `If-None-Match` on repeated reads. HTTP `304 Not Modified` reuses the previously parsed payload. The oracle records the observed GitHub rate-limit limit, remaining count, reset epoch, and resource class.

Open PRs and workflow runs are paginated in pages of 100 and then canonicalized locally. API response order is never used as semantic order.

The ETag cache is process-local in V1. Retry/backoff and a persistent authenticated acquisition cache are future operational-hardening slices.

## Exact-head workflow binding

The Actions endpoint is queried by target `head_sha`, but AEDR does not trust that server-side filter as sufficient. `GitHubLiveOracle` independently rejects every returned workflow run whose `run.head_sha` does not equal the requested head. `DeterministicSnapshotBuilder` repeats the same filter as a second fail-closed boundary.

Only a same-head `conclusion == success` may contribute `exact_head_green = true`. `queued`, `in_progress`, `skipped`, `cancelled`, `action_required`, stale success, and unknown conclusions never become GREEN.

`exact_head_green` is only a convenience fact that at least one exact-head workflow succeeded. It is **not** proof that all required workflows passed and it is never converted into a falsification surface.

## Adapter boundary

The acquisition adapter translates only information established by the snapshot:

- workflow receipts become exact-head `EvidenceReceiptRef` objects with `authority_class = NONE`;
- `domain:mhp` maps to `SEMANTIC_LINEAGE_EVIDENCE`, not hardware evidence;
- a PR `base_sha` is not silently represented as the commit's immediate parent;
- missing ancestry pairs become `UNKNOWN`, never inferred from mergeability or branch names;
- the V1 falsification-surface oracle returns `None` until a separately authenticated surface-acquisition contract exists.

Consequently a workflow SUCCESS bit alone can never establish AEDR dominance or supersession.

## Supersession rule

`A` may be proposed as a supersession candidate for `B` only when:

1. authority domains are exactly equal under V1 policy;
2. both independently acquired falsification surfaces bind their live exact heads;
3. `A` has an exact-head terminal GREEN receipt bound to its current head;
4. `A`'s own required behavior/falsifiers are internally complete;
5. `required_behavior(B) <= verified_behavior(A)`;
6. `required_falsifiers(B) <= verified_falsifiers(A)`;
7. every non-generated path unique to `B` remains represented in `A` under the strict V1 no-drop rule;
8. `A` introduces no new assumption-debt identity;
9. `A` introduces no new security-exposure identity.

Even then the result is only `PROPOSE_SUPERSESSION_REVIEW`, never automatic branch closure.

## Ancestry orientation

The ancestry oracle follows GitHub compare semantics `base...head`. A declared current parent is integrated only when `parent_head...child_head` establishes the parent as an ancestor of the child (`behind_by == 0`).

V1 acquisition stores main-to-PR anchors plus explicitly declared parent and semantic-dependency comparisons. It does not yet perform an exhaustive all-pairs ancestry matrix; absent relationships remain `UNKNOWN` and fail closed.

## Semantic join rule

Semantic dependencies are independent of exact base equality. If PR `B` declares PR `A` as a semantic prerequisite, `A.head` must be an ancestor of `B.head`; otherwise AEDR emits `PROPOSE_SEMANTIC_JOIN`, including when generated/bot commits moved either exact base.

Body parsing in V1 recognizes explicit machine-readable markers:

- `[parent-pr: #123]`
- `[head-sha: <7-to-40 hex chars>]`
- `[depends-on: #123, #124]`

Free-form prose is not silently interpreted as authoritative dependency metadata.

## Current authority boundary

```text
ACQUISITION_AUTHORITY       = NONE
ACQUISITION_EXECUTION_MODE  = READ_ONLY
SNAPSHOT_SIGNER_AUTHORITY   = NOT_ESTABLISHED
FALSIFICATION_SURFACE_LIVE  = NOT_IMPLEMENTED
EXHAUSTIVE_ANCESTRY_MATRIX  = NOT_IMPLEMENTED
AUTO_MERGE                  = FORBIDDEN
AUTO_CLOSE                  = FORBIDDEN
AUTO_REBASE                 = NOT_IMPLEMENTED
AUTO_DEPLOY                 = FORBIDDEN
AUTO_ADMISSION              = FORBIDDEN
```

Live acquisition therefore supplies immutable, deterministic observation evidence to AEDR. It does not decide repository truth, mint authority, or authorize destructive reconstruction by itself.
