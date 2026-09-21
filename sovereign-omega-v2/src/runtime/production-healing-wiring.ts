// ============================================================
// SOVEREIGN OMEGA — Production Self-Healing Wiring V1
// EPISTEMIC TIER: T2 composition boundary
//
// This module wires existing recovery/governance primitives together.
// It grants no mutation authority and performs no durable repair apply.
// ============================================================

import type {
  CapacityDeclaration,
  MutationOperatorMetadata,
} from '../core/types.js'
import type { AdaptiveLineageEntry } from '../frame/adaptive-lineage.js'
import {
  GraceSupervisor,
  type GraceEvent,
} from '../memory/grace-supervisor.js'
import {
  CapacityDeclarationRegistry,
  MutationOperatorRegistry,
} from '../verifier/registry.js'
import {
  AgenticSelfHealingRuntime,
  type HealingCycleReceipt,
  type HealingVerifier,
} from './agentic-self-healing.js'
import {
  createGraceHealingPlanner,
  createGraceRetentionRecoveryAdapter,
  healingObservationFromGrace,
} from './grace-healing-adapter.js'
import {
  createHealingAuthorityPreflight,
} from './healing-authority-adapter.js'

export const PRODUCTION_HEALING_WIRING_SCHEMA_VERSION = '1.0.0' as const

export interface ProductionGraceHealingOptions {
  readonly component_id: string
  readonly verifiers: readonly HealingVerifier[]
}

/**
 * Stateful production composition root for the existing Grace recovery path.
 *
 * The runtime is retained across calls so receipt linkage, monotonic sequence
 * checks and the per-incident attempt budget cannot be reset by reconstruction.
 * Calls are serialized to prevent two observations from branching from the same
 * terminal receipt hash.
 */
export class ProductionGraceHealingService {
  private runtime = AgenticSelfHealingRuntime.create()
  private queue: Promise<void> = Promise.resolve()

  private constructor(private readonly options: ProductionGraceHealingOptions) {
    if (!options.component_id) throw new Error('component_id required')
    if (options.verifiers.length === 0) throw new Error('at least one production verifier required')
  }

  static create(options: ProductionGraceHealingOptions): ProductionGraceHealingService {
    return new ProductionGraceHealingService(options)
  }

  get receiptCount(): number {
    return this.runtime.receiptCount
  }

  async handleGraceFault(
    supervisor: GraceSupervisor,
    event: GraceEvent,
  ): Promise<{ readonly receipt: HealingCycleReceipt }> {
    let resolveResult!: (value: { readonly receipt: HealingCycleReceipt }) => void
    let rejectResult!: (reason?: unknown) => void
    const result = new Promise<{ readonly receipt: HealingCycleReceipt }>((resolve, reject) => {
      resolveResult = resolve
      rejectResult = reject
    })

    const operation = this.queue.then(async () => {
      try {
        const observation = await healingObservationFromGrace(
          supervisor,
          event,
          this.options.component_id,
        )
        const cycle = await this.runtime.runCycle(observation, {
          planner: createGraceHealingPlanner(),
          volatile_recovery: createGraceRetentionRecoveryAdapter(supervisor),
          verifiers: this.options.verifiers,
        })
        this.runtime = cycle.runtime
        resolveResult({ receipt: cycle.receipt })
      } catch (error) {
        rejectResult(error)
      }
    })

    this.queue = operation.then(() => undefined, () => undefined)
    return await result
  }
}

export interface ProductionHealingAuthorityBootstrap {
  readonly operators: readonly MutationOperatorMetadata[]
  readonly capacities: readonly CapacityDeclaration[]
  readonly lineageEntries: () => readonly AdaptiveLineageEntry[]
}

export interface ProductionHealingAuthority {
  readonly runtime: AgenticSelfHealingRuntime
  readonly operatorRegistry: MutationOperatorRegistry
  readonly capacityRegistry: CapacityDeclarationRegistry
  readonly preflight: ReturnType<typeof createHealingAuthorityPreflight>
}

/**
 * Bootstrap the authority *eligibility* adapter from explicit governed inputs.
 *
 * There are deliberately no default operators or capacities. The registry is
 * sealed only after every supplied declaration validates. This function does
 * not approve or apply a mutation; a verified durable proposal still terminates
 * at AWAITING_AUTHORITY in AgenticSelfHealingRuntime.
 */
export async function bootstrapProductionHealingAuthority(
  input: ProductionHealingAuthorityBootstrap,
): Promise<ProductionHealingAuthority> {
  if (input.operators.length === 0) {
    throw new Error('at least one governed mutation operator required')
  }
  if (input.capacities.length === 0) {
    throw new Error('at least one governed capacity declaration required')
  }

  const operatorRegistry = new MutationOperatorRegistry()
  for (const operator of input.operators) operatorRegistry.register(operator)

  const capacityRegistry = new CapacityDeclarationRegistry(operatorRegistry)
  for (const capacity of input.capacities) await capacityRegistry.register(capacity)

  operatorRegistry.seal()

  const preflight = createHealingAuthorityPreflight({
    lineageEntries: input.lineageEntries,
    operatorRegistry,
    capacityRegistry,
  })

  return Object.freeze({
    runtime: AgenticSelfHealingRuntime.create(),
    operatorRegistry,
    capacityRegistry,
    preflight,
  })
}
