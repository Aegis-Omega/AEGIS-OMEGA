import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

const SAFE_ID = /^[A-Za-z0-9._:/@+\-]{1,128}$/

export type ProviderActionBootstrapInput = {
  actionClass: string
  authorityDomain: string
  requestedCapability: string
  tool: string
  target: string
  action: Record<string, unknown>
  mutationTarget?: string
}

export type ProviderSessionBootstrap = {
  identity: Record<string, unknown>
  identity_root: string
  workspace: Record<string, unknown>
  state_root: string
  capability: string
  authority: 'IDENTITY_ONLY_NOT_AUTHORIZATION'
}

export class ProviderSessionError extends Error {
  constructor(public readonly code: string, message?: string) {
    super(message ?? code)
    this.name = 'ProviderSessionError'
  }
}

function requiredProviderEnv(name: string): string {
  const value = process.env[name]
  if (!value || !SAFE_ID.test(value)) throw new ProviderSessionError(`${name}_UNAVAILABLE_OR_INVALID`)
  return value
}

export function providerSessionConfigured(): boolean {
  return Boolean(process.env['AEGIS_PROVIDER_ID'] && process.env['AEGIS_MODEL_ID'] && process.env['AEGIS_PROVIDER_SESSION_ID'])
}

export function bootstrapProviderAction(root: string, input: ProviderActionBootstrapInput): ProviderSessionBootstrap {
  const provider = requiredProviderEnv('AEGIS_PROVIDER_ID')
  const model = requiredProviderEnv('AEGIS_MODEL_ID')
  const session = requiredProviderEnv('AEGIS_PROVIDER_SESSION_ID')
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const result = spawnSync(python, [join(root, 'scripts', 'provider-session-bootstrap.py')], {
    cwd: root,
    env: process.env,
    encoding: 'utf8',
    input: JSON.stringify({
      provider,
      model,
      session,
      action_class: input.actionClass,
      authority_domain: input.authorityDomain,
      requested_capability: input.requestedCapability,
      tool: input.tool,
      target: input.target,
      mutation_target: input.mutationTarget ?? '.',
      action: input.action,
    }),
    timeout: 15_000,
    maxBuffer: 1_048_576,
  })
  if (result.error || result.signal || result.status !== 0) {
    throw new ProviderSessionError('PROVIDER_SESSION_BOOTSTRAP_FAILED', result.stderr || result.stdout || result.error?.message)
  }
  let parsed: unknown
  try { parsed = JSON.parse(result.stdout) } catch { throw new ProviderSessionError('PROVIDER_SESSION_BOOTSTRAP_MALFORMED') }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new ProviderSessionError('PROVIDER_SESSION_BOOTSTRAP_MALFORMED')
  const record = parsed as Record<string, unknown>
  if (record['authority'] !== 'IDENTITY_ONLY_NOT_AUTHORIZATION') throw new ProviderSessionError('PROVIDER_SESSION_AUTHORITY_BOUNDARY_VIOLATION')
  if (typeof record['identity'] !== 'object' || record['identity'] === null || Array.isArray(record['identity'])) throw new ProviderSessionError('PROVIDER_SESSION_IDENTITY_MALFORMED')
  if (typeof record['workspace'] !== 'object' || record['workspace'] === null || Array.isArray(record['workspace'])) throw new ProviderSessionError('PROVIDER_SESSION_WORKSPACE_MALFORMED')
  return record as unknown as ProviderSessionBootstrap
}
