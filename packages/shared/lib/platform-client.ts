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

  constructor(apiKey: string, base = 'https://aegis-vertex.aegisomega.com') {
    this.apiKey = apiKey
    this.base = base.replace(/\/$/, '')
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
