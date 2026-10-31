import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  observeCloudflareAnthropicV1,
  observeCloudflareWorkerV1,
} from '../../src/sovereignty/provider-adapters/cloudflare.js'

describe('Cloudflare provider evidence v1', () => {
  it('keeps a live but source-drifted Worker non-routable', async () => {
    const observed = await observeCloudflareWorkerV1({
      status_code: 200,
      source_semantics_match: false,
    }, '21')

    expect(observed.state).toBe('NETWORK_REACHABLE')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['SERVERLESS_FUNCTION'],
      current_generation: '21',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
  })

  it('permits Worker routing only when health and source semantics are both bound', async () => {
    const observed = await observeCloudflareWorkerV1({
      status_code: 200,
      source_semantics_match: true,
    }, '21')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
  })

  it('records missing Anthropic edge secret without model execution', async () => {
    const observed = await observeCloudflareAnthropicV1({
      status_code: 401,
      secret_configured: false,
      malformed_request_reached_model: false,
    }, '21')

    expect(observed.state).toBe('CREDENTIAL_MISSING')
    expect(observed.observed_capabilities).toEqual(['AGENT_EXECUTION', 'MODEL_INFERENCE'])
  })
})
