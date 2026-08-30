// ============================================================
// Agent Telemetry — 6 constitutional metrics
// EPISTEMIC TIER: T2 provisional (all pending P3 empirical validation)
// No wall-clock time. All computations are pure functions.
// ============================================================

export interface AgentTelemetrySnapshot {
  readonly agent_coordination_stability: number
  readonly workflow_replay_integrity: number
  readonly workspace_memory_density: number
  readonly extension_ecology_entropy: number
  readonly mutation_chain_depth: number
  readonly orchestration_pressure_index: number
}

// [0,1] — ratio of monotonic coordination frames to total
export function computeCoordinationStability(stability: number): number {
  return Math.max(0, Math.min(1, stability))
}

// [0,1] — fraction of completed workflows (status='completed')
export function computeWorkflowReplayIntegrity(
  completedWorkflows: number,
  totalWorkflows: number
): number {
  if (totalWorkflows === 0) return 1
  return completedWorkflows / totalWorkflows
}

// memory entries per governed path (0 if no paths)
export function computeWorkspaceMemoryDensity(
  memoryEntries: number,
  governedPathCount: number
): number {
  if (governedPathCount === 0) return 0
  return memoryEntries / governedPathCount
}

// normalized entropy from active plugin count [0,1]
export function computeExtensionEcologyEntropy(admittedPlugins: number): number {
  return Math.min(1, admittedPlugins / 16)
}

// average agent-initiated mutation chain depth
export function computeMutationChainDepth(
  totalMutations: number,
  completedWorkflows: number
): number {
  if (completedWorkflows === 0) return 0
  return totalMutations / completedWorkflows
}

// composite orchestration pressure [0,1]
export function computeOrchestrationPressureIndex(
  activeAgents: number,
  activeWorkflows: number,
  memoryDensity: number
): number {
  const agentsNorm = Math.min(1, activeAgents / 8)
  const workflowsNorm = Math.min(1, activeWorkflows / 16)
  const densityNorm = Math.min(1, memoryDensity / 100)
  return (agentsNorm + workflowsNorm + densityNorm) / 3
}

export function buildAgentTelemetry(params: {
  coordinationStability: number
  completedWorkflows: number
  totalWorkflows: number
  memoryEntries: number
  governedPathCount: number
  admittedPlugins: number
  totalMutations: number
  activeAgents: number
  activeWorkflows: number
}): AgentTelemetrySnapshot {
  const density = computeWorkspaceMemoryDensity(params.memoryEntries, params.governedPathCount)
  return Object.freeze({
    agent_coordination_stability: computeCoordinationStability(params.coordinationStability),
    workflow_replay_integrity: computeWorkflowReplayIntegrity(params.completedWorkflows, params.totalWorkflows),
    workspace_memory_density: density,
    extension_ecology_entropy: computeExtensionEcologyEntropy(params.admittedPlugins),
    mutation_chain_depth: computeMutationChainDepth(params.totalMutations, params.completedWorkflows),
    orchestration_pressure_index: computeOrchestrationPressureIndex(params.activeAgents, params.activeWorkflows, density),
  })
}
