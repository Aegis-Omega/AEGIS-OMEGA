# IDE Runtime Specification — Constitutional Operational Nervous System

## Epistemic Tier: T1 · Gate 11

The IDE is the constitutional operational nervous system of the AEGIS workspace.
It coordinates perception (telemetry), memory (WorkspaceMemoryGraph), replay
(AgentCoordinator frame log), and governance (CapabilityGuard) across all agents.

All panel states derive from replay state. There are no UI components in this layer —
only pure state derivation functions and immutable state objects.

---

## 10 Panel Definitions

Each panel implements `BasePanelState`:
```
{ panel_id, last_updated_sequence, is_replay_reconstructable: true, schema_version: '1.0.0' }
```

### 1. ReplayExplorerPanel (`replay-explorer`)
**Derivation:** AgentCoordinator frame log
Fields: `replay_frame_count`, `oldest_sequence`, `newest_sequence`

### 2. WorkspaceTopologyPanel (`workspace-topology`)
**Derivation:** GovernedWorkspace path list
Fields: `governed_path_count`, `installation_context: InstallationContext`

### 3. AgentHabitatPanel (`agent-habitat`)
**Derivation:** AgentRegistry active manifest list
Fields: `active_agent_count`, `registered_agent_count`, `agent_types: readonly AgentType[]`

### 4. ConstitutionalInvariantDashboard (`constitutional-invariants`)
**Derivation:** Gate pass/fail history
Fields: `checked_invariant_count`, `t0_violations`, `t1_alerts`

### 5. TelemetryCockpit (`telemetry-cockpit`)
**Derivation:** AgentTelemetrySnapshot + environment entropy
Fields: `agent_telemetry: AgentTelemetrySnapshot`, `env_entropy: number`

### 6. CapabilityGovernanceSurface (`capability-governance`)
**Derivation:** CapabilityGuard registration and grant log
Fields: `registered_capability_count`, `active_grant_count`

### 7. ExtensionEcologyView (`extension-ecology`)
**Derivation:** ExtensionRegistry admit/evict history
Fields: `admitted_plugin_count`, `evicted_plugin_count`

### 8. MutationTimelinePanel (`mutation-timeline`)
**Derivation:** MutationLedger append log
Fields: `total_mutations`, `recent_mutation_types: readonly string[]`

### 9. ReplayIntegrityPanel (`replay-integrity`)
**Derivation:** WorkflowEngine frame invariant satisfaction ratio
Fields: `reconstruction_ratio`, `frame_count`

### 10. EnvironmentalDriftMonitor (`environmental-drift`)
**Derivation:** EnvironmentTelemetrySnapshot adaptation pressure metrics
Fields: `drift_rate`, `stability_score`, `pressure_index`

---

## Orchestrator Lifecycle

```
IDEOrchestrator.create(sequence)        // initialize with all 10 panels at sequence
    .update(OrchestratorUpdateParams)   // derive new state from live params
    .getState()                         // read IDERuntimeState
    .panelSequence()                    // read last_updated_sequence
```

`update()` is a pure function: same `OrchestratorUpdateParams` always produces
the same `IDERuntimeState`. No side effects. No Date.now(). No external state.

---

## 6 Agent Telemetry Metrics — T2 Provenance

All 6 metrics are bounded to `[0, 1]` unless otherwise noted. All are pure functions.

| Metric | Formula | T2 Justification |
|--------|---------|-----------------|
| `agent_coordination_stability` | monotonic_frames / (total_frames − 1) | Bounded by construction; 1 = perfect monotonicity |
| `workflow_replay_integrity` | completed_workflows / total_workflows | 1 = all workflows completed; 0 = all aborted |
| `workspace_memory_density` | memory_entries / governed_path_count | Unbounded; 0 if no paths |
| `extension_ecology_entropy` | min(1, admitted_plugins / 16) | 16-plugin normalization; provisional |
| `mutation_chain_depth` | total_mutations / max(1, completed_workflows) | Average; unbounded |
| `orchestration_pressure_index` | (agents_norm + workflows_norm + density_norm) / 3 | Composite [0,1]; T2 threshold at 0.7 |

**T2 Provisional Note:** All 6 metrics are pending P3 empirical validation against
the production governance workload. Threshold values (16 plugins, 8 agents, 16 workflows,
100 density cap) are engineering estimates, not empirically calibrated constants.

---

## Constitutional Invariants for the IDE Layer

- All panel states must have `is_replay_reconstructable: true`
- All panel states must carry `schema_version: IDE_PANEL_SCHEMA_VERSION`
- `buildInitialIDERuntimeState(sequence)` is the only permitted initialization path
- `IDEOrchestrator.update()` must not read from any external source — params only
- No panel state may reference mutable external state
- `panelSequence()` is monotonically non-decreasing across `update()` calls
