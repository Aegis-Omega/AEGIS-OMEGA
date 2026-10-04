import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import { observeRailwayConnectorV1 } from '../../src/sovereignty/provider-adapters/railway.js'
import { observeWolframKernelV1 } from '../../src/sovereignty/provider-adapters/wolfram.js'

describe('connected provider resource adapters v1', () => {
  it('keeps expired Railway trial non-routable even when capabilities are declared', async () => {
    const railway = await observeRailwayConnectorV1({
      outcome: 'TRIAL_EXPIRED',
      project_present: true,
      service_count: 0,
      deployment_count: 0,
    }, '20')

    expect(railway.state).toBe('BILLING_BLOCKED')
    expect(railway.observed_capabilities).toEqual(['CONTAINER_RUNTIME', 'DURABLE_RUNNER'])

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [railway])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DURABLE_RUNNER'],
      current_generation: '20',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('routes symbolic compute to Wolfram only after successful kernel evidence', async () => {
    const wolfram = await observeWolframKernelV1({
      outcome: 'KERNEL_SUCCESS',
      verifier_root: '888f5cd67e3a9d7eaf1145e8e07aa77328f840be20dafe454fd8b3b325a08bb5',
      computation_kind: 'provider-selection-cross-check',
    }, '20')

    expect(wolfram.state).toBe('OBSERVED_AVAILABLE')
    expect(wolfram.observed_capabilities).toEqual(['SYMBOLIC_COMPUTE'])

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [wolfram])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['SYMBOLIC_COMPUTE'],
      current_generation: '20',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('wolfram')
    expect(receipt.evidence_hashes).toEqual([
      '888f5cd67e3a9d7eaf1145e8e07aa77328f840be20dafe454fd8b3b325a08bb5',
    ])
  })

  it('does not promote a failed Wolfram computation', async () => {
    const wolfram = await observeWolframKernelV1({
      outcome: 'KERNEL_FAILURE',
      verifier_root: null,
      computation_kind: 'provider-selection-cross-check',
    }, '20')

    expect(wolfram.state).toBe('UNKNOWN')
    expect(wolfram.observed_capabilities).toEqual([])
  })
})
