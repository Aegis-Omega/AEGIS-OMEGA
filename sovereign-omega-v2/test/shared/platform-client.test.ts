/**
 * PlatformClient — consume-side envelope validation tests
 * EPISTEMIC TIER: T1
 *
 * Tests that the client rejects malformed PlatformEnvelope responses before
 * they propagate into consuming code (brief §4: validate on both produce AND
 * consume; §8: schema rejection as a layer of injection/confusion defence).
 */
import { describe, it, expect, vi, beforeEach } from 'vitest'
import {
  PlatformClient,
  PlatformApiError,
  signEventEnvelope,
  type EventEnvelope,
} from '../../../packages/shared/lib/platform-client.js'

const VALID_ENVELOPE = {
  contract_version: '1.0.0',
  execution_id: 'exec-abc-123',
  timestamp: '2026-06-10T00:00:00Z',
  is_replay_reconstructable: true,
  data: { version: '1.0.0', chain_valid: true, total_agents: 39, available: true, contract_version: '1.0.0', audit_chain_hash: '0'.repeat(64) },
}

function mockFetch(body: unknown, status = 200) {
  global.fetch = vi.fn().mockResolvedValue({
    ok: status >= 200 && status < 300,
    status,
    json: () => Promise.resolve(body),
    body: null,
  }) as unknown as typeof fetch
}

beforeEach(() => { vi.restoreAllMocks() })

const client = new PlatformClient('aegis_test_key', 'http://localhost:7890')

describe('PlatformClient envelope validation', () => {
  it('passes through a well-formed PlatformEnvelope', async () => {
    mockFetch(VALID_ENVELOPE)
    const result = await client.status()
    expect(result).toEqual(VALID_ENVELOPE.data)
  })

  it('rejects response missing contract_version', async () => {
    const { contract_version: _, ...bad } = VALID_ENVELOPE
    mockFetch(bad)
    await expect(client.status()).rejects.toThrow(PlatformApiError)
    await expect(client.status()).rejects.toMatchObject({ code: 'INTERNAL' })
  })

  it('rejects response missing execution_id', async () => {
    const { execution_id: _, ...bad } = VALID_ENVELOPE
    mockFetch(bad)
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })

  it('rejects response missing timestamp', async () => {
    const { timestamp: _, ...bad } = VALID_ENVELOPE
    mockFetch(bad)
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })

  it('rejects response with is_replay_reconstructable !== true', async () => {
    mockFetch({ ...VALID_ENVELOPE, is_replay_reconstructable: false })
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })

  it('rejects response with is_replay_reconstructable missing', async () => {
    const { is_replay_reconstructable: _, ...bad } = VALID_ENVELOPE
    mockFetch(bad)
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })

  it('surfaces HTTP error with PlatformError code on 4xx', async () => {
    mockFetch({ error: 'Invalid or revoked API key', code: 'UNAUTHORIZED' }, 401)
    await expect(client.status()).rejects.toMatchObject({ code: 'UNAUTHORIZED', status: 401 })
  })

  it('surfaces HTTP error on 429 rate limit', async () => {
    mockFetch({ error: 'Usage limit reached', code: 'RATE_LIMITED' }, 429)
    await expect(client.status()).rejects.toMatchObject({ code: 'RATE_LIMITED', status: 429 })
  })

  it('is_replay_reconstructable: true is the exact boolean true, not truthy', async () => {
    mockFetch({ ...VALID_ENVELOPE, is_replay_reconstructable: 1 })
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })

  it('rejects response with contract_version !== 1.0.0', async () => {
    mockFetch({ ...VALID_ENVELOPE, contract_version: '2.0.0' })
    await expect(client.status()).rejects.toThrow(PlatformApiError)
    await expect(client.status()).rejects.toMatchObject({ code: 'INTERNAL' })
  })

  it('rejects response with contract_version as numeric 1', async () => {
    mockFetch({ ...VALID_ENVELOPE, contract_version: 1 })
    await expect(client.status()).rejects.toThrow(PlatformApiError)
  })
})

describe('PlatformClient collaborate/startExecution envelope validation', () => {
  it('collaborate: valid envelope passes through', async () => {
    const collab_data = {
      cycle_id: 'c1', objective: 'grow ARR', mode: 'revenue',
      departments_collaborated: 39, artifacts: [],
      projection: {}, constitutional_audit: { verdict: 'APPROVED' },
      chain_valid: true, audit_chain_hash: '0'.repeat(64), execution_id: 'exec-1',
    }
    mockFetch({ ...VALID_ENVELOPE, data: collab_data })
    const result = await client.collaborate({ objective: 'grow ARR', mode: 'revenue', live: false })
    expect(result).toEqual(collab_data)
  })

  it('collaborate: missing envelope field rejects with PlatformApiError', async () => {
    const { contract_version: _, ...bad } = VALID_ENVELOPE
    mockFetch(bad)
    await expect(
      client.collaborate({ objective: 'grow ARR', mode: 'revenue', live: false })
    ).rejects.toThrow(PlatformApiError)
  })

  it('startExecution: valid envelope passes through', async () => {
    const exec_data = { execution_id: 'exec-2', stream_url: '/platform/executions/live?id=exec-2', status: 'pending' }
    mockFetch({ ...VALID_ENVELOPE, data: exec_data })
    const result = await client.startExecution({ objective: 'test', mode: 'analysis', live: false })
    expect(result).toEqual(exec_data)
  })
})

describe('PlatformClient deleteExecution', () => {
  it('204 response succeeds without throwing', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: true, status: 204, json: () => Promise.resolve({}), body: null,
    }) as unknown as typeof fetch
    await expect(client.deleteExecution('exec-del-1')).resolves.toBeUndefined()
  })

  it('401 on DELETE throws with UNAUTHORIZED code', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 401,
      json: () => Promise.resolve({ error: 'Invalid or revoked API key', code: 'UNAUTHORIZED' }),
      body: null,
    }) as unknown as typeof fetch
    await expect(client.deleteExecution('exec-del-2')).rejects.toMatchObject({
      code: 'UNAUTHORIZED', status: 401,
    })
  })

  it('500 on DELETE throws with INTERNAL code', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      ok: false, status: 500,
      json: () => Promise.resolve({ error: 'server error', code: 'INTERNAL' }),
      body: null,
    }) as unknown as typeof fetch
    await expect(client.deleteExecution('exec-del-3')).rejects.toMatchObject({
      code: 'INTERNAL', status: 500,
    })
  })
})


describe('PlatformClient: System-2 EventEnvelope Verification Tests', () => {
  const mockSecret = '6180339887a0b3f81e6a9f4c3d2e1b0a7c5d6e3f4a1b9c2d8e7f6a5b4c3d2e1f' // pragma: allowlist secret
  const parentHash = '69a8f27b9c4c11e49afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
  const deterministicTimestamp = '2026-06-10T00:00:00Z'
  let verificationClient: PlatformClient

  beforeEach(() => {
    verificationClient = new PlatformClient({
      endpoint: 'http://localhost:5000/platform',
      apiKey: 'test-api-key-tier-regulatory',
      secretKey: mockSecret,
      genesisHash: parentHash,
      initialSequence: 0,
    })
  })

  function validEnvelope(overrides: Partial<EventEnvelope> = {}): EventEnvelope {
    return {
      execution_id: '86f725a0-0d22-441d-b52e-c1cfc1157956',
      parent_hash: parentHash,
      sequence: 1,
      timestamp: deterministicTimestamp,
      payload: { opportunity_id: '0068W000018xxxxQAA', status: 'VERIFIED' },
      ...overrides,
    }
  }

  it('Valid EventEnvelope passes verification seamlessly', () => {
    const envelope = validEnvelope()
    const validSignature = signEventEnvelope(envelope, mockSecret)
    const result = verificationClient.verifyEnvelopeLocally(envelope, validSignature)
    expect(result.isValid).toBe(true)
    expect(result.nextChainHash).toMatch(/^[a-f0-9]{64}$/)
  })

  it('Envelope signature verification fails with mutated payload', () => {
    const envelope = validEnvelope()
    const signature = signEventEnvelope(envelope, mockSecret)
    const mutatedEnvelope = validEnvelope({
      payload: { opportunity_id: '0068W000018xxxxQAA', status: 'COMPLIANT_BYPASS' },
    })

    const result = verificationClient.verifyEnvelopeLocally(mutatedEnvelope, signature)
    expect(result.isValid).toBe(false)
    expect(result.error).toContain('SIGNATURE_MISMATCH')
  })

  it('System-2 rejects out-of-sequence sequence identifiers', () => {
    const envelope = validEnvelope({ sequence: 9999 })
    const signature = signEventEnvelope(envelope, mockSecret)
    const result = verificationClient.verifyEnvelopeLocally(envelope, signature)
    expect(result.isValid).toBe(false)
    expect(result.error).toContain('SEQUENCE_OUT_OF_BOUNDS')
  })

  it('System-2 rejects mismatched parent hash before chain advancement', () => {
    const envelope = validEnvelope({ parent_hash: '0'.repeat(64) })
    const signature = signEventEnvelope(envelope, mockSecret)
    const result = verificationClient.verifyEnvelopeLocally(envelope, signature)
    expect(result.isValid).toBe(false)
    expect(result.error).toContain('PARENT_HASH_MISMATCH')
  })
})
