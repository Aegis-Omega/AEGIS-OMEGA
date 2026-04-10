# SOVEREIGN AGI OS — WORKFLOW REGISTRY

Version: 3.2.0 | Updated: 2026-04-10

---

### WORKFLOW: SESSION_BOOT
- **Trigger**: Start of every session
- **Steps**:
  1. `node swarm_os/tools/validate-state.js` → must PASS
  2. Read CONTEXT.md
  3. Read .agent/rules.md
  4. Run `node swarm_os/tools/cognitive-eval.js`
  5. Identify highest-HD component
  6. Begin execution loop
- **Gate**: validator must return `success: true`
- **Status**: ENFORCED

### WORKFLOW: EXECUTION_LOOP
- **Trigger**: After SESSION_BOOT
- **Steps**:
  1. Identify weakest component (Priority = HD×0.4 + Risk×0.3 + Importance×0.2 + Centrality×0.1)
  2. Fix highest-priority item only
  3. Stress test the fix
  4. Verify with validate-state.js or cognitive-eval.js
  5. Log event to `.forge/docs/audit.jsonl`
  6. Repeat
- **Law**: Do not widen scope mid-mission
- **Status**: ACTIVE

### WORKFLOW: SWARM_BENCHMARK_RUN
- **Trigger**: Execution target #2 per HANDOFF_V8.md
- **Pre-condition**: validate-state.js PASS
- **Steps**:
  1. `cd /mnt/d/03_WORK_PROJECTS/system_rebuild/swarm_os`
  2. `export $(grep -v '^#' free-claude-code/.env | xargs)`
  3. `python benchmark/multi_model_runner.py`
  4. Record elected model, mean HD, per-task scores
  5. Atomic write results to state.json benchmark section
  6. Log BENCHMARK_COMPLETE to audit.jsonl
- **Environment**: WSL only (no torch on Cowork VM)
- **File rule**: multi_model_runner.py is READ ONLY
- **Status**: ACTIVE

### WORKFLOW: KG_GROWTH
- **Trigger**: When KG node count < target or HD > 0.10
- **Steps**:
  1. Prepare knowledge triplets (domain, subject, relation, object)
  2. Run `tools/ingest_knowledge.py --auto`
  3. Record LTP/LTD counts and calibration r
  4. Atomic write updated KG to `.forge/knowledge_graph.json`
  5. Update state.json graph_health section
  6. Verify HD improvement
- **Environment**: WSL only
- **Status**: ACTIVE

### WORKFLOW: SESSION_HANDOFF
- **Trigger**: End of every session
- **Steps**:
  1. Update `HANDOFF_V8.md` with current metrics
  2. Update `CONTEXT.md` if bio metrics changed
  3. `gsutil cp .forge/state.json gs://lifequestplatinum_cloudbuild/sovereign-vault/`
  4. `gsutil cp .forge/knowledge_graph.json gs://lifequestplatinum_cloudbuild/sovereign-vault/`
  5. `node swarm_os/tools/validate-state.js`
  6. Note HD and weakest component for next session
- **Status**: ENFORCED

### WORKFLOW: CLOUD_REDEPLOY
- **Trigger**: Execution target #3 per HANDOFF_V8.md
- **Pre-condition**: `.gcloudignore` must exist
- **Steps**:
  1. `copy docs\outputs\gcloudignore .gcloudignore`
  2. Run `docs\outputs\DEPLOY_COMMANDS.ps1`
  3. Verify Cloud Run URL is live
- **Environment**: Windows PowerShell
- **Status**: ACTIVE

### WORKFLOW: ATOMIC_STATE_UPDATE
- **Trigger**: Any time state.json or knowledge_graph.json must be modified
- **Steps**:
  1. Read current file into memory
  2. Apply changes in-memory
  3. Write to `.tmp` file
  4. `os.replace(tmp, target)` — atomic
  5. Verify file is valid JSON
- **Rule**: NEVER skip atomic pattern
- **Status**: ENFORCED
