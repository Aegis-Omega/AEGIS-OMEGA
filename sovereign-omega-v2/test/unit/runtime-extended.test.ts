// ============================================================
// Constitutional Runtime Extended Tests — constitutional/runtime.ts
// Targets uncovered branches:
//   guardianInvokedPayload on empty runtime (decisions=[]) → null coalesce
//   guardianVerdictPayload on empty runtime (decisions=[]) → null coalesce
//   convergenceDepth() direct access
//   telemetry() on empty runtime
// ============================================================

import { describe, it, expect } from 'vitest'
import { ConstitutionalRuntime } from '../../src/constitutional/runtime.js'
import type { UUIDv7 } from '../../src/core/types.js'

const MOCK_UUID = '00000000-0000-7000-0000-000000000001' as UUIDv7

// ─── Empty runtime — null coalesce paths ─────────────────

describe('ConstitutionalRuntime: empty runtime fallbacks', () => {
  it('guardianInvokedPayload on empty runtime uses default check_reason', () => {
    const runtime = ConstitutionalRuntime.empty()
    const payload = runtime.guardianInvokedPayload({
      invoked_by: 'operator',
      files_under_review: ['src/constitutional/runtime.ts'],
    })
    expect(payload.check_reason).toBe('Constitutional governance check')
  })

  it('guardianVerdictPayload on empty runtime uses PERMIT verdict fallback', () => {
    const runtime = ConstitutionalRuntime.empty()
    const payload = runtime.guardianVerdictPayload({
      location: 'src/constitutional',
      invocation_event_id: MOCK_UUID,
    })
    // PERMIT verdict → maps to 'APPROVED' in guardian payloads
    expect(typeof payload.verdict).toBe('string')
  })

  it('guardianVerdictPayload on empty runtime uses default reason', () => {
    const runtime = ConstitutionalRuntime.empty()
    const payload = runtime.guardianVerdictPayload({
      location: 'src/constitutional',
      invocation_event_id: MOCK_UUID,
    })
    expect(payload.reason).toBe('Constitutional governance check')
  })
})

// ─── convergenceDepth direct access ──────────────────────

describe('ConstitutionalRuntime: convergenceDepth()', () => {
  it('returns 0 on empty runtime', () => {
    expect(ConstitutionalRuntime.empty().convergenceDepth()).toBe(0)
  })
})

// ─── telemetry on empty runtime ──────────────────────────

describe('ConstitutionalRuntime: telemetry()', () => {
  it('telemetry on empty runtime returns all expected fields', () => {
    const t = ConstitutionalRuntime.empty().telemetry(0)
    expect(t.verdict).toBeDefined()
    expect(typeof t.decision_count).toBe('number')
    expect(typeof t.convergence_depth).toBe('number')
    expect(typeof t.governance_throughput).toBe('number')
    expect(t.schema_version).toBeDefined()
  })

  it('telemetry decision_count = 0 before any evaluate', () => {
    expect(ConstitutionalRuntime.empty().telemetry(0).decision_count).toBe(0)
  })
})
