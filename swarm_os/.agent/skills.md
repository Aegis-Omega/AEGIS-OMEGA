# SOVEREIGN AGI OS — SKILL REGISTRY

Version: 3.2.0 | Updated: 2026-04-10

---

### SKILL: HD_EVALUATION
- **Description**: Compute hallucination delta between claimed and actual cognitive output
- **Formula**: `HD = |claimed − actual|`
- **Range**: 0.00 (verified) → 1.00 (invalid)
- **Strong evidence**: 0.05–0.20
- **Unstable**: >0.50
- **Inputs**: benchmark task responses, ground truth
- **Output**: per-task HD score, mean HD, elected model
- **Entry point**: `benchmark/multi_model_runner.py`
- **Status**: ACTIVE

### SKILL: KG_INGESTION
- **Description**: Ingest structured knowledge triplets into the knowledge graph with Hebbian learning
- **LTP threshold**: activated edge > 0.5 weight
- **LTD threshold**: suppressed edge < 0.3 weight
- **Entry point**: `tools/ingest_knowledge.py` or `tools/knowledge_ingest.py`
- **Output**: nodes added, LTP/LTD counts, calibration r
- **Current KG**: 74 nodes, 260 edges
- **Status**: ACTIVE

### SKILL: ATOMIC_STATE_WRITE
- **Description**: Write state.json or knowledge_graph.json without race conditions
- **Pattern**: write to `.tmp`, then `os.replace()` (atomic)
- **Rule**: NEVER direct-write state files
- **Files governed**: `swarm_os/.forge/state.json`, `swarm_os/.forge/knowledge_graph.json`
- **Status**: ENFORCED

### SKILL: COGNITIVE_EVALUATION
- **Description**: Run DeepMind 10-faculty cognitive self-evaluation
- **Entry point**: `node swarm_os/tools/cognitive-eval.js`
- **Multipliers**: metacognition × executive degrade composite
- **Triggers**: populate when score < 50% per faculty
- **Status**: ACTIVE

### SKILL: STATE_VALIDATION
- **Description**: Validate state.json shape, version, and required fields
- **Entry point**: `node swarm_os/tools/validate-state.js`
- **Expected version**: 3.2.0
- **Required fields**: lifecycle, meta, telemetry, cognition
- **Run**: every session boot
- **Status**: ACTIVE

### SKILL: SWARM_BENCHMARK
- **Description**: Run multi-model HD benchmark against NVIDIA NIM models
- **Entry point**: `benchmark/multi_model_runner.py` (READ ONLY — 657 lines)
- **Env**: `export $(grep -v '^#' free-claude-code/.env | xargs)`
- **Current elected model**: kimi-k2-instruct (mean HD 0.0991)
- **Run location**: WSL `/mnt/d/03_WORK_PROJECTS/system_rebuild/swarm_os`
- **Status**: ACTIVE

### SKILL: PHOTONIC_RESOLUTION
- **Description**: Compute photonic resonance between KG nodes via waveform cross-correlation
- **Formula**: `R = max|crosscorr(|Ψ_u|,|Ψ_v|)| / (||Ψ_u||·||Ψ_v||)`
- **HD_photonic**: `1 - mean(R(u,v))`
- **Current HD_photonic**: 0.015098
- **Entry point**: `tools/swarm/photonic_resolver.py`
- **Status**: ACTIVE

### SKILL: DREAM_STATE
- **Description**: A² dream loop for KG pattern recognition and ego update cycles
- **Entry point**: `tools/swarm/dream_state.py`
- **Current**: 1017 cycles logged, best HD 0.0203
- **Status**: ACTIVE
