# AEGIS Ω unified evolution workplane — integration map v1

**Purpose:** Connect the ALREADY EXISTING Issue board, dendritic information
plane, evolution contract, local mailbox, relay attestation and skill lineage
without creating another orchestrator or asserting that experiments ran.

This implementation extends [PR #773](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/773).
It does not merge #727, #730, #732, #743, #747 or #766 into this branch.
Those remain distinct candidate PRs with independent exact-head admission.

## Data plane (implemented)

| Existing component | Input | Output / connection | Status |
| --- | --- | --- | --- |
| `agents/issue_evolution.py` | Open Issue snapshot | All Issue contracts and relationship graph | Compiles metadata; source snapshot external |
| `evolve_issues()` | Graph + optional paired trial records | Per-Issue seven proposal families, loss-preserving round | Trials are self-reported |
| `spread_issue_graph()` | Graph + pinned source HEAD | Topic-specific dendritic routes in chunks of 32 | In-memory information |
| `agents/dendrite_workplane.py` | Graph + evolution round | Single content-hashed workplane; explicit cross-Issue lesson packets routed according to TARGET Issue topic | Actual integration adapter |
| `agents/dendrite_system.py` | Typed packets | Bounded routing over 19 existing roles; quarantine | No execution |
| `agents/dendrite_mailbox.py` | Routing receipts | Private local on-disk role inboxes with idempotent retry | Optional publisher writes local files |
| `agents/dendrite_attestation.py` | Local inbox + operator HMAC | Authenticated **local relay**, strict recipient check | Not original-source authentication |
| `agents/evolution.py` | Existing skill tree + adaptive lineage | `EvolutionEngine.tick(apply_changes=False)` read-only eligibility observations | **Zero promotion or mutation** |
| `agents/cognitive_pipeline.py` | Actual research arbitration | Existing `--dendrite` topic route and spool | Independent producer |
| `agents/revenue_engine.py` | Actual revenue-cycle artifacts | Existing `--dendrite` topic route and spool | Existing producer has separate side effects |
| `agents/dendrite_formal_gate.py` | Exact local Lean HEAD source | Formal source-bound message to relay | Does not prove RH |
| `agents/coordinator.py` / `AuthorityEvaluator` | Existing authority decisions | **Not called or modified** by informational workplane | Exclusive operational gate |

The workplane returns `skill_promotion=DENIED`, `production_admission=DENIED`,
`authority_effect=NONE` and `execution_effect=NONE` unconditionally.

## Full Issue board, nonexecuting

The read-only API snapshot captured on 2026-10-12 has 37 actual open Issues
(out of 281 open Issue+PR entries). The snapshot is explicitly historical.
There are 70 deduplicated relations within the open Issue subset and 49
unresolved references outside it; none creates execution permissions.

The CLI completes BOTH 32+5 informational batches for all 37 Issues and,
when trial records exist, produces additional batched lesson messages,
targeted to the destination Issue's topic. Quarantined operator-required
Issues do not reach business or engineering inboxes.

```sh
# Dry-run: compile all Issues; no new network, model, money or filesystem writes
python3 -m agents.dendrite_workplane \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --source-head "$(git rev-parse HEAD)" \
  > /tmp/aegis-unified-workplane.json

# Optional read-only inspection of existing skill tiers (no apply):
python3 -m agents.dendrite_workplane \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --source-head "$(git rev-parse HEAD)" \
  --skill-tree harness/skill_tree.json \
  --lineage agents/adaptive_lineage.json \
  > /tmp/aegis-workplane-with-skill-observation.json

# Optional, explicitly requested local delivery; no agent execution.
python3 -m agents.dendrite_workplane \
  --snapshot examples/issue_evolution_snapshot_20261012.json \
  --source-head "$(git rev-parse HEAD)" \
  --spool-dir "$HOME/.aegis-dendrite-inbox"
```

HMAC relay options are available only with a spool:
`--relay-key-file <PRIVATE_0600_KEY_FILE> --relay-key-id operator_relay`.
Secrets never belong in Git commits. The spool remains plaintext and
accessible to the same authorized OS user.

The optional `--trials` input is an **array** of issue-evolution trial
records (not the single trial JSON file). A candidate score, even with
a significant exact sign test, is never independent outcome proof.

## Still separate / not misrepresented as connected production services

- #749 universal contract and #750 durable workflow runtime: pure graph is
  metadata, not executable task scheduling.
- #751 evidence adapters, #755 adversarial independent review and #757
  hidden holdouts: **not replaced**, no PASS synthesized from trial scores.
- #753 durable memory/retractions: workplane JSON is an exportable round,
  not a long-lived secured research memory or automatic training corpus.
- #754 / PR #730 capability selection and existing Automaton-3 authority:
  no role privilege or skill rank expansion.
- #765 / PR #766 source scout: source URL snapshots remain separate until
  trusted publisher/collection receipts are available.
- #746 / PR #747 proof-carrying GitHub admission: signed commits, protected
  main and independently executed tests are mandatory.
- Other repositories and their 11k+ Lean files are **not silently scanned**
  or mutated by a 37-Issue snapshot of AEGIS-OMEGA. Formal Conjectures
  ingress is separately covered by its PR #82.
- Evolution like AlphaEvolve requires real mutation/selection/search over
  actual algorithm implementations, benchmark execution, independent
  evaluators, budget tracking, negative-result retention and rollback.
  The current workplane is the **coupling foundation**, not that completed
  autonomous scientific/evolutionary search engine.

## Verification

```sh
python3 -m unittest \
  agents.tests.test_dendrite_mesh \
  agents.tests.test_dendrite_system \
  agents.tests.test_dendrite_mailbox \
  agents.tests.test_dendrite_attestation \
  agents.tests.test_dendrite_formal_gate \
  agents.tests.test_issue_evolution \
  agents.tests.test_dendrite_workplane -v
```

The existing Python CI job is extended with 13 workplane tests. A local
test of the workplane against the real dendrite transport and a substitute
issue compiler is **not** a native exact-head repository test of the complete
Issue graph. Keep PR DRAFT and fail closed while hosted jobs skip or fail
before executing.

## Actual bounded routing evolution experiment (2026-10-12)

`agents/dendrite_route_evolution.py` is a real **search over routing
configuration candidates**, NOT an assertion that algorithms magically
evolved. For each of six informational topics it enumerates TTL 0–8, invokes
the existing 19-node `system_mesh().propagate()` and measures exact
recipient-set coverage and message deliveries against an explicitly frozen
TTL=5 baseline. It separately exhausts quarantine behavior to veto leakage.
It retains all 54 candidate routing traces with deterministic hashes,
including losses/coverage failures.

Current *synthetic objective* result (not real latency/cost measurement):
- Formal: candidate TTL 3 instead of 5; one fewer delivery.
- Engineering: TTL 1 instead of 5; three fewer deliveries.
- Security: TTL 1 instead of 5; two fewer deliveries.
- Commerce: TTL 2 instead of 5; one fewer delivery.
- Research and operations: no claimed improvement.

These are advisory `NOT_ADMITTED` candidates. They are included in
`dendrite_workplane.compose(...)["candidate_route_search"]` but **never
change active TTL, subscriptions, authorization, task routing or actual
agents**. The objectives are author-defined fixtures, not independent hidden
tests or observed production utility. A future #757 evaluator must test
comparable real work before considering adoption.

## Reconciliation with the co-developed contract spine

The current PR branch also contains `agents/evolution_contract_spine.py`
and `agents/tests/test_evolution_contract_spine.py`, which were present
during exact-head reconciliation and are **reused**, not overwritten.
The spine's `--snapshot` entrypoint already calls
`dendrite_workplane.compose(...)`, binds its receipt to the same Issue graph
and evolution round, and emits a per-Issue informational token linked to
the existing AdaptiveLineage and sealed skill registry when supplied.

The current branch's `agents/evolution.py` and
`agents/tests/test_evolution_no_self_promotion.py` also close the
reported-counters-to-tier-mutation path: even `tick(apply_changes=True)`
cannot promote skills based on such untrusted counters. These concurrent
changes belong to the PR as a whole, not to a falsely attributed single step.

```sh
# Same 37-Issue snapshot, plus explicit no-trial input.
printf '[]\\n' > /tmp/aegis-none-trials.json
python3 -m agents.evolution_contract_spine \\
  --snapshot examples/issue_evolution_snapshot_20261012.json \\
  --trials /tmp/aegis-none-trials.json \\
  --source-head "$(git rev-parse HEAD)" \\
  > /tmp/aegis-unified-contract-spine.json

# Independent routing strategy search regression ring.
python3 -m unittest agents.tests.test_dendrite_route_evolution -v
```

**Still open:** full GitHub-native exact-head tests and signed/protected
admission, externally verified source/publisher identity, real heterogeneous
holdouts, provider/agent runtime delivery, signed independent review,
rollback-on-regression, and field measurements. No claim is made that all
unmerged PR branches or all Lean source modules were compiled into one
runtime. The connected core is the existing contracts and informational
planes, with future execution gated by the separate authority workflow.
