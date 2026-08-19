import { spawnSync } from 'node:child_process'

const IDENTITY_RE = /^[A-Za-z0-9._:/@+\-]{1,128}$/
const SHA256_RE = /^[0-9a-f]{64}$/

export type ProviderContributionInput = {
  workId: string
  provider: string
  model: string
  artifactDigest: string
  sourceRef: string
}

export class OrganismClientError extends Error {
  constructor(public readonly code: string, message?: string) {
    super(message ?? code)
    this.name = 'OrganismClientError'
  }
}

function boundedIdentity(value: string, code: string): void {
  if (!IDENTITY_RE.test(value)) throw new OrganismClientError(code)
}

export function recordProviderContribution(root: string, input: ProviderContributionInput): Record<string, unknown> {
  boundedIdentity(input.workId, 'WORK_ID_INVALID')
  boundedIdentity(input.provider, 'PROVIDER_ID_INVALID')
  boundedIdentity(input.model, 'MODEL_ID_INVALID')
  boundedIdentity(input.sourceRef, 'SOURCE_REF_INVALID')
  if (!SHA256_RE.test(input.artifactDigest)) throw new OrganismClientError('ARTIFACT_DIGEST_INVALID')

  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const result = spawnSync(
    python,
    [
      '-m', 'agents.organism', 'contribute',
      '--id', input.workId,
      '--provider', input.provider,
      '--model', input.model,
      '--artifact-digest', input.artifactDigest,
      '--source-ref', input.sourceRef,
    ],
    { cwd: root, env: process.env, encoding: 'utf8', timeout: 10_000, maxBuffer: 1_048_576 },
  )
  if (result.error || result.signal || result.status !== 0) {
    throw new OrganismClientError('ORGANISM_CONTRIBUTION_FAILED', result.stderr || result.error?.message)
  }
  let parsed: unknown
  try { parsed = JSON.parse(result.stdout) } catch { throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED') }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED')
  }
  const record = parsed as Record<string, unknown>
  if (record['authority'] !== 'NON_AUTHORITATIVE_EVIDENCE') {
    throw new OrganismClientError('ORGANISM_AUTHORITY_BOUNDARY_VIOLATION')
  }
  const ref = record['contribution_ref']
  if (typeof ref !== 'string' || !ref.includes(input.artifactDigest)) {
    throw new OrganismClientError('ORGANISM_CONTRIBUTION_BINDING_MISMATCH')
  }
  return record
}

export function readOrganismStatus(root: string): Record<string, unknown> {
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const result = spawnSync(python, ['-m', 'agents.organism', 'status'], {
    cwd: root, env: process.env, encoding: 'utf8', timeout: 10_000, maxBuffer: 1_048_576,
  })
  if (result.error || result.signal || result.status !== 0) {
    throw new OrganismClientError('ORGANISM_STATUS_FAILED', result.stderr || result.error?.message)
  }
  try {
    const parsed: unknown = JSON.parse(result.stdout)
    if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new Error('shape')
    return parsed as Record<string, unknown>
  } catch {
    throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED')
  }
}
