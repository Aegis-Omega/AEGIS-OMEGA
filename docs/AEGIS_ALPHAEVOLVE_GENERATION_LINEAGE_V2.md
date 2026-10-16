# AEGIS Ω — AlphaEvolve generational lineage (issue #758 / PR #773)

## Integrated source, not a new dispatcher

- `agents/alphaevolve_corpus_discovery_v1.py`: discovers constrained time-series hypotheses by inspecting byte-hashed local corpus catalog entries. Non-evaluable data remains `EVALUATOR_MISSING` / `NOT_EVALUATED`.
- `agents/alphaevolve_islands_v1.py`: four-island candidate archive, reproducible parent selection, fixed non-executable three-parameter DSL, bounded experiment, resumable campaign.
- `agents/alphaevolve_genetic_inheritance_v1.py`: two-parent diploid crossover, mutation, genotype/phenotype binding, XX/XY-inspired *heuristic* regulator and auditable ancestry. Not a model of human biology.
- `agents/alphaevolve_generation_ledger_v1.py`: arbitrary-precision decimal generation IDs (including 2^128), verified contiguous append-only SHA-256 links and migration from legacy INTEGER ticks.
- Regression suites are wired into the EXISTING `.github/workflows/ci.yml` Python Bridge job. No new dispatcher, schedule, self-promotion, wallet authority or deployment.

## Reproduce on a local corpus with explicit permission

Install Python >= 3.11, NumPy 2.2.6. Place a local `corpus.sqlite` and its `imported/` directory under `$AEGIS_CORPUS`.

```sh
PYTHONPATH=. python3 -m unittest \
 agents.tests.test_alphaevolve_corpus_discovery_v1 \
 agents.tests.test_alphaevolve_islands_v1 \
 agents.tests.test_alphaevolve_genetic_inheritance_v1 \
 agents.tests.test_alphaevolve_generation_ledger_v1 -v

PYTHONPATH=. python3 -m agents.alphaevolve_islands_v1 search \
 --catalog "$AEGIS_CORPUS/corpus.sqlite" --root "$AEGIS_CORPUS" \
 --db "$AEGIS_CAMPAIGN_DB" --ticks 300 --islands 4 \
 --seed 758 --inheritance diploid_xy_v1
```

**Never use `finalize` during routine search.** It opens a one-shot heldout and permanently freezes the campaign. No raw private source data is committed to this public repository.

## Evidence measured locally, 2026-10-12

- Four regression suites, **39/39 PASS** on Python 3.13/NumPy 2.3.5. These local versions differ from CI's Python 3.11/NumPy 2.2.6; CI has not established hosted PASS.
- The real AEGIS QuantumDNA campaign was resumed on an *isolated copy*: 1,701 -> 2,001 recorded candidate-proposal steps, 1,881 unique candidate programs evaluated. It includes **120 duplicate proposal steps** that did **not** trigger a new evaluation; the 2,001 steps must never be quoted as 2,001 independent experiments.
- Candidate outcome counts: 1,723 `EVALUATED_CANDIDATE`, 158 `EVALUATED_VETO`, 120 `DUPLICATE`.
- 1,992 completed genetic offspring had both previously evaluated parents. The 9 initial steps are seeded founders.
- Parent lookup previously performed a correlated full table scan. Added `idx_breeding_candidate_first ON breeding(candidate_id)` and a query-plan test; isolated query measured 0.107 seconds before, 0.003 seconds after, not an end-to-end 35x speedup.
- The 101 post-timeout steps (1,900 -> 2,001) completed in **1.387 seconds** with the index. The best validation relative-MSE remained **0.0009006286442499431** (unchanged from 1,701), so there is **no new measured fitness improvement**.
- Original campaign database remained byte-identical. Frozen holdout was **not** opened.
- This establishes local execution and reproducibility **only**. No independently sourced 30+ paired holdout groups, independent reviewer, signed exact-head CI PASS, or scientific proof.

## Generation-depth claim

Representing generation `2^128` requires at least 129 bits. The ledger supports arbitrary-precision text IDs, but it **never fabricates missing generation events**. At 2,001 recorded steps the claim is 2,001; not `2^128`. Physical time and database capacities remain bounded.

## Integration and admission

Owner issues: #758 (evidence-gated evolution), #757 (evaluation lab); umbrella #734. Existing `agents/issue_evolution.py` and `agents/evolution_contract_spine.py` remain the authority/admission boundary; autonomous discovery emits research evidence only. `promotion=DENIED`, `scientific_admission=DENIED`, `authority_effect=NONE`. Human review required for consequential changes.

## Immediate remaining proof obligations

1. Get exact-head GitHub CI jobs to **execute**, not just show pre-execution failures; no green assertion until logs confirm native tests.
2. Implement real domain evaluators for the currently `EVALUATOR_MISSING` families and new independent train/validation/heldout groups; do not fake independence by multiplying row counts.
3. Distinguish proposal steps, unique program evaluations and physically distinct scientific replications in receipts.
4. Only after reproduced gains and #758's full evidence threshold should any candidate be considered for governed promotion.
