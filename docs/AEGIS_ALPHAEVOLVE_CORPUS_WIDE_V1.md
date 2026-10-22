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


## 2026-10-22: corpus-index and semantic research integration

**Scope:** Reconcile the historical 2026-10-12 local import with eight user-supplied research/workflow artifacts. This is source reuse, not a new index, an assertion of current remote discovery, an RH proof, or permission to alter the data.

### Canonical index reconciliation

The earlier AEGIS_ALPHAEVOLVE_GLOBAL_COVERAGE_V1.md handoff and AEGIS_CorpusWide_ExactData_Receipt_v1.json identify the following single imported **snapshot**, not live counts:

| Classification | Objects |
|---|---:|
| Unique, byte-verified representation assets | 32,841 |
| Aliases of these digests | 34,476 |
| Sensitive source-path metadata only | 67 |
| Quarantined source records | 61 |
| **All imported object IDs** | **67,445** |

- Import corpus.sqlite has 67,445 original records; historical SHA-256 = ee052e36b1b9e3b9fb1b7b3d19af2e2f29abf1820d88c64b9f4d6685216344d5.
- Prior result corpus_wide_corrected.sqlite has a coverage.object_id for every imported object and 32,841 unique assets.digest. Historical trials: 98,418 **reversible storage representation** candidates, NOT 98,418 scientific discoveries.
- Existing frontier catalog routes 32,841 digests into 129 content-derived cohorts: 90 assets with observational evaluation, 24,069 evaluator-required, and 8,682 representation-only. Cohort count is not asset count.
- Historical global-coverage plan schedules 32,841 integrity/provenance slots plus 3 × 8,805 research slots = **59,256 planned slots**; 9,474 cross-domain links are **unverified metadata hypotheses**, not discoveries.
- Historical handoff names agents/alphaevolve_global_coverage_v1.py, but this module **was absent at the inspected PR #773 head 318e9ab78b8a3537a38bd3a996d1fa632a60b2df**. Do not claim that planner shipped on this branch.
- User-supplied files from 2026-10-22 are NOT assumed to be in the 2026-10-12 index. New intake must explicitly pin hashes and provenance; do not rewrite historical cardinalities.

### Read-only identity gate in the existing Frontier Router

Function: agents.alphaevolve_frontier_router_v1.reconcile_import_index(import_db, evolved_db).

It audits exact import-object IDs against evolved coverage IDs, source/coverage SHA relations, canonical and alias asset membership, verified asset flags, and the pinned import SHA in the historical receipt. Missing, stale, blocked or contradictory inputs fail closed. It reads the two existing SQLite databases and does NOT build a replacement.

Example, using explicitly mounted catalogs:

~~~bash
PYTHONPATH=. python3 - <<'PY'
import json
from pathlib import Path
from agents.alphaevolve_frontier_router_v1 import reconcile_import_index
result = reconcile_import_index(
    Path('/PATH/TO/corpus.sqlite'),
    Path('/PATH/TO/corpus_wide_corrected.sqlite'))
print(json.dumps(result, sort_keys=True, indent=2))
PY
PYTHONPATH=. python3 -m unittest agents.tests.test_alphaevolve_frontier_router_v1 -v
~~~

An EXACT_READ_ONLY_PASS proves only the **actual catalog pair supplied**. It corresponds to this historic 67,445-object snapshot only when the SHA and audited counts match. Synthetic regression tests do not constitute a live corpus replay.

### Eight source artifacts mapped to their existing ownership

| Source artifact | Existing target / reuse | Truth boundary |
|---|---|---|
| Data Intelligence_ MCP to Semantic Query.md | Evidence-backed semantic JSON requests, deterministic business metrics, lineage, provenance | Design; dbt MCP / metric provider are not deployed by this mapping |
| AEGIS-Ω Historical Handoff and Integration.docx | MJLS → RSDP → thermodynamic geometry → stochastic modal type theory research ancestry | Theory summary is not itself a Lean kernel proof |
| AI_Remaster_Workflow_Specification.md | Safe AST / IR, reversible code representation, behavioral tests for existing software evaluator | Workflow proposal, not proof of engine independence |
| AEGIS_Omega_Evolution_Workbench_RH_ProofBook_SourceReuse_V2_20261012.ipynb | Offline candidate search, source hashes, negative controls, RH proof-source reuse | Requires additional workbench modules; do not claim Run All here |
| Ecosystem Mapping: Workflow, Agents, Distributed.docx | Existing #734 orchestration, #753 memory, #757 evaluation, #758 evolution and #773 issue/checkpoint graph | Seven-layer design does not deploy Kafka/Ray/Temporal/Kubernetes |
| AEGIS_QuantumTensor_Evolution_38_v1.json | Report for 38 NPZ assets; reuse existing quantum tensor evaluator | Observational only; scientific_admission=DENIED |
| mathematical_results_AEGIS_RH_Appendix_20261012.ipynb | Tensor source and RH appendix as separate scientific/formal verification tracks | Exact tensor identity is not an RH kernel proof |
| alphaevolve_quantum_tensor_v1.py | Reuse agents/alphaevolve_quantum_tensor_v1.py already on #773 | Checked source/hash/holdout policies; not an independently proven physical law |

### Typed semantic inquiry and admission contracts

Every research proposal must preserve: source_digest, snapshot_id, domain_cohort, metric_definition_version, dimensions, filters, provenance, evaluator, holdout_policy, execution_receipt, admission_status. Query/metric execution is allowed only when a real, explicitly discovered, read-only metric provider exists. Never hallucinate join keys, invent a deployed Semantic Layer, convert metadata links into measured relations, or execute untrusted notebook cells.

Execution ordering: **discovery → identity reconciliation → semantic request proposal → approved read-only execution → independent evaluation → evidence checkpoint → governed review**. A semantic writer, dbt/Fusion, BSL/Ibis, and each connector stay UNVERIFIED in this scope until independently observed. Unsupported domain science remains EVALUATOR_REQUIRED.

### Governance and limitations

- Reuse existing issue #758 / PR #773 and existing #734/#753/#757 gates. No parallel coordinator, new index/repository/branch/workflow, hosted billing, production writes or automatic merging.
- The uploaded Google Drive originals and local source snapshots have not been overwritten by this repository change.
- Original SQLite files are not mounted in this integration environment. **Live index integrity: NOT_REPLAYED**, pending the read-only audit on the exact operator-owned databases.
- RH results require exact-head Lean kernel evidence and explicit theorem closure. Tensor checks, static source review and metadata lineage do not prove unconditional RH.
