// ============================================================
// SOVEREIGN OMEGA — Mutation Governance Registry
// EPISTEMIC TIER: T0
// ChatGPT synthesis v2.1-Ω — replaces mutation-registry.ts
// ============================================================

import type { CapacityDeclaration, SHA256Hex } from '../core/types.js'
import { deepFreeze } from '../core/immutable.js'

export interface MigrationContract {
  migration_id: string; from_schema_id: string; from_version: string;
  to_schema_id: string; to_version: string;
  transform: (p: unknown) => unknown;
  transform_source_hash: SHA256Hex; delta_k: number;
}
export interface RollbackContract {
  migration_id: string; rollback_supported: boolean;
  inverse_transform?: (p: unknown) => unknown;
}

export class MutationGovernanceRegistry {
  private migrations = new Map<string, MigrationContract>()
  private rollbacks = new Map<string, RollbackContract>()
  private capacities = new Map<string, CapacityDeclaration>()
  private appliedMigrations = new Map<string, Set<string>>()
  private sealed = false

  registerCapacity(d: CapacityDeclaration): void {
    if (this.sealed) throw new Error('REGISTRY_SEALED')
    if (d.k_bound < 0 || !Number.isInteger(d.k_bound)) throw new Error('INVALID_K_BOUND')
    this.capacities.set(d.component_id, deepFreeze({ ...d }))
  }

  register(m: MigrationContract, r: RollbackContract): void {
    if (this.sealed) throw new Error('REGISTRY_SEALED')
    if (m.delta_k < 0) throw new Error('NEGATIVE_DELTA_K_FORBIDDEN')
    this.migrations.set(m.migration_id, deepFreeze({ ...m }))
    this.rollbacks.set(m.migration_id, deepFreeze({ ...r }))
  }

  seal(): void { this.sealed = true }

  validateKBound(componentId: string, delta: number): void {
    const cap = this.capacities.get(componentId)
    if (!cap) throw new Error(`NO_CAPACITY_FOR_${componentId}`)
    const applied = this.appliedMigrations.get(componentId)
    let currentK = 0
    if (applied) for (const id of applied) {
      const m = this.migrations.get(id)
      if (m) currentK += m.delta_k
    }
    if (currentK + delta > cap.k_bound) throw new Error(`K_BOUND_EXCEEDED_${componentId}`)
  }

  markApplied(componentId: string, migrationId: string): void {
    if (!this.appliedMigrations.has(componentId)) this.appliedMigrations.set(componentId, new Set())
    this.appliedMigrations.get(componentId)!.add(migrationId)
  }

  findPath(fromId: string, fromVer: string, toId: string, toVer: string): MigrationContract[] | null {
    if (fromId === toId && fromVer === toVer) return []
    const result: MigrationContract[] = []
    let cur = { id: fromId, ver: fromVer }
    for (let i = 0; i < 10; i++) {
      const next = [...this.migrations.values()].find(m =>
        m.from_schema_id === cur.id && m.from_version === cur.ver)
      if (!next) return null
      result.push(next)
      cur = { id: next.to_schema_id, ver: next.to_version }
      if (cur.id === toId && cur.ver === toVer) return result
    }
    return null
  }
}

export const mutationGovernanceRegistry = new MutationGovernanceRegistry()
