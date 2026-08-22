# AEGIS Repository Reconciliation and Continuity Design

Date: 2026-08-21
Status: operator-approved direction; implementation must remain fail-closed and evidence-bound.

## Problem

AEGIS has accumulated a large off-main knowledge universe, many stacked PRs, provider-created branches, historical experiments, and external/session artifacts. Existing agent startup logic answers only "where am I now?" and does not resolve "what prior work must I continue?". This permits repeated reinvention, false absence claims, duplicate branches, and stranded validated work.

The repository already records this failure mode in `WORKFLOW.md`: sessions reinvented from scratch and work was stranded on feature branches. The current `ground-truth.sh` reports current branch/main drift but does not resolve task lineage across all refs, PRs, historical provider work, Drive/corpus, or workflow artifacts.

## Non-negotiable invariants

1. `main` is the admitted/canonical runtime state, not the complete knowledge universe.
2. A worktree miss is never a global absence result.
3. A branch/PR name is evidence of a named reference, not proof of implementation.
4. No branch may be deleted until redundancy is mechanically proven against an identified container ref and its tip SHA is recorded.
5. No PR may be merged merely because it is mergeable. Exact-head evidence, parent lineage, unresolved blockers, and scope must be checked first.
6. No new branch may be created when a compatible active or recoverable lineage already exists.
7. Provider/model output is evidence only, never authority.
8. Reconciliation must preserve Decision / Execution / Effect / Admission separation and all frozen CEL v1.1 epistemic boundaries.
9. Cleanup must never erase unique historical evidence. "Clean" means classify, consolidate, archive, merge, or prove redundant before deletion.
10. Every destructive or canonical mutation must be replayable from a recorded reconciliation decision.

## Three universes

AEGIS must represent three different sets explicitly.

### Knowledge Universe

Everything the organization may have learned or built:

- all reachable Git commits across all refs;
- open and closed PR heads/base relationships;
- tags and historical integration anchors;
- CI/workflow candidate SHAs and retained artifacts;
- provider/session work that can be recovered;
- Google Drive/research corpus artifacts;
- named artifacts whose current branch name no longer identifies their original implementation;
- optional unreachable/dangling Git objects when a full clone is available.

Knowledge membership does not imply correctness or admission.

### Active Work Universe

All work that is still being developed, reviewed, integrated, or recovered. Each work item has a stable WorkID independent of its branch name.

### Admitted Runtime

Only canonical state admitted to `main` under current policy and evidence gates.

The system must never infer `not in Admitted Runtime => does not exist`.

## Stable work identity

Branch names are mutable transport references, not work identity. Every active/recovered unit must map to:

- `work_id`
- `objective_digest`
- `capability_set`
- `lineage_root`
- `current_head`
- `current_ref`
- `parent_work_ids`
- `pr_number` when present
- `owner_lease` / generation when active
- `evidence_roots`
- `verification_state`
- `admission_state`
- `supersedes` / `superseded_by`
- `known_failures`
- `required_rules`

## Lineage resolver

Before any provider starts implementation, AEGIS resolves the requested work against the Knowledge + Active Work universes.

Allowed outcomes:

- `CONTINUE_EXISTING`
- `STACK_ON_EXISTING`
- `RESUME_ABANDONED`
- `CREATE_NEW`
- `AMBIGUOUS_HALT`

Hard rule:

`CreateBranch(W) => ResolveLineage(W) == CREATE_NEW`

and:

`exists L: Compatible(L,W) => CreateBranch(W) == DENY`

Compatibility must consider objective/capability/path overlap, explicit parentage, PR topology, exact referenced artifacts, and provider/session provenance. Name equality alone is insufficient.

## Existing integration spine

The current repository already contains a real integration spine rooted at PR #275 rather than isolated feature islands. The active lineage observed from GitHub is:

`#275 -> #276 -> #277 -> #278 -> #279 -> #280 -> #282 -> #283 -> #284 -> #285 -> #290 -> #291`

with separate side prooflines and side products that must be reconciled, not blindly merged. PR #275 explicitly identifies itself as the single UCI integration spine and is based on canonical main. That existing spine is the preferred convergence target unless evidence shows a later lineage should supersede it.

Side lineages include, among others:

- effect/receipt history already transplanted into the UCI spine (#268 -> #270 -> #272 -> #273, then reconciled by #276);
- formal proof/refinement lineage (#286 -> #289 -> #292) based from the Trace SDK;
- cross-plane experiment #281;
- Khatt/Abjad #274;
- Memory Sentinel #267;
- older product, provider, billing, App Intents, ECD, and agent-skill PRs.

No side lineage is discarded until its unique diff and evidence are classified.

## Reconciliation classification

Every branch/PR/work item receives exactly one current classification:

- `ACTIVE_SPINE`
- `READY_TO_ADMIT`
- `NEEDS_REVERIFY`
- `BLOCKED`
- `UNIQUE_SIDE_CAPABILITY`
- `SUPERSEDED_BY`
- `REDUNDANT_PROVEN`
- `HISTORICAL_EVIDENCE_ONLY`
- `RECOVERY_REQUIRED`
- `UNKNOWN_FAIL_CLOSED`

`UNKNOWN_FAIL_CLOSED` may never be deleted, merged, or treated as absent.

## Merge discipline

Reconciliation proceeds bottom-up from the nearest canonical parent. A downstream PR cannot be promoted merely because its own tests are green if its parent is unadmitted or its exact-parent contract would be invalidated by retargeting.

For each candidate:

1. resolve exact current head and base;
2. identify unique commits/files relative to the intended container;
3. verify whether another active lineage already contains those changes;
4. read current CI/check state for the exact head;
5. preserve artifacts/receipt roots needed to explain historical assertions;
6. determine whether merge, transplant, restack/reverify, archive, or proven deletion is correct;
7. perform one mutation at a time;
8. re-read resulting GitHub state before continuing.

No bulk merge button and no bulk branch deletion.

## Cleanup discipline

PR #287 already contains a useful reachability-based cleanup concept. Its safe principle is retained: a candidate branch is only deletable if `git merge-base --is-ancestor candidate container` succeeds (or an explicitly allowed generated-manifest-only delta is independently checked), the candidate tip SHA is recorded, and the intended container is identified.

However cleanup runs only after the repository-wide lineage manifest exists. The branch named `claude/proof-prism-v1-ltti67` demonstrates why branch names cannot be trusted as work identity: its present tip is a cleanup PR while historical session evidence shows the Proof Prism work existed elsewhere in the provider workspace/history.

## Recovery discipline

Recovery is structural, not name-only. Named artifacts such as ProofPrism are searched by:

- exact names and aliases;
- file/path signatures;
- API/type/function fingerprints;
- commit-message semantics;
- PR/workflow exact SHAs;
- session/provider artifacts where accessible;
- Drive/research corpus.

Recovered content remains `RECOVERY_REQUIRED` or `HISTORICAL_EVIDENCE_ONLY` until exact source identity and current compatibility are established.

## Provider continuity

Claude, Codex/OpenAI, Gemini, and future provider agents must receive the same WorkID and continuation envelope:

- work ID/objective digest;
- continuation ref and expected head;
- exact parent/dependency work IDs;
- allowed scope/capabilities/tools/providers;
- current lease/fence;
- known evidence and known failures;
- required repository rules;
- unresolved verification debt.

A second provider encountering an already leased WorkID becomes verifier/reviewer/helper unless the scheduler explicitly grants another non-conflicting node. It does not create a competing branch for the same objective.

## Connector relation

The future connector capability plane is subordinate to this continuity model. GitHub, Drive, SciSpace, Hugging Face, Airtable, Slack, Gmail, Supabase, Vercel and other connectors may produce observations/evidence or execute authorized effects, but they do not define work identity or authority. Cross-provider agents access connectors through AEGIS-bound WorkOrders and the same lineage state.

## Execution phases

### Phase 0 — Stop adding entropy

- no new feature branch for work with an existing compatible lineage;
- no destructive branch cleanup;
- no broad merge while classification is unknown.

### Phase 1 — Complete census

Build a machine-readable repository-universe manifest from all reachable refs/PRs and current workflow evidence. Record canonical main separately from off-main knowledge.

### Phase 2 — Build lineage graph

Map PR bases/heads, ancestry, duplicate containment, integration-spine membership, side capabilities, and supersession relationships. Attach stable WorkIDs.

### Phase 3 — Reconcile the active spine

Walk the #275-derived chain in parent order. For every node decide `READY_TO_ADMIT`, `NEEDS_REVERIFY`, or `BLOCKED`. Never invalidate frozen-parent evidence silently; restack/reverify where canonical parent movement changes the contract.

### Phase 4 — Salvage side capabilities

Compare every non-spine PR/branch against the reconciled spine. Transplant only unique, still-desired capability slices with preserved provenance. Archive obsolete experiments as evidence rather than pretending they never existed.

### Phase 5 — Proven cleanup

Only after containment classification, run branch cleanup in dry-run mode, compare the output to the manifest, then delete proven-redundant refs individually or in an explicitly reviewed batch. Preserve tip SHAs in the reconciliation receipt.

### Phase 6 — Enforce continuity for all providers

Move lineage resolution into session startup / `aegis_next_work`, so provider sessions cannot start blind or open duplicate branches.

### Phase 7 — Cross-provider connector plane

Expose shared connectors/skills/tools through the existing provider-neutral AEGIS MCP after continuity and WorkOrder identity are enforced.

## Required machine artifacts

Implementation should converge on these bounded artifacts rather than another prose-only workflow:

- `.aegis/reconciliation/repository-universe.v1.json`
- `.aegis/reconciliation/work-lineage.v1.json`
- `.aegis/reconciliation/reconciliation-decisions.v1.jsonl`
- `scripts/reconcile-repository-universe.py`
- `scripts/resolve-work-lineage.py`
- tests that prove duplicate branch creation is denied when compatible work exists;
- tests that prove unknown/incomplete discovery cannot authorize deletion;
- provider session/startup integration that surfaces the resolved continuation envelope.

Exact filenames may change only if an already-existing repository primitive should be reused; reuse is preferred to duplication.

## Success criteria

The reconciliation program is successful when:

1. every reachable open PR and non-main branch is classified with an evidence-backed disposition;
2. the primary UCI/Company Brain lineage has one explicit convergence path to canonical main;
3. unique side capabilities have a recorded keep/transplant/archive decision;
4. redundant refs can be deleted only by mechanical containment proof;
5. provider sessions receive a WorkID + continuation ref before coding;
6. duplicate branch creation for compatible work fails closed;
7. ProofPrism-class false negatives are no longer possible from current-worktree-only search;
8. connector availability is shared through AEGIS without granting provider authority;
9. every merge/deletion has a replayable decision record;
10. no historical evidence is silently lost during cleanup.
