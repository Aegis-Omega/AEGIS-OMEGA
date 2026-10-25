# AEGIS Ω / #758 — bioreactor cohort evaluation

This document records **real observational execution**, not an admission or a claim of biological discovery.

## Imported-source problem closed

The 67,445-record imported catalog previously classified headerless yeast-bioreactor CSVs as `CSV_EVALUATOR_PENDING`. Their numeric first line was mistaken for a header, and some use semicolon delimiters with decimal commas. The existing `agents/alphaevolve_frontier_router_v1.py` now optionally invokes `agents/alphaevolve_bioreactor_v1.py` when given an explicitly mounted corpus root.

No dataset bytes are committed to this repository. Source material is looked up by SHA-256 in the local read-only SQLite catalog.

## Observed local replay (2026-10-12)

- Catalog entries: **67,445**; distinct source contents in the catalog: **32,841**.
- Bioreactor CSVs discovered/evaluated: **8/8**; measured channels: **17**.
- Candidate algorithms: **12 causal one-step predictors per channel**, selected using validation data only.
- Held-out later-time segment: **13 channels** improved against the last-value baseline, **one degraded**, and remaining channels tied.
- Illustrative later-time prediction MSE reductions: 48.82%, 48.06%, 49.38%, 46.30% on four long, distinct source traces.
- **9/9 new local regression/integration tests PASS.**
- No independent biological replication or mechanistic claim; `scientific_admission=DENIED`. The tests and replay do not create new AEGIS authority.

The raw corpus and independently generated full replay JSON remain outside the public repository. To reproduce using the same imported corpus tree:

```bash
PYTHONPATH=. python -m unittest agents.tests.test_alphaevolve_bioreactor_v1 agents.tests.test_alphaevolve_bioreactor_route_v1 -v
PYTHONPATH=. python -m agents.alphaevolve_frontier_router_v1 --db /path/to/AEGIS_evolution_67445.sqlite --data-root /path/to/imported/corpus/root --out /path/to/bioreactor_replay.json
```

The associated GitHub CI job is observational only and is intentionally excluded from constitutional admission. If the host reports failure without starting any test steps, that **does not establish a Python test failure**.

This closes one previously excluded scientific cohort, **not** automatic scientific evolution across every imported domain. Unsupported families remain explicitly `EVALUATOR_REQUIRED`.
