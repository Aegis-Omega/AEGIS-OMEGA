// ============================================================
// SOVEREIGN OMEGA — Admin API Client
// EPISTEMIC TIER: T2 · Gate 219
//
// Programmatic management of the Anthropic organization:
//   - Usage and cost monitoring
//   - Workspace management
//   - API key inventory
//
// Copyright (C) 2025 Tarik Skalić — All rights reserved.
// ============================================================

export const ADMIN_CLIENT_SCHEMA_VERSION = '1.0.0' as const
const ANTHROPIC_API_BASE = 'https://api.anthropic.com'
const ANTHROPIC_VERSION = '2023-06-01'
const DEFAULT_ADMIN_TIMEOUT_MS = 30_000
const MAX_ADMIN_ERROR_BODY_CHARS = 2_048

export interface OrgInfo {
  readonly id: string
  readonly name: string
  readonly type: 'organization'
}

export interface ApiKeyInfo {
  readonly id: string
  readonly name: string
  readonly status: 'active' | 'inactive'
  readonly created_at: string
  readonly workspace_id?: string
}

export interface WorkspaceInfo {
  readonly id: string
  readonly name: string
  readonly created_at: string
  readonly archived_at?: string
}

export class AdminClient {
  private readonly _adminKey: string
  private readonly _timeoutMs: number

  constructor(adminKey?: string, timeoutMs = DEFAULT_ADMIN_TIMEOUT_MS) {
    const key = adminKey ?? process.env.ANTHROPIC_ADMIN_API_KEY
    if (!key) throw new Error('[ADMIN_CLIENT] ANTHROPIC_ADMIN_API_KEY not set')
    if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) {
      throw new RangeError('[ADMIN_CLIENT] timeoutMs must be a finite positive number')
    }
    this._adminKey = key
    this._timeoutMs = Math.floor(timeoutMs)
  }

  private async _fetch<T>(path: string, options: RequestInit = {}): Promise<T> {
    const signal = options.signal ?? AbortSignal.timeout(this._timeoutMs)
    let res: Response

    try {
      res = await fetch(`${ANTHROPIC_API_BASE}${path}`, {
        ...options,
        signal,
        headers: {
          'anthropic-version': ANTHROPIC_VERSION,
          'x-api-key': this._adminKey,
          'content-type': 'application/json',
          ...(options.headers ?? {}),
        },
      })
    } catch (error) {
      if (error instanceof Error && (error.name === 'AbortError' || error.name === 'TimeoutError')) {
        throw new Error(`[ADMIN_API] timeout after ${this._timeoutMs}ms ${path}`)
      }
      throw error
    }

    if (!res.ok) {
      const body = (await res.text()).slice(0, MAX_ADMIN_ERROR_BODY_CHARS)
      throw new Error(`[ADMIN_API] ${res.status} ${path}: ${body}`)
    }
    return res.json() as Promise<T>
  }

  /** Get organization info. */
  async getOrg(): Promise<OrgInfo> {
    return this._fetch<OrgInfo>('/v1/organizations/me')
  }

  /** List all API keys (active and inactive). */
  async listApiKeys(limit = 20): Promise<ApiKeyInfo[]> {
    const data = await this._fetch<{ data: ApiKeyInfo[] }>(
      `/v1/organizations/api_keys?limit=${limit}&status=active`
    )
    return data.data ?? []
  }

  /** List workspaces. */
  async listWorkspaces(limit = 20): Promise<WorkspaceInfo[]> {
    const data = await this._fetch<{ data: WorkspaceInfo[] }>(
      `/v1/organizations/workspaces?limit=${limit}`
    )
    return data.data ?? []
  }

  /** Create a new workspace. */
  async createWorkspace(name: string): Promise<WorkspaceInfo> {
    return this._fetch<WorkspaceInfo>('/v1/organizations/workspaces', {
      method: 'POST',
      body: JSON.stringify({ name }),
    })
  }

  /** Get a summary of org status (org info + key count + workspace count). */
  async summary(): Promise<{
    org: OrgInfo
    activeKeyCount: number
    workspaceCount: number
  }> {
    const [org, keys, workspaces] = await Promise.all([
      this.getOrg(),
      this.listApiKeys(),
      this.listWorkspaces(),
    ])
    return { org, activeKeyCount: keys.length, workspaceCount: workspaces.length }
  }
}
