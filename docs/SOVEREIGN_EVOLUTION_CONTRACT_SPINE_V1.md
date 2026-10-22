# AEGIS Ω — Sovereign Evolution Contract Spine v1

This reuses existing modules: no new agent coordinator, blockchain currency,
tier manager, authority policy, or independent learning system.

Existing GitHub Issue → issue_evolution contract → dendrite_workplane →
dendrite information packets → paired-trial screen → counterexample memory →
AdaptiveLineage checkpoint → sealed skill-registry checkpoint → optional
existing AuthorityEvaluator D0 observation.

## Existing source-to-source integration

| Existing module | Connected mechanism | Trust limit |
| --- | --- | --- |
| #734 / agents/issue_evolution.py | Reuse per-Issue evolution contracts, dependency DAG, 30-pair screen, negative results | Text/scores unverified |
| agents/dendrite_workplane.py | Optional exact workplane receipt hash bound into each issue token | No second dispatcher |
| agents/dendrite_system.py | Bounded 32-event batches over existing role mesh | Informational only |
| #727 / agents/evolution.py | Reuse exact Foundry no-self-promotion repair and no-write regression tests | Eligibility is not promotion |
| AdaptiveLineage | Replay existing hash chain and bind terminal root | Chain consistency, not authorship |
| harness/sdk/skill_authority.py | Recompute sealed V2 registry root | Digest does not authenticate observations |
| #727 Foundry negative knowledge | Hash explicit per-issue counterexample candidate | Witness not externally authenticated |
| harness/sdk/authority_client.py | Optional read-only D0 request through existing AuthorityEvaluator | Observed D0 admission != operational permission |
| #746/#747, #751/#755, #757/#758 | Actual independent review remains mandatory | No self-reported PASS |

## What an informational evolution token means

Each AEGIS_INFORMATIONAL_EVOLUTION_TOKEN_V1 is a content-addressed
NON-AUTHORIZING reference. Its token_id is the SHA-256 digest of a canonical
JSON record containing issue identity, workplane/graph/round roots,
proposal and claimed trial receipts, negative learning pointers, plus
available skill-tree and lineage roots.

It is NOT a wallet, spendable currency, Ethereum contract, public-key
signature, independently authenticated agent, permission, proof of a
scientific claim, or operational execution credential. On-chain anchoring
could be designed separately but is not implemented or needed for this
local consistency check.

Invariants:
- Explicit needs-operator remains operator-required.
- The self-reported best-case evaluation only requests independent review.
- Cross-issue lessons are pointers, never promotion votes or capabilities.
- No mutation of skills, lineage, workspace, issues, tokens on chain or main.
- Caller-supplied SHA and GitHub snapshot are NOT authenticated by hashes alone.
- No positive evaluation overrides an existing signed/protected admission gate.

## One-command offline 37-Issue replay

In the isolated PR #773 checkout (historical 2026-10-12 snapshot):

~~~sh
printf '[]\n' > /tmp/aegis-no-trials.json

python3 -m agents.evolution_contract_spine \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --trials /tmp/aegis-no-trials.json \
  --source-head "$(git rev-parse HEAD)" \
  --lineage agents/adaptive_lineage.json \
  --registry harness/skill_tree.json \
  > /tmp/aegis-sovereign-evolution-contracts.json
~~~

This builds the existing unified workplane and binds its receipt to the
contract output. Supply --graph path.json instead of --snapshot when
the graph has already been produced; no workplane claim is then made.
An invalid lineage hash, skill registry root, or workplane content is a
hard denial, never an excuse to discard evidence checks.

Optional --authority-probe performs an existing D0 read-only evaluation;
without an authenticated environment, the central client denies.

A --trials file supplies claimed paired results to the existing
issue_evolution evaluator (minimum 30 matched tasks, one-sided exact
sign-test p <= 0.01, zero safety regressions). No such synthetic result
may promote a skill without an independent evaluator.

Optional --counterexamples is an explicit list of issue/witness pairs
containing an AEGIS_REPLAYABLE_COUNTEREXAMPLE_V1 record. Each pointer
is content-hashed, labeled UNVERIFIED_COUNTEREXAMPLE_CANDIDATE and
retained as knowledge without making it a blocker or authority token.

## Scope and admission

Only the available frozen snapshot's 37 Issues and explicit references
are covered. Other repositories, private data, merged PR effects,
author identity, correctness of observations and all historical work are
not automatically discovered or certified. 32-event batches limit
in-memory dissemination. No live agents, external transport, billing,
wallet signing, proof promotions or auto-merge are enabled.

Existing Python CI now lists the new contract and no-self-promotion
regressions. Hosted exact-head native execution, independent review,
signed commits and protected-main admission remain mandatory.
No skipped job or zero-step workflow counts as PASS.

This is a bounded implementation connecting existing modules, not a
claim that every system-wide module has been integrated.


## Fusion integrity repair — 2026-10-12

### Proven failure in the prior contract binder

The spine previously accepted a caller-authored workplane containing fabricated
`issue_route_shards` as long as the caller recomputed the top-level JSON hash
and preserved selected summary fields. A hash of attacker-supplied content is
not proof that its derived data follows the canonical issue graph.

The bounded **pre-patch local replay** submitted a forged
`delivered_roles=["finance","sales"]` packet in the workplane and recomputed
`receipt_hash`. The old binder returned
`LOCAL_CONTENT_CONSISTENCY_ONLY` instead of rejecting it.

### Single fusion repair, no new service

Existing `evolution_contract_spine.py` now checks the full allowed workplane
field set and **rederives** each of the following from the already-validated
graph, exact `source_head` and existing trial reducer:

- issue evolution state;
- every 32-event issue routing shard;
- every cross-issue lesson routing shard;
- the existing bounded synthetic TTL search result;
- issue snapshot hash, explicit dependency and relationship counts;
- informational transport, source/benchmark-unverified status;
- existing EvolutionEngine observation; any reported applied promotion fails
  closed, and a claimed observed lineage must match a supplied replayed
  AdaptiveLineage root.

These computations reuse `issue_evolution.py`,
`dendrite_workplane._route_lessons`, `dendrite_route_evolution.search_routes`
and `AdaptiveLineage`. No independent second route graph, new model, contract
executor, workflow daemon, financial token, or privileged capability is created.

Six new adversarial tests in the **existing** contract-spine suite deny
rehash-after-forgery of route delivery, purported evolution outcome, route
optimizer promotion, lesson deletion, skill promotion and additional authority
metadata. The existing valid workplane test remains unchanged.

A local candidate replay with partial mirror modules produced 96/96 passing
tests (89 existing tests plus 7 targeted checks); this is **not**
a byte-identical complete-GitHub-tree native run. GitHub Python Bridge
was skipped due to upstream zero-step workflow failures at the observed
heads; no hosted PASS is claimed.

### Open issue inventory rebinding

The existing 37-issue example snapshot was re-bound to a **complete three-page
GitHub read-only API observation**. Exactly five issue records had changed
between the previous frozen snapshot and the checked API response:
#734, #753, #754, #757, #758. The `acquisition` field now records
`GITHUB_READ_ONLY_API` instead of `EXPLICIT_OFFLINE_FIXTURE`.

GitHub API retrieval authenticates neither arbitrary embedded assertions in
issue bodies nor the independent validity of trial scores. It only supplies the
observed current issue metadata as input to a reproducible local compilation.
Other repositories and inaccessible/redirected scopes remain explicitly
outside this 37-issue snapshot.

### Verification and admission limits

Recomputed consistency means that the workplane agrees with the current
in-memory source graph and the existing version-pinned code; it does **not**
authenticate the GitHub issue author, establish mathematical truth, authorize
tool execution or verify the external benchmarks. The exact-head CI, signed
commit admission, independent reviewer and any higher-authority operations
remain separate and currently blocked/unknown.

Run from an exact-head PR checkout:

~~~sh
PYTHONPATH=. python3 -m unittest \
  agents.tests.test_evolution_contract_spine \
  agents.tests.test_issue_evolution \
  agents.tests.test_dendrite_workplane \
  agents.tests.test_evolution_no_self_promotion -v
~~~
