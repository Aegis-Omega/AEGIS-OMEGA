// ============================================================
// SOVEREIGN OMEGA — Gate Migration Registry
// EPISTEMIC TIER: T0
// Schema evolution for gate decision payloads.
// All migrations must be registered before runtime begins.
// Sealed after first gate evaluation — no runtime injection.
// ============================================================

import type { GateDecisionPayload } from '../types.js'

export interface GateMigration {
  readonly from_version: string
  readonly to_version: string
  readonly migrate: (payload: unknown) => GateDecisionPayload
}

const migrations: GateMigration[] = []
let sealed = false

export function registerGateMigration(m: GateMigration): void {
  if (sealed) throw new Error('Gate migration registry is sealed.')
  migrations.push(Object.freeze(m))
}

export function sealGateMigrations(): void { sealed = true }

export function migrateGatePayload(
  payload: unknown,
  fromVersion: string,
  toVersion: string
): GateDecisionPayload | null {
  const m = migrations.find(
    x => x.from_version === fromVersion && x.to_version === toVersion
  )
  return m ? m.migrate(payload) : null
}
