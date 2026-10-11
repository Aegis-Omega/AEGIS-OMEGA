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
