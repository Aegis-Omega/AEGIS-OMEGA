// ============================================================
// SOVEREIGN OMEGA — Verifier Registry & Mutation Operator Registry
// EPISTEMIC TIER: T0
// PRIMITIVE 5: Hard Trust Partitioning
// Section 5.4: Capacity Constraint — K Specification
// ============================================================

import type {
  CapacityDeclaration, MutationOperatorMetadata,
  CalibrationDomain
} from '../core/types.js'
import { CalibrationDomain as CD, VerifierClass as VC } from '../core/types.js'
import type { Verifier } from './types.js'

class VerifierRegistry {
  private readonly verifiers = new Map<string, Verifier>()

  register(verifier: Verifier): void {
    const { verifier_id, verifier_class, is_deterministic, max_latency_ms } = verifier.definition
    if (!verifier_id) throw new RegistrationError('verifier_id required')
    if (is_deterministic === false && (
      verifier_class === VC.V1_DETERMINISTIC || verifier_class === VC.V2_SCHEMA
    )) throw new RegistrationError('V1/V2 verifiers must be deterministic')
    if (max_latency_ms > 30_000) throw new RegistrationError(`Verifier ${verifier_id} exceeds 30s latency ceiling`)
    this.verifiers.set(verifier_id, verifier)
  }

  get(id: string): Verifier | undefined { return this.verifiers.get(id) }

  getCalibrationEligible(): readonly Verifier[] {
    return [...this.verifiers.values()].filter(v =>
      v.definition.trust_class === CD.GROUND_TRUTH ||
      v.definition.trust_class === CD.RETRIEVAL_ASSISTED
    )
  }

  getCalibrationWeight(trust_class: CalibrationDomain): number {
    if (trust_class === CD.GROUND_TRUTH) return 1.0
    if (trust_class === CD.RETRIEVAL_ASSISTED) return 0.5
    return 0.0
  }
}

export const verifierRegistry = new VerifierRegistry()

class MutationOperatorRegistry {
  private readonly operators = new Map<string, MutationOperatorMetadata>()
  private sealed = false

  register(op: MutationOperatorMetadata): void {
    if (this.sealed) throw new RegistrationError('MutationOperatorRegistry is sealed. Dynamic injection rejected.')
    if (!op.operator_id) throw new RegistrationError('operator_id required')
    if (op.max_branching_factor <= 0) throw new RegistrationError('max_branching_factor must be positive')
    this.operators.set(op.operator_id, Object.freeze(op))
  }

  seal(): void { this.sealed = true }

  validate(operatorIds: readonly string[]): void {
    for (const id of operatorIds) {
      if (!this.operators.has(id)) throw new RegistrationError(`Unknown mutation operator: ${id}`)
    }
  }

  computeKBound(operatorIds: readonly string[]): number {
    this.validate(operatorIds)
    return operatorIds.reduce((product, id) => product * (this.operators.get(id)!.max_branching_factor), 1)
  }
}

export const mutationOperatorRegistry = new MutationOperatorRegistry()

class CapacityDeclarationRegistry {
  private readonly declarations = new Map<string, CapacityDeclaration>()

  async register(declaration: CapacityDeclaration): Promise<void> {
    mutationOperatorRegistry.validate(declaration.mutation_operators)
    if (!Number.isFinite(declaration.k_bound) || declaration.k_bound < 0)
      throw new RegistrationError(`k_bound must be finite non-negative for ${declaration.component_id}`)

    const computedK = mutationOperatorRegistry.computeKBound(declaration.mutation_operators)
    if (computedK > declaration.k_bound)
      throw new RegistrationError(`Computed K (${computedK}) exceeds k_bound (${declaration.k_bound})`)

    this.declarations.set(declaration.component_id, Object.freeze(declaration))
  }

  get(componentId: string): CapacityDeclaration | undefined { return this.declarations.get(componentId) }

  checkKBound(componentId: string, deltaK: number): boolean {
    const decl = this.declarations.get(componentId)
    if (!decl) throw new RegistrationError(`Component ${componentId} not registered`)
    return deltaK <= decl.k_bound
  }
}

export const capacityRegistry = new CapacityDeclarationRegistry()

export class RegistrationError extends Error {
  constructor(message: string) { super(message); this.name = 'RegistrationError' }
}
