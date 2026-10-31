import { describe, expect, it } from 'vitest'
import type { SHA256Hex } from '../../src/core/types.js'
import {
  DECLARED_PROVIDER_CATALOG_V1, PROVIDER_MESH_SCHEMA_VERSION,
  buildProviderMeshSnapshotV1, selectProviderV1,
  type ProviderObservationV1, type ProviderCapabilityV1,
} from '../../src/sovereignty/provider-mesh.js'

const makeEvidence = (
  provider_id: string, state: ProviderObservationV1['state'],
  observed_capabilities: readonly ProviderCapabilityV1[],
  generation = '42',
): ProviderObservationV1 => ({
  schema_version: PROVIDER_MESH_SCHEMA_VERSION, provider_id, state,
  observed_capabilities, evidence_hash: 'a'.repeat(64) as SHA256Hex,
  observation_generation: generation, authority_effect: 'NONE',
})
const request = {
  required_capabilities: ['REPOSITORY_WORKFLOW'] as const,
  current_generation: '42', max_observation_age_generations: '2',
}

describe('AEGIS cross-cloud executable federation is evidence-only', () => {
  it('recognizes Azure Pipelines, GitLab CI, Codespaces and Vercel Sandbox as descriptors, not grants', () => {
    for (const id of [
      'azure-devops-pipelines', 'gitlab-ci', 'github-codespaces',
      'vercel-sandbox', 'microsoft-azure', 'digitalocean',
    ]) {
      const d = DECLARED_PROVIDER_CATALOG_V1.find(x => x.provider_id === id)
      expect(d).toBeDefined()
      expect(d?.authority_effect).toBe('NONE')
    }
  })
  it('denies Azure pipelines on invitation alone, even when explicitly preferred', async () => {
    const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      makeEvidence('azure-devops-pipelines', 'ACCOUNT_CONFIGURED', []),
    ])
    const r = await selectProviderV1(s, {
      ...request, preferred_provider_order: ['azure-devops-pipelines'],
    })
    expect(r.outcome).toBe('DENIED')
    expect(r.provider_id).toBeNull()
    expect(r.authority_effect).toBe('NONE')
  })
  it('does not promote old GitLab pipeline successes without an observation bound to this request', async () => {
    const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [])
    const r = await selectProviderV1(s, {
      ...request, preferred_provider_order: ['gitlab-ci', 'azure-devops-pipelines'],
    })
    expect(r.outcome).toBe('DENIED')
    expect(r.provider_id).toBeNull()
  })
  it('routes a hypothetical evidence-qualified Azure runner but never grants admission', async () => {
    const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      makeEvidence('azure-devops-pipelines', 'OBSERVED_AVAILABLE',
        ['DURABLE_RUNNER', 'REPOSITORY_WORKFLOW']),
    ])
    const r = await selectProviderV1(s, request)
    expect(r.outcome).toBe('SELECTED')
    expect(r.provider_id).toBe('azure-devops-pipelines')
    expect(r.authority_effect).toBe('NONE')
  })
  it('prefers a fresh GitLab run over unverified Azure even when Azure is first in preference', async () => {
    const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      makeEvidence('azure-devops-pipelines', 'CONFIGURED', []),
      makeEvidence('gitlab-ci', 'OBSERVED_AVAILABLE', ['REPOSITORY_WORKFLOW']),
    ])
    const r = await selectProviderV1(s, {
      ...request, preferred_provider_order: ['azure-devops-pipelines', 'gitlab-ci'],
    })
    expect(r.outcome).toBe('SELECTED')
    expect(r.provider_id).toBe('gitlab-ci')
    expect(r.authority_effect).toBe('NONE')
  })
  it('denies future or stale Azure evidence', async () => {
    for(const gen of ['39', '43']) {
      const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
        makeEvidence('azure-devops-pipelines', 'OBSERVED_AVAILABLE',
          ['REPOSITORY_WORKFLOW'], gen),
      ])
      const r = await selectProviderV1(s, request)
      expect(r.outcome).toBe('DENIED')
      expect(r.provider_id).toBeNull()
    }
  })
  it('rejects numeric generations in provider observations and selection requests', async () => {
    await expect(buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      { ...makeEvidence('azure-devops-pipelines', 'OBSERVED_AVAILABLE', ['REPOSITORY_WORKFLOW']),
        observation_generation: 42 as never },
    ])).rejects.toThrow('observation_generation must be canonical unsigned decimal')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [])
    await expect(selectProviderV1(snapshot, {
      ...request, current_generation: 42 as never,
    })).rejects.toThrow('current_generation must be canonical unsigned decimal')
    await expect(selectProviderV1(snapshot, {
      ...request, max_observation_age_generations: 2 as never,
    })).rejects.toThrow('max_observation_age_generations must be canonical unsigned decimal')
  })

  it('rejects a forged SHA-256-looking object before canonicalization', async () => {
    const fakeHex = { toString: () => 'a'.repeat(64) }
    await expect(buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      { ...makeEvidence('azure-devops-pipelines', 'OBSERVED_AVAILABLE', ['REPOSITORY_WORKFLOW']),
        evidence_hash: fakeHex as never },
    ])).rejects.toThrow('evidence_hash must be lowercase SHA-256 hex')
  })

  it('rejects a string-coercible non-string provider identity', async () => {
    const fakeId = { toString: () => 'azure-devops-pipelines' }
    const invalid = {
      ...DECLARED_PROVIDER_CATALOG_V1[0]!,
      provider_id: fakeId as never,
    }
    await expect(buildProviderMeshSnapshotV1([invalid], []))
      .rejects.toThrow('provider_id is invalid')
  })

  it('never confuses a configured Codespace or stopped Vercel sandbox with usable compute', async () => {
    const s = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      makeEvidence('github-codespaces', 'CONFIGURED', []),
      makeEvidence('vercel-sandbox', 'OBSERVED_UNAVAILABLE', []),
    ])
    const r = await selectProviderV1(s, {
      required_capabilities: ['CONTAINER_RUNTIME'],
      current_generation: '42', max_observation_age_generations: '0',
    })
    expect(r.outcome).toBe('DENIED')
    expect(r.authority_effect).toBe('NONE')
  })
})
