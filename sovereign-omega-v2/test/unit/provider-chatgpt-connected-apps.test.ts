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
