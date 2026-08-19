import { spawnSync } from 'node:child_process'

const IDENTITY_RE = /^[A-Za-z0-9._:/@+\-]{1,128}$/
const SHA256_RE = /^[0-9a-f]{64}$/
const MAX_TEXT_BYTES = 262_144
const ALLOWED_MEDIA = new Set(['text/plain', 'text/markdown', 'application/json'])

export type ProviderContributionInput = {
  workId: string
  provider: string
  model: string
  artifactDigest: string
  sourceRef: string
}

export type ProviderTextContributionInput = {
  workId: string
  provider: string
  model: string
  text: string
  sourceRef: string
  mediaType?: 'text/plain' | 'text/markdown' | 'application/json'
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

function runPython(root: string, args: string[], input?: string): string {
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const result = spawnSync(python, args, {
    cwd: root,
    env: process.env,
    encoding: 'utf8',
    input,
    timeout: 10_000,
    maxBuffer: 2_097_152,
  })
  if (result.error || result.signal || result.status !== 0) {
    throw new OrganismClientError('ORGANISM_COMMAND_FAILED', result.stderr || result.error?.message || `status=${result.status}`)
  }
  return result.stdout
}

function parseObject(raw: string): Record<string, unknown> {
  let parsed: unknown
  try { parsed = JSON.parse(raw) } catch { throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED') }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED')
  return parsed as Record<string, unknown>
}

function assertContributionBoundary(record: Record<string, unknown>, digest?: string): void {
  if (record['authority'] !== 'NON_AUTHORITATIVE_EVIDENCE') {
    throw new OrganismClientError('ORGANISM_AUTHORITY_BOUNDARY_VIOLATION')
  }
  const ref = record['contribution_ref']
  if (typeof ref !== 'string' || (digest !== undefined && !ref.includes(digest))) {
    throw new OrganismClientError('ORGANISM_CONTRIBUTION_BINDING_MISMATCH')
  }
}

export function recordProviderContribution(root: string, input: ProviderContributionInput): Record<string, unknown> {
  boundedIdentity(input.workId, 'WORK_ID_INVALID')
  boundedIdentity(input.provider, 'PROVIDER_ID_INVALID')
  boundedIdentity(input.model, 'MODEL_ID_INVALID')
  boundedIdentity(input.sourceRef, 'SOURCE_REF_INVALID')
  if (!SHA256_RE.test(input.artifactDigest)) throw new OrganismClientError('ARTIFACT_DIGEST_INVALID')

  const raw = runPython(root, [
    '-m', 'agents.organism', 'contribute',
    '--id', input.workId,
    '--provider', input.provider,
    '--model', input.model,
    '--artifact-digest', input.artifactDigest,
    '--source-ref', input.sourceRef,
  ])
  const record = parseObject(raw)
  assertContributionBoundary(record, input.artifactDigest)
  return record
}

export function recordProviderTextContribution(root: string, input: ProviderTextContributionInput): Record<string, unknown> {
  boundedIdentity(input.workId, 'WORK_ID_INVALID')
  boundedIdentity(input.provider, 'PROVIDER_ID_INVALID')
  boundedIdentity(input.model, 'MODEL_ID_INVALID')
  boundedIdentity(input.sourceRef, 'SOURCE_REF_INVALID')
  const mediaType = input.mediaType ?? 'text/markdown'
  if (!ALLOWED_MEDIA.has(mediaType)) throw new OrganismClientError('CONTRIBUTION_MEDIA_TYPE_INVALID')
  const bytes = Buffer.byteLength(input.text, 'utf8')
  if (bytes < 1) throw new OrganismClientError('CONTRIBUTION_EMPTY')
  if (bytes > MAX_TEXT_BYTES) throw new OrganismClientError('CONTRIBUTION_TOO_LARGE')

  const raw = runPython(root, ['-m', 'agents.organism', 'contribute-json'], JSON.stringify({
    work_id: input.workId,
    provider: input.provider,
    model: input.model,
    text: input.text,
    source_ref: input.sourceRef,
    media_type: mediaType,
  }))
  const record = parseObject(raw)
  const artifact = record['artifact']
  if (typeof artifact !== 'object' || artifact === null || Array.isArray(artifact)) {
    throw new OrganismClientError('ORGANISM_ARTIFACT_MALFORMED')
  }
  const digest = (artifact as Record<string, unknown>)['sha256']
  if (typeof digest !== 'string' || !SHA256_RE.test(digest)) {
    throw new OrganismClientError('ORGANISM_ARTIFACT_DIGEST_MALFORMED')
  }
  assertContributionBoundary(record, digest)
  return record
}

export function readNextWork(root: string, limit = 10): Array<Record<string, unknown>> {
  if (!Number.isSafeInteger(limit) || limit < 1 || limit > 100) throw new OrganismClientError('NEXT_WORK_LIMIT_INVALID')
  const raw = runPython(root, ['-m', 'agents.organism', 'next', '--limit', String(limit)])
  let parsed: unknown
  try { parsed = JSON.parse(raw) } catch { throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED') }
  if (!Array.isArray(parsed) || parsed.some((x) => typeof x !== 'object' || x === null || Array.isArray(x))) {
    throw new OrganismClientError('ORGANISM_RESPONSE_MALFORMED')
  }
  return parsed as Array<Record<string, unknown>>
}

export function readOrganismStatus(root: string): Record<string, unknown> {
  return parseObject(runPython(root, ['-m', 'agents.organism', 'status']))
}
