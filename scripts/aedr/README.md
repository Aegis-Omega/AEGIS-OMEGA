# AEDR Multilayer DAG V1

AEDR models repository consolidation as five orthogonal relations over one freshly resolved exact-head snapshot:

- `E_git` — commit ancestry only;
- `E_sem` — semantic prerequisite/dependency only;
- `E_auth` — authority-domain overlap only;
- `E_evidence` — exact-head receipt/falsification bindings only;
- `E_conflict` — detected incompatible/divergent relations only.

No edge implies another edge. In particular, mergeability is not proof, semantic dependency is not git ancestry, and a receipt from a stale SHA cannot authorize a current-head claim.

## Authority boundary

The V1 evaluator is advisory only. Its outputs are `PROPOSE_*` recommendations with `authority_class = NONE`. It has no merge, close, rebase, push, deployment, admission, security-dismissal, or authority-granting surface.

The content-addressed advisory receipt is deliberately **unsigned** in V1 and reports `signature_status = UNSIGNED_CONTENT_ADDRESSED`. SHA-256 establishes deterministic payload integrity only; signer authenticity requires a later identity-bound signing layer.

## Supersession rule

`A` may be proposed as a supersession candidate for `B` only when:

1. authority domains are exactly equal under V1 policy;
2. both falsification surfaces bind their live exact heads;
3. `A` has an exact-head terminal GREEN receipt bound to its current head;
4. `A`'s own required behavior/falsifiers are internally complete;
5. `required_behavior(B) ⊆ verified_behavior(A)`;
6. `required_falsifiers(B) ⊆ verified_falsifiers(A)`;
7. every non-generated path unique to `B` remains represented in `A` under the strict V1 no-drop rule;
8. `A` introduces no new assumption-debt identity;
9. `A` introduces no new security-exposure identity.

Even then the result is only `PROPOSE_SUPERSESSION_REVIEW`, never automatic branch closure.

## Ancestry orientation

The ancestry oracle follows GitHub compare semantics `base...head`. A declared current parent is integrated only when `parent_head...child_head` reports the parent as an ancestor of the child (`behind_by == 0`).

## Semantic join rule

Semantic dependencies are independent of exact base equality. If PR `B` declares PR `A` as a semantic prerequisite, `A.head` must be an ancestor of `B.head`; otherwise AEDR emits `PROPOSE_SEMANTIC_JOIN`, including when generated/bot commits moved either exact base.

## Scope

This lane does not execute repository reconciliation by itself. Live graph acquisition, authenticated GitHub ancestry/evidence oracles, identity-bound signing, and reversible branch reconstruction are separate future slices.
