/**
 * AEGIS-Ω Platform Client — TypeScript SDK
 * EPISTEMIC TIER: T1
 *
 * Typed fetch wrapper for the /platform/* API on aegis-vertex.aegisomega.com.
 * Import from any product in the monorepo via @shared/lib/platform-client.
 *
 * All responses are unwrapped from PlatformEnvelope automatically.
 * The raw envelope is available via the `envelope` field on the result.
 */

import type {
  CollaborationRequest,
  CollaborationResult,
  ExecutionInitResult,
  ExecutionGetResult,
  PlatformEnvelope,
  PlatformError,
  PlatformErrorCode,
  PlatformStatus,
  SseEvent,
} from './platform-contract.js'

export type { CollaborationRequest, CollaborationResult, PlatformStatus, SseEvent }

export interface EventEnvelope {
  readonly execution_id: string
  readonly parent_hash: string
  readonly sequence: number
  readonly timestamp: string
  readonly payload: Record<string, unknown>
}

export interface LocalEnvelopeVerificationResult {
  readonly isValid: boolean
  readonly nextChainHash?: string
  readonly error?: string
}

export interface PlatformClientOptions {
  readonly apiKey: string
  readonly endpoint?: string
  readonly secretKey?: string
  readonly genesisHash?: string
  readonly initialSequence?: number
}

const DEFAULT_AUTOMATON_GENESIS_HASH = '69a8f27b9c4c11e49afbf4c8996fb92427ae41e4649b934ca495991b7852b855'
const SHA256_HEX_PATTERN = /^[a-f0-9]{64}$/i

// ── Error class ───────────────────────────────────────────────────────────────

export class PlatformApiError extends Error {
  constructor(
    message: string,
    public readonly code: PlatformErrorCode,
    public readonly status: number,
    public readonly execution_id?: string,
  ) {
    super(message)
    this.name = 'PlatformApiError'
  }
}

// ── Client ────────────────────────────────────────────────────────────────────

export class PlatformClient {
  private readonly base: string
  private readonly apiKey: string
  private readonly secretKey: string | undefined
  private readonly genesisHash: string
  private readonly initialSequence: number

  constructor(apiKeyOrOptions: string | PlatformClientOptions, base = 'https://aegis-vertex.aegisomega.com') {
    if (typeof apiKeyOrOptions === 'string') {
      this.apiKey = apiKeyOrOptions
      this.base = base.replace(/\/$/, '')
      this.genesisHash = DEFAULT_AUTOMATON_GENESIS_HASH
      this.initialSequence = 0
      return
    }

    this.apiKey = apiKeyOrOptions.apiKey
    this.base = (apiKeyOrOptions.endpoint ?? base).replace(/\/$/, '')
    this.secretKey = apiKeyOrOptions.secretKey
    this.genesisHash = apiKeyOrOptions.genesisHash ?? DEFAULT_AUTOMATON_GENESIS_HASH
    this.initialSequence = apiKeyOrOptions.initialSequence ?? 0
  }

  async verifyEnvelopeLocally(
    envelope: EventEnvelope,
    signature: string,
    expectedParentHash?: string,
    expectedSequence?: number,
  ): Promise<LocalEnvelopeVerificationResult> {
    if (this.secretKey === undefined || this.secretKey.length === 0) {
      return { isValid: false, error: 'SECRET_KEY_MISSING' }
    }

    const shapeError = validateEventEnvelopeShape(envelope)
    if (shapeError !== undefined) {
      return { isValid: false, error: shapeError }
    }

    // Caller supplies the expected parent hash and sequence for chain position N.
    // Falls back to genesisHash / initialSequence+1 for the first envelope only.
    const parentHash = expectedParentHash ?? this.genesisHash
    const sequence   = expectedSequence   ?? this.initialSequence + 1

    if (envelope.parent_hash !== parentHash) {
      return { isValid: false, error: 'PARENT_HASH_MISMATCH' }
    }

    if (envelope.sequence !== sequence) {
      return { isValid: false, error: 'SEQUENCE_OUT_OF_BOUNDS' }
    }

    const expectedSignature = await signEventEnvelope(envelope, this.secretKey)
    if (!timingSafeHexEqual(expectedSignature, signature)) {
      return { isValid: false, error: 'SIGNATURE_MISMATCH' }
    }

    if (!payloadPassesConstitutionalFilter(envelope.payload)) {
      return { isValid: false, error: 'CONSTITUTIONAL_VIOLATION' }
    }

    return { isValid: true, nextChainHash: await calculateEventEnvelopeHash(envelope) }
  }

  // ── GET /platform/status ──────────────────────────────────────────────────

  async status(): Promise<PlatformStatus> {
    const env = await this._get<PlatformStatus>('/platform/status')
    return env.data
  }

  // ── POST /platform/collaborate ────────────────────────────────────────────

  async collaborate(req: CollaborationRequest): Promise<CollaborationResult> {
    const env = await this._post<CollaborationResult>('/platform/collaborate', req)
    return env.data
  }

  // ── POST /platform/executions (async init) ────────────────────────────────

  async startExecution(req: CollaborationRequest): Promise<ExecutionInitResult> {
    const env = await this._post<ExecutionInitResult>('/platform/executions', req)
    return env.data
  }

  // ── GET /platform/executions/{id} (poll result) ───────────────────────────

  async getExecution(executionId: string): Promise<ExecutionGetResult> {
    const env = await this._get<ExecutionGetResult>(`/platform/executions/${executionId}`)
    return env.data
  }

  // ── DELETE /platform/executions/{id} ─────────────────────────────────────

  async deleteExecution(executionId: string): Promise<void> {
    const resp = await fetch(`${this.base}/platform/executions/${executionId}`, {
      method: 'DELETE',
      headers: { 'x-api-key': this.apiKey },
    })
    if (resp.status !== 204 && !resp.ok) {
      await this._throwFromResponse(resp)
    }
  }

  // ── GET /platform/executions/live (SSE stream) ────────────────────────────

  /**
   * Open an SSE stream for an async execution.
   * Yields typed SseEvent objects until 'completion' or 'error'.
   *
   * @example
   * const { execution_id } = await client.startExecution(req)
   * for await (const event of client.streamExecution(execution_id)) {
   *   if (event.type === 'completion') console.log(event.payload)
   * }
   */
  async *streamExecution(executionId: string): AsyncGenerator<SseEvent> {
    const resp = await fetch(
      `${this.base}/platform/executions/live?id=${executionId}`,
      { headers: { 'x-api-key': this.apiKey } },
    )
    if (!resp.ok || !resp.body) {
      await this._throwFromResponse(resp)
      return
    }

    const reader = resp.body.getReader()
    const decoder = new TextDecoder()
    let buf = ''

    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })

      const lines = buf.split('\n')
      buf = lines.pop() ?? ''

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        const raw = line.slice(6).trim()
        if (!raw) continue
        let event: SseEvent
        try {
          event = JSON.parse(raw) as SseEvent
        } catch {
          continue
        }
        yield event
        if (event.type === 'completion' || event.type === 'error') return
      }
    }
  }

  // ── Internal helpers ──────────────────────────────────────────────────────

  private async _get<T>(path: string): Promise<PlatformEnvelope<T>> {
    const resp = await fetch(`${this.base}${path}`, {
      headers: { 'x-api-key': this.apiKey },
    })
    return this._parse<T>(resp)
  }

  private async _post<T>(path: string, body: object): Promise<PlatformEnvelope<T>> {
    const resp = await fetch(`${this.base}${path}`, {
      method: 'POST',
      headers: {
        'x-api-key': this.apiKey,
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(body),
    })
    return this._parse<T>(resp)
  }

  private async _parse<T>(resp: Response): Promise<PlatformEnvelope<T>> {
    let json: unknown
    try {
      json = await resp.json()
    } catch {
      throw new PlatformApiError('Non-JSON response', 'INTERNAL', resp.status)
    }

    if (!resp.ok) {
      const err = json as Partial<PlatformError>
      throw new PlatformApiError(
        err.error ?? `HTTP ${resp.status}`,
        (err.code as PlatformErrorCode) ?? 'INTERNAL',
        resp.status,
        err.execution_id,
      )
    }

    const envelopeError = validatePlatformEnvelope(json)
    if (envelopeError !== undefined) {
      throw new PlatformApiError(envelopeError, 'INTERNAL', resp.status)
    }

    return json as PlatformEnvelope<T>
  }

  private async _throwFromResponse(resp: Response): Promise<never> {
    let err: Partial<PlatformError> = {}
    try { err = (await resp.json()) as Partial<PlatformError> } catch { /* ignore */ }
    throw new PlatformApiError(
      err.error ?? `HTTP ${resp.status}`,
      (err.code as PlatformErrorCode) ?? 'INTERNAL',
      resp.status,
      err.execution_id,
    )
  }
}

// ── Factory ───────────────────────────────────────────────────────────────────

/**
 * Create a PlatformClient with the given API key.
 * The base URL defaults to the production endpoint.
 */
export function createPlatformClient(
  apiKey: string,
  base?: string,
): PlatformClient {
  return new PlatformClient(apiKey, base)
}

// Web Crypto helpers — work in browsers, Node 18+, Deno, CF Workers
// Replaces node:crypto which is unavailable in browser runtimes.

async function sha256Hex(data: string): Promise<string> {
  const buf = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(data))
  return Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, '0')).join('')
}

async function hmacSha256Hex(keyBytes: Uint8Array, data: string): Promise<string> {
  const key = await globalThis.crypto.subtle.importKey(
    'raw', keyBytes.buffer.slice(keyBytes.byteOffset, keyBytes.byteOffset + keyBytes.byteLength) as ArrayBuffer,
    { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'],
  )
  const sig = await globalThis.crypto.subtle.sign('HMAC', key, new TextEncoder().encode(data))
  return Array.from(new Uint8Array(sig)).map(b => b.toString(16).padStart(2, '0')).join('')
}

function secretKeyBytes(secretKey: string): Uint8Array {
  if (/^[a-f0-9]+$/i.test(secretKey) && secretKey.length % 2 === 0) {
    const bytes = new Uint8Array(secretKey.length / 2)
    for (let i = 0; i < bytes.length; i++) bytes[i] = parseInt(secretKey.slice(i * 2, i * 2 + 2), 16)
    return bytes
  }
  return new TextEncoder().encode(secretKey)
}

export async function calculateEventEnvelopeHash(envelope: EventEnvelope): Promise<string> {
  const canonicalEnvelope = {
    execution_id: envelope.execution_id,
    parent_hash: envelope.parent_hash,
    payload: envelope.payload,
    sequence: envelope.sequence,
    timestamp: envelope.timestamp,
  }
  return sha256Hex(canonicalizeJson(canonicalEnvelope))
}

export async function signEventEnvelope(envelope: EventEnvelope, secretKey: string): Promise<string> {
  const envelopeHash = await calculateEventEnvelopeHash(envelope)
  return hmacSha256Hex(secretKeyBytes(secretKey), envelopeHash)
}

function validatePlatformEnvelope(json: unknown): string | undefined {
  if (!isPlainRecord(json)) return 'envelope is not an object'
  const { contract_version, execution_id, timestamp, is_replay_reconstructable, data } = json as Record<string, unknown>
  if (typeof contract_version !== 'string') return 'missing or non-string contract_version'
  if (contract_version !== '1.0.0') return `contract_version mismatch: ${contract_version}`
  if (typeof execution_id !== 'string' || execution_id.length === 0) return 'missing or empty execution_id'
  if (typeof timestamp !== 'string' || timestamp.length === 0) return 'missing or empty timestamp'
  if (is_replay_reconstructable !== true) return 'is_replay_reconstructable must be exactly true'
  if (data === undefined) return 'envelope missing data field'
  return undefined
}

function validateEventEnvelopeShape(envelope: EventEnvelope): string | undefined {
  if (typeof envelope.execution_id !== 'string' || envelope.execution_id.length === 0) {
    return 'ENVELOPE_INVALID: execution_id'
  }
  if (!SHA256_HEX_PATTERN.test(envelope.parent_hash)) {
    return 'ENVELOPE_INVALID: parent_hash'
  }
  if (!Number.isSafeInteger(envelope.sequence) || envelope.sequence < 0) {
    return 'ENVELOPE_INVALID: sequence'
  }
  if (typeof envelope.timestamp !== 'string' || envelope.timestamp.length === 0) {
    return 'ENVELOPE_INVALID: timestamp'
  }
  if (!isPlainRecord(envelope.payload)) {
    return 'ENVELOPE_INVALID: payload'
  }
  return undefined
}

function payloadPassesConstitutionalFilter(payload: Record<string, unknown>): boolean {
  const prohibited = ['DROP', 'DELETE', 'FORCE_COMMIT', 'BYPASS_CONSENSUS']
  return payloadEntries(payload).every(([key, value]) => {
    const keyText = key.toUpperCase()
    const valueText = String(value).toUpperCase()
    return prohibited.every(command => !keyText.includes(command) && !valueText.includes(command))
  })
}

function payloadEntries(payload: Record<string, unknown>): ReadonlyArray<readonly [string, unknown]> {
  const entries: Array<readonly [string, unknown]> = []
  for (const key of Object.keys(payload)) {
    const value = payload[key]
    if (isPlainRecord(value)) {
      entries.push([key, ''])
      entries.push(...payloadEntries(value).map(([childKey, childValue]) => [`${key}.${childKey}`, childValue] as const))
    } else if (Array.isArray(value)) {
      entries.push([key, ''])
      value.forEach((item, index) => {
        if (isPlainRecord(item)) {
          entries.push(...payloadEntries(item).map(([childKey, childValue]) => [`${key}[${index}].${childKey}`, childValue] as const))
        } else {
          entries.push([`${key}[${index}]`, item])
        }
      })
    } else {
      entries.push([key, value])
    }
  }
  return entries
}

function timingSafeHexEqual(left: string, right: string): boolean {
  const rightLower = right.toLowerCase()
  if (!/^[a-f0-9]+$/.test(rightLower) || left.length !== rightLower.length) return false
  let diff = 0
  for (let index = 0; index < left.length; index += 1) {
    diff |= left.charCodeAt(index) ^ rightLower.charCodeAt(index)
  }
  return diff === 0
}


function canonicalizeJson(value: unknown): string {
  if (value === null) return 'null'
  if (typeof value === 'string') return quoteJsonString(value)
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) throw new RangeError('non-finite numbers are not canonical JSON')
    return String(value)
  }
  if (typeof value === 'boolean') return value ? 'true' : 'false'
  if (Array.isArray(value)) return `[${value.map(item => canonicalizeJson(item)).join(',')}]`
  if (isPlainRecord(value)) {
    return `{${Object.keys(value).sort().map(key => `${quoteJsonString(key)}:${canonicalizeJson(value[key])}`).join(',')}}`
  }
  throw new TypeError(`unsupported canonical JSON value: ${typeof value}`)
}

function isPlainRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}

function quoteJsonString(value: string): string {
  let out = '"'
  for (let index = 0; index < value.length; ) {
    const cp = value.codePointAt(index) ?? 0
    if (cp > 0xffff) {
      // Non-BMP character: emit surrogate pair escape sequences
      const hi = Math.floor((cp - 0x10000) / 0x400) + 0xd800
      const lo = ((cp - 0x10000) % 0x400) + 0xdc00
      out += `\\u${hi.toString(16).padStart(4, '0')}\\u${lo.toString(16).padStart(4, '0')}`
      index += 2
      continue
    }
    switch (cp) {
      case 0x08: out += '\\b'; break
      case 0x09: out += '\\t'; break
      case 0x0a: out += '\\n'; break
      case 0x0c: out += '\\f'; break
      case 0x0d: out += '\\r'; break
      case 0x22: out += '\\"'; break
      case 0x5c: out += '\\\\'; break
      default:
        if (cp <= 0x1f) {
          out += `\\u${cp.toString(16).padStart(4, '0')}`
        } else {
          out += value[index]
        }
    }
    index += 1
  }
  return `${out}"`
}
