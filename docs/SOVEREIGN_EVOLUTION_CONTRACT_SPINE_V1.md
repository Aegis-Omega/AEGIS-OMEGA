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
