import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
  type ProviderCapabilityV1,
  type ProviderObservationStateV1,
  type ProviderObservationV1,
} from '../../src/sovereignty/provider-mesh.js'

const hash = (digit: string): SHA256Hex => digit.repeat(64) as SHA256Hex

function observation(
  provider_id: string,
  state: ProviderObservationStateV1,
  observed_capabilities: readonly ProviderCapabilityV1[],
  observation_generation = '10',
  evidenceDigit = 'a',
): ProviderObservationV1 {
  return {
    schema_version: PROVIDER_MESH_SCHEMA_VERSION,
    provider_id,
    state,
    observed_capabilities,
    evidence_hash: hash(evidenceDigit),
    observation_generation,
    authority_effect: 'NONE',
  }
}

describe('sovereign provider mesh v1', () => {
  it('keeps all declared providers authority-neutral', () => {
    expect(DECLARED_PROVIDER_CATALOG_V1.length).toBeGreaterThan(0)
    for (const provider of DECLARED_PROVIDER_CATALOG_V1) {
      expect(provider.authority_effect).toBe('NONE')
    }
  })

  it('fails closed when providers are declared but not observed available', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      current_generation: '10',
      max_observation_age_generations: '2',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
    expect(receipt.authority_effect).toBe('NONE')
  })

  it('does not treat CONFIGURED as availability evidence', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('github-actions', 'CONFIGURED', ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW']),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      preferred_provider_order: ['github-actions'],
      current_generation: '10',
      max_observation_age_generations: '2',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('selects an observed provider only when the required capability was observed', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('nebius-ai-cloud', 'OBSERVED_AVAILABLE', ['GPU_COMPUTE'], '10', 'b'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['GPU_COMPUTE'],
      current_generation: '10',
      max_observation_age_generations: '0',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('nebius-ai-cloud')
    expect(receipt.evidence_hashes).toEqual([hash('b')])
    expect(receipt.denial_codes).toEqual([])
    expect(receipt.authority_effect).toBe('NONE')
  })

  it('uses explicit preference only among evidence-qualified providers', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('github-actions', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW'], '10', 'c'),
      observation('google-cloud', 'OBSERVED_AVAILABLE', ['CONTAINER_RUNTIME', 'DURABLE_RUNNER'], '10', 'd'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      preferred_provider_order: ['google-cloud', 'github-actions'],
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('google-cloud')
    expect(receipt.evidence_hashes).toEqual([hash('d')])
  })

  it('cannot use preference to bypass missing observed capability evidence', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('openai', 'OBSERVED_AVAILABLE', ['MODEL_INFERENCE'], '10', 'e'),
      observation('anthropic', 'OBSERVED_AVAILABLE', ['AGENT_EXECUTION', 'MODEL_INFERENCE'], '10', 'f'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['AGENT_EXECUTION'],
      preferred_provider_order: ['openai', 'anthropic'],
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('anthropic')
    expect(receipt.evidence_hashes).toEqual([hash('f')])
  })

  it('rejects stale observations', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('google-cloud', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '5'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      current_generation: '10',
      max_observation_age_generations: '4',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.denial_codes).toContain('OBSERVATION_STALE')
  })

  it('rejects observations from a future generation', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('google-cloud', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '11'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      current_generation: '10',
      max_observation_age_generations: '10',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.denial_codes).toContain('OBSERVATION_FROM_FUTURE')
  })

  it('rejects observed capabilities that the provider descriptor did not declare', async () => {
    await expect(buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('openai', 'OBSERVED_AVAILABLE', ['GPU_COMPUTE']),
    ])).rejects.toThrow('observed capability is not declared for openai: GPU_COMPUTE')
  })

  it('honours an explicit provider allow-list', async () => {
    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      observation('github-actions', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '10', '1'),
      observation('google-cloud', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '10', '2'),
    ])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      allowed_providers: ['github-actions'],
      preferred_provider_order: ['google-cloud', 'github-actions'],
      current_generation: '10',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('github-actions')
  })

  it('is deterministic under descriptor and observation input reordering', async () => {
    const observations = [
      observation('github-actions', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '10', '3'),
      observation('google-cloud', 'OBSERVED_AVAILABLE', ['DURABLE_RUNNER'], '10', '4'),
    ]
    const left = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, observations)
    const right = await buildProviderMeshSnapshotV1(
      [...DECLARED_PROVIDER_CATALOG_V1].reverse(),
      [...observations].reverse(),
    )

    expect(left.snapshot_root).toBe(right.snapshot_root)

    const request = {
      required_capabilities: ['DURABLE_RUNNER'] as const,
      current_generation: '10',
      max_observation_age_generations: '1',
    }
    const leftDecision = await selectProviderV1(left, request)
    const rightDecision = await selectProviderV1(right, request)
    expect(leftDecision.provider_id).toBe(rightDecision.provider_id)
    expect(leftDecision.receipt_root).toBe(rightDecision.receipt_root)
  })
})
