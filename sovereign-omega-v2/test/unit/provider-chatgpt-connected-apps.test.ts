import { describe, expect, it } from 'vitest'
import {
  DECLARED_PROVIDER_CATALOG_V1,
  buildProviderMeshSnapshotV1,
  selectProviderV1,
} from '../../src/sovereignty/provider-mesh.js'
import {
  observeChatGptConnectedAppV1,
  type ChatGptConnectedAppIdV1,
} from '../../src/sovereignty/provider-adapters/chatgpt-connected-apps.js'

describe('ChatGPT connected-app provider observations v1', () => {
  it('promotes a successful Google Drive read probe to document retrieval availability', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-drive',
      operation: 'search',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')

    expect(observed.provider_id).toBe('chatgpt-google-drive')
    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['DOCUMENT_RETRIEVAL'])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps installed-but-unprobed Gmail non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-gmail',
      operation: 'plugin_directory_state',
      outcome: 'CONNECTED_NOT_PROBED',
      result_count: 0,
    }, '20')

    expect(observed.state).toBe('ACCOUNT_CONFIGURED')
    expect(observed.observed_capabilities).toEqual([])
  })

  it('keeps a generic connector read failure epistemically unknown', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-calendar',
      operation: 'list_calendars',
      outcome: 'READ_FAILURE',
      result_count: 0,
    }, '20')

    expect(observed.state).toBe('UNKNOWN')
    expect(observed.observed_capabilities).toEqual([])
  })


  it.each([
    ['chatgpt-slack', 'slack_read_user_profile', 'COLLABORATION_READ'],
    ['chatgpt-notion', 'fetch_self', 'KNOWLEDGE_BASE_READ'],
    ['chatgpt-linear', 'list_documents', 'WORK_TRACKING_READ'],
    ['chatgpt-hubspot', 'discover_hubspot_schema', 'CRM_READ'],
    ['chatgpt-legalquants-transactional', 'skills_read_lq_start', 'LEGAL_TRANSACTIONAL_GUIDANCE'],
    ['chatgpt-linkedin', 'linkedin_search_people', 'PROFESSIONAL_PROFILE_SEARCH'],
    ['chatgpt-sofa', 'sofa_search_and_get_post', 'AGENT_KNOWLEDGE_READ'],
  ] as const)('maps %s successful read evidence to %s capability', async (connector_id, operation, capability) => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id,
      operation,
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '21')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual([capability])
    expect(observed.authority_effect).toBe('NONE')
  })

  it('keeps Ads Manager without an accessible account non-routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-ads-manager',
      operation: 'list_ad_accounts',
      outcome: 'ACCOUNT_UNAVAILABLE',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('OBSERVED_UNAVAILABLE')
    expect(observed.observed_capabilities).toEqual([])
    expect(observed.evidence_hash).toBe('6254e17cf94dc9231547e344fb21f81069f6ba1d4808aca2153f469e6852ffcb')
  })

  it('preserves Semrush billing evidence without making SEO routable', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-semrush',
      operation: 'domain_overview',
      outcome: 'BILLING_BLOCKED',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('BILLING_BLOCKED')
    expect(observed.observed_capabilities).toEqual(['SEO_INTELLIGENCE'])
    expect(observed.evidence_hash).toBe('faf37338f630fe71a9dfbb1ae01dd6a254302391e6ee4b8dc333659655f2d750')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['SEO_INTELLIGENCE'],
      allowed_providers: ['chatgpt-semrush'],
      current_generation: '22',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('keeps Blockscout network reachability below blockchain-data availability', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-blockscout',
      operation: 'unlock_blockchain_analysis',
      outcome: 'NETWORK_REACHABLE',
      result_count: 1,
    }, '22')

    expect(observed.state).toBe('NETWORK_REACHABLE')
    expect(observed.observed_capabilities).toEqual(['BLOCKCHAIN_DATA_READ'])
    expect(observed.evidence_hash).toBe('76eb44c6502654c34ade8acb44264564674a506e301b878844ba2463b569be12')

    const snapshot = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [observed])
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['BLOCKCHAIN_DATA_READ'],
      allowed_providers: ['chatgpt-blockscout'],
      current_generation: '22',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('DENIED')
    expect(receipt.provider_id).toBeNull()
    expect(receipt.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
  })

  it('binds successful LinkedIn search evidence even when result_count is zero', async () => {
    const observed = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-linkedin',
      operation: 'linkedin_search_people',
      outcome: 'READ_SUCCESS',
      result_count: 0,
    }, '22')

    expect(observed.state).toBe('OBSERVED_AVAILABLE')
    expect(observed.observed_capabilities).toEqual(['PROFESSIONAL_PROFILE_SEARCH'])
    expect(observed.evidence_hash).toBe('1a8f1c739b9cc211677169170cef489accf0c6287deb559d13caf777abb3975f')
  })

  it('rejects an unknown connector instead of accepting caller-authored capability claims', async () => {
    await expect(observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-unknown' as ChatGptConnectedAppIdV1,
      operation: 'read',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')).rejects.toThrow('unsupported ChatGPT connected app')
  })

  it('routes document retrieval only after successful connector evidence', async () => {
    const drive = await observeChatGptConnectedAppV1({
      connector_id: 'chatgpt-google-drive',
      operation: 'search',
      outcome: 'READ_SUCCESS',
      result_count: 1,
    }, '20')

    const snapshot = await buildProviderMeshSnapshotV1(
      DECLARED_PROVIDER_CATALOG_V1,
      [drive],
    )
    const receipt = await selectProviderV1(snapshot, {
      required_capabilities: ['DOCUMENT_RETRIEVAL'],
      allowed_providers: ['chatgpt-google-drive'],
      current_generation: '20',
      max_observation_age_generations: '1',
    })

    expect(receipt.outcome).toBe('SELECTED')
    expect(receipt.provider_id).toBe('chatgpt-google-drive')
    expect(receipt.authority_effect).toBe('NONE')
  })
})
