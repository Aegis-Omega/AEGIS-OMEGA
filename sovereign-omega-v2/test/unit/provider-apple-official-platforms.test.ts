import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  observeAppleOfficialPlatformV1,
} from '../../src/sovereignty/provider-adapters/apple-official-platforms.js'

describe('Apple official platform evidence v1', () => {
  it('binds Apple Intelligence developer documentation read evidence', async () => {
    const observed = await observeAppleOfficialPlatformV1({
      provider_id: 'apple-developer-intelligence',
      official_url: 'https://developer.apple.com/apple-intelligence/',
      source_class: 'OFFICIAL_DEVELOPER_DOCS',
      outcome: 'READ_SUCCESS',
    }, '30')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['APPLE_INTELLIGENCE_DEVELOPER_READ'])
    expect(observed.evidence_hash).toBe('2010dbf590170c87431428a77f88d0bed552451f0d6d7f90579bb2fd19946e9a')
    expect(observed.authority_effect).toBe('NONE')
  })

  it('binds Apple business AI documentation read evidence', async () => {
    const observed = await observeAppleOfficialPlatformV1({
      provider_id: 'apple-business-ai',
      official_url: 'https://developer.apple.com/business/ai/',
      source_class: 'OFFICIAL_BUSINESS_DOCS',
      outcome: 'READ_SUCCESS',
    }, '30')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['APPLE_BUSINESS_DEPLOYMENT_READ'])
    expect(observed.evidence_hash).toBe('ffed888d87ae9e5f78299035b0a8f4b0b07532e4b49f085df48232bdfd844d52')
  })

  it('rejects caller-swapped Apple official URLs', async () => {
    await expect(observeAppleOfficialPlatformV1({
      provider_id: 'apple-developer-intelligence',
      official_url: 'https://developer.apple.com/business/ai/',
      source_class: 'OFFICIAL_DEVELOPER_DOCS',
      outcome: 'READ_SUCCESS',
    }, '30')).rejects.toThrow('official_url does not match declared Apple source')
  })

  it('routes Apple developer evidence without granting authority', async () => {
    const developer = await observeAppleOfficialPlatformV1({
      provider_id: 'apple-developer-intelligence',
      official_url: 'https://developer.apple.com/apple-intelligence/',
      source_class: 'OFFICIAL_DEVELOPER_DOCS',
      outcome: 'READ_SUCCESS',
    }, '30')

    const snapshot = await buildProviderMeshSnapshotV1(
      DECLARED_PROVIDER_CATALOG_V1,
      [developer],
    )
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['APPLE_INTELLIGENCE_DEVELOPER_READ'],
      allowed_providers: ['apple-developer-intelligence'],
      current_generation: '30',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('apple-developer-intelligence')
    expect(receipt.authority_effect).toBe('NONE')
  })
})
