// ============================================================
// Sandbox Boundary — plugin isolation enforcement
// RULE: Plugins may not mutate constitutional primitives directly.
// RULE: Plugin entropy contribution must remain measurable.
// EPISTEMIC TIER: T0 (isolation is constitutionally required)
// ============================================================

import { deepFreeze } from '../../core/immutable'
import type { SandboxBoundary, MutationReceipt } from '../types'
import { SandboxViolationError } from '../types'

export function createSandbox(params: {
  plugin_id: string
  allowed_capability_ids: readonly string[]
  allowed_paths: readonly string[]
  entropy_budget_fixed: number
  max_mutation_count: number
}): SandboxBoundary {
  return deepFreeze({
    sandbox_id: `sandbox_${params.plugin_id}`,
    plugin_id: params.plugin_id,
    allowed_capability_ids: deepFreeze([...params.allowed_capability_ids]),
    allowed_paths: deepFreeze([...params.allowed_paths]),
    max_mutation_count: params.max_mutation_count,
    current_mutation_count: 0,
    entropy_used_fixed: 0,
    entropy_budget_fixed: params.entropy_budget_fixed,
    is_isolated: true,
  })
}

export function checkSandboxAllows(
  sandbox: SandboxBoundary,
  capabilityId: string,
  targetPath: string
): void {
  if (!sandbox.is_isolated) {
    throw new SandboxViolationError(
      `Sandbox for plugin ${sandbox.plugin_id} is not isolated`
    )
  }
  if (!sandbox.allowed_capability_ids.includes(capabilityId)) {
    throw new SandboxViolationError(
      `Plugin ${sandbox.plugin_id} attempted to use capability ${capabilityId} outside sandbox allowlist`
    )
  }
  if (!sandbox.allowed_paths.some(p => targetPath.startsWith(p))) {
    throw new SandboxViolationError(
      `Plugin ${sandbox.plugin_id} attempted to access path ${targetPath} outside sandbox boundary`
    )
  }
  if (sandbox.current_mutation_count >= sandbox.max_mutation_count) {
    throw new SandboxViolationError(
      `Plugin ${sandbox.plugin_id} exceeded mutation budget (${sandbox.max_mutation_count})`
    )
  }
  if (sandbox.entropy_used_fixed >= sandbox.entropy_budget_fixed) {
    throw new SandboxViolationError(
      `Plugin ${sandbox.plugin_id} exceeded entropy budget`
    )
  }
}

export function recordMutation(
  sandbox: SandboxBoundary,
  receipt: MutationReceipt
): SandboxBoundary {
  if (receipt.plugin_id !== sandbox.plugin_id) {
    throw new SandboxViolationError(
      `Receipt plugin_id ${receipt.plugin_id} does not match sandbox plugin_id ${sandbox.plugin_id}`
    )
  }
  return deepFreeze({
    ...sandbox,
    current_mutation_count: sandbox.current_mutation_count + 1,
    entropy_used_fixed: sandbox.entropy_used_fixed + receipt.entropy_contribution_fixed,
  })
}

export function computeSandboxEntropyRatio(sandbox: SandboxBoundary): number {
  if (sandbox.entropy_budget_fixed === 0) return 0
  return sandbox.entropy_used_fixed / sandbox.entropy_budget_fixed
}
