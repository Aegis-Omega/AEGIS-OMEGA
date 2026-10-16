# AEGIS Ω × AlphaEvolve — Corpus-Wide Evidence Contract (2026-10-12)

Existing PR: #773. Existing issue: #758 (evidence-gated evolution), #757 (evaluation laboratory). No additional dispatcher, automatic PR merge, paid service, wallet, agent authority, or theorem promotion.

## What was actually executed (local source catalog SHA-256)

`ee052e36b1b9e3b9fb1b7b3d19af2e2f29abf1820d88c64b9f4d6685216344d5` = SHA-256 of the exact **local** `corpus.sqlite` bytes (not a Git commit or remote-accessible dataset).

- 67,445 indexed objects; exactly 67,445 have an outcome in `coverage`.
- 32,841 unique content digests independently evaluated for fully reversible storage representation, with 98,418 actually executed codec candidates. 34,476 aliases were bound to those results; 61 source records quarantined and 67 sensitive-path records metadata-only.
- 2,204,317,162 original bytes across evaluated unique content; winning recipes total 1,312,098,575 encoded bytes; potential saving 892,218,587 bytes (not a production storage saving; encoded outputs have not been persisted).
- Every scored compressed candidate was verified by streaming decompression and comparing its original SHA-256. Source files were not overwritten.
- JSON/Python parsed without execution, Lean/Coq sources inspected **statically only**; a source is NOT a proved theorem without a pinned kernel build.
- Scientific observational task families: 39 numeric time series, 13 auto-selected tabular prediction tasks, **38 QuantumDNA NPZ archives** (76 tensor-array comparisons). The two references `reference_Hawke2010_states.npz` and `reference_1BNA_states.npz` were handled with 37×37 complex density matrices and `H_rad_ps` Hamiltonian. Sampled trace/Hermiticity/eigenvalue checks passed; independently verified physical validity is **not** established.
- 105 distinct CSV contents have no supported domain evaluator/meaningful target, and two CSV contents are beyond the bounded parser.
- The frontier router assigned all 32,841 evaluated unique digests to 129 discovered cohorts. At this point, 90 have executed observational scientific evaluators; 24,069 need domain-appropriate evaluators; 8,682 have representation evolution only.

## What **not** to infer

This is not a proof of RH, drug discovery, a new physical law, performance on an independent external cohort, production ROI, Google DeepMind AlphaEvolve deployment, or completion of all remote GitHub/Drive data intake. Only the imported local snapshot is covered.

## Actual executable modules

- `agents/alphaevolve_corpus_wide_v1.py`: streaming exact-sha reversible codec search, bounded JSON/Python/formal lenses, time series and supervised-looking *observational* tabular exploration, SQLite `coverage` and `trials`.
- `agents/alphaevolve_quantum_tensor_v1.py`: exact-sha read-only density matrix interpolation tests, per-archive scientific outcomes, sampled PSD/trace/Hermiticity preflight; no tensor mutation.
- `agents/alphaevolve_frontier_router_v1.py`: content-derived 129-cohort research work queue and explicit evaluator gaps; no automatic scientific promotion.
- Tests: `agents/tests/test_alphaevolve_corpus_wide_v1.py`, `test_alphaevolve_quantum_tensor_v1.py`, `test_alphaevolve_frontier_router_v1.py` in the already-existing Python Bridge CI job.

## Reproduction against operator-owned imported corpus

```bash
PYTHONPATH=. python -m agents.alphaevolve_corpus_wide_v1 --catalog /absolute/path/corpus.sqlite --root /absolute/import-root --out /tmp/aegis-evolution.sqlite --receipt /tmp/aegis-evolution.json
PYTHONPATH=. python -m agents.alphaevolve_quantum_tensor_v1 --catalog /absolute/path/corpus.sqlite --root /absolute/import-root --db /tmp/aegis-evolution.sqlite --out /tmp/aegis-quantum.json
PYTHONPATH=. python -m agents.alphaevolve_frontier_router_v1 --db /tmp/aegis-evolution.sqlite --out /tmp/aegis-frontier.json
PYTHONPATH=. python -m unittest agents.tests.test_alphaevolve_corpus_wide_v1 agents.tests.test_alphaevolve_quantum_tensor_v1 agents.tests.test_alphaevolve_frontier_router_v1 -v
```

Do not commit imported user source bytes to GitHub. Keep the corpus outside the repository. Rebind science revisions when the evaluator changes; never silently reclassify historical experiments. Do not use `needs review` as `PASS`. New hosted CI PASS and independent reviewer remain necessary before admitting an improvement.
