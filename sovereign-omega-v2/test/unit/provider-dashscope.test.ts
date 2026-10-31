import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import { observeDashScopeAuthV1 } from '../../src/sovereignty/provider-adapters/dashscope.js'

describe('DashScope provider adapter v1', () => {
  it('keeps an invalid API key non-routable', async () => {
    const observed = await observeDashScopeAuthV1({
      outcome: 'INVALID_API_KEY',
      status_code: 401,
      request_id: '495bb644-4c47-907e-afb4-c54647072246',
    }, '21')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual(['MODEL_INFERENCE'])

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['MODEL_INFERENCE'],
      current_generation: '21',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
  })

  it('permits routing only after successful authenticated evidence', async () => {
    const observed = await observeDashScopeAuthV1({
      outcome: 'AUTHENTICATED',
      status_code: 200,
      request_id: 'request-1',
    }, '21')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['MODEL_INFERENCE'],
      current_generation: '21',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('dashscope')
  })

  it('does not convert a network failure into credential invalidity', async () => {
    const observed = await observeDashScopeAuthV1({
      outcome: 'NETWORK_FAILURE',
      status_code: null,
      request_id: null,
    }, '21')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })
})
