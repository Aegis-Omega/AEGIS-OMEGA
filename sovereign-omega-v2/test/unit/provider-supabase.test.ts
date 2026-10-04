import { describe, expect, it } from 'vitest'
import { observeSupabaseRuntimeV1 } from '../../src/sovereignty/provider-adapters/supabase-edge.js'

describe('Supabase provider adapter v1', () => {
  it('requires database, edge runtime, and outbound egress before availability', async () => {
    const observed = await observeSupabaseRuntimeV1({
      project_status: 'ACTIVE_HEALTHY',
      database_health_ok: true,
      edge_function_reachable: true,
      outbound_http_observed: true,
    }, '20')

    expect(observed.provider_id).toBe('supabase-edge')
    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([
      'SERVERLESS_FUNCTION',
      'DATABASE',
      'HTTP_EGRESS',
    ])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('does not promote partial health evidence', async () => {
    const observed = await observeSupabaseRuntimeV1({
      project_status: 'ACTIVE_HEALTHY',
      database_health_ok: true,
      edge_function_reachable: false,
      outbound_http_observed: true,
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })

  it('marks an inactive project unavailable', async () => {
    const observed = await observeSupabaseRuntimeV1({
      project_status: 'INACTIVE',
      database_health_ok: false,
      edge_function_reachable: false,
      outbound_http_observed: false,
    }, '20')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
  })
})
