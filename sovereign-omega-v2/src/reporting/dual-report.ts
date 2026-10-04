// ============================================================
// SOVEREIGN OMEGA — Dual Report Contract V1
// EPISTEMIC TIER: T0/T1 reporting infrastructure
// PURPOSE: one evidence core, two deterministic projections
// ============================================================

import type { SHA256Hex } from '../core/types.js'
import { hashString, hashValue } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'

export const DUAL_REPORT_FORMAT = 'AEGIS_DUAL_REPORT'
export const DUAL_REPORT_VERSION = '1.0.0'
export const DUAL_REPORT_CANONICALIZATION = 'RFC8785'

export const REPORT_STATUSES = ['PASS', 'FAIL', 'BLOCKED', 'PARTIAL', 'INFORMATIONAL'] as const
export const CLAIM_STATUSES = ['VERIFIED', 'FALSIFIED', 'UNVERIFIED'] as const
export const EPISTEMIC_TIERS = ['T0', 'T1', 'T2', 'T3', 'T4', 'T5'] as const
export const ADMISSION_STATES = ['ADMITTED', 'NOT_ADMITTED', 'NOT_APPLICABLE'] as const
export const AUTHORITY_EFFECTS = [
  'NONE',
  'READ_ONLY',
  'MUTATION_PROPOSED',
  'MUTATION_EXECUTED',
  'AUTHORITY_CHANGED',
] as const
export const EVIDENCE_KINDS = [
  'github_commit',
  'workflow_run',
  'artifact',
  'file',
  'test_run',
  'external',
] as const

export type ReportStatus = typeof REPORT_STATUSES[number]
export type ClaimStatus = typeof CLAIM_STATUSES[number]
export type EpistemicTier = typeof EPISTEMIC_TIERS[number]
export type AdmissionState = typeof ADMISSION_STATES[number]
export type AuthorityEffect = typeof AUTHORITY_EFFECTS[number]
export type EvidenceKind = typeof EVIDENCE_KINDS[number]

export interface ExactHeadBinding {
  readonly repository: string
  readonly commit_sha: string
}

export interface ReportClaim {
  readonly claim_id: string
  readonly statement: string
  readonly status: ClaimStatus
  readonly evidence_ids: readonly string[]
}

export interface EvidenceReference {
  readonly evidence_id: string
  readonly kind: EvidenceKind
  readonly locator: string
  readonly sha256?: SHA256Hex
}

export interface EvidenceReportCore {
  readonly report_id: string
  readonly title: string
  readonly generated_at: string
  readonly exact_head: ExactHeadBinding
  readonly status: ReportStatus
  readonly epistemic_tier: EpistemicTier
  readonly admission: AdmissionState
  readonly authority_effect: AuthorityEffect
  readonly scope: string
  readonly summary: string
  readonly claims: readonly ReportClaim[]
  readonly evidence: readonly EvidenceReference[]
  readonly limitations: readonly string[]
  readonly next_actions: readonly string[]
}

export interface MachineReportV1 {
  readonly format: typeof DUAL_REPORT_FORMAT
  readonly report_version: typeof DUAL_REPORT_VERSION
  readonly canonicalization: typeof DUAL_REPORT_CANONICALIZATION
  readonly core: Readonly<EvidenceReportCore>
  readonly integrity: Readonly<{
    readonly core_sha256: SHA256Hex
    readonly human_sha256: SHA256Hex
  }>
}

export interface BuiltDualReport {
  readonly machine: Readonly<MachineReportV1>
  readonly human: string
}

export interface DualReportVerification {
  readonly ok: boolean
  readonly code:
    | 'VERIFIED'
    | 'INVALID_REPORT'
    | 'CORE_DIGEST_MISMATCH'
    | 'HUMAN_RENDER_MISMATCH'
    | 'HUMAN_DIGEST_MISMATCH'
  readonly detail: string
}

const SHA256_RE = /^[0-9a-f]{64}$/
const GIT_OID_RE = /^(?:[0-9a-f]{40}|[0-9a-f]{64})$/
const REPOSITORY_RE = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/
const RFC3339_UTC_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/
const ID_RE = /^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$/

const CORE_KEYS = [
  'report_id',
  'title',
  'generated_at',
  'exact_head',
  'status',
  'epistemic_tier',
  'admission',
  'authority_effect',
  'scope',
  'summary',
  'claims',
  'evidence',
  'limitations',
  'next_actions',
] as const

const EXACT_HEAD_KEYS = ['repository', 'commit_sha'] as const
const CLAIM_KEYS = ['claim_id', 'statement', 'status', 'evidence_ids'] as const
const EVIDENCE_KEYS = ['evidence_id', 'kind', 'locator', 'sha256'] as const
const MACHINE_KEYS = ['format', 'report_version', 'canonicalization', 'core', 'integrity'] as const
const INTEGRITY_KEYS = ['core_sha256', 'human_sha256'] as const

function isRecord(value: unknown): value is Record<string, unknown> {
  return value !== null && typeof value === 'object' && !Array.isArray(value)
}

function assertRecord(value: unknown, name: string): asserts value is Record<string, unknown> {
  if (!isRecord(value)) throw new TypeError(name + ' must be an object')
}

function assertExactKeys(value: unknown, name: string, allowed: readonly string[]): void {
  assertRecord(value, name)
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) {
      throw new TypeError(name + ' contains unsupported field: ' + key)
    }
  }
}

function assertNonEmptyString(value: unknown, name: string): asserts value is string {
  if (typeof value !== 'string' || value.trim().length === 0) {
    throw new TypeError(name + ' must be a non-empty string')
  }
}

function assertId(value: unknown, name: string): asserts value is string {
  assertNonEmptyString(value, name)
  if (!ID_RE.test(value)) throw new TypeError(name + ' is not a valid report identifier')
}

function assertEnum(value: unknown, name: string, allowed: readonly string[]): asserts value is string {
  if (typeof value !== 'string' || !allowed.includes(value)) {
    throw new TypeError(name + ' must be one of: ' + allowed.join(', '))
  }
}

function assertStringArray(value: unknown, name: string): asserts value is readonly string[] {
  if (!Array.isArray(value)) throw new TypeError(name + ' must be an array')
  for (let i = 0; i < value.length; i += 1) {
    assertNonEmptyString(value[i], name + '[' + i + ']')
  }
}

function assertSha256(value: unknown, name: string): asserts value is SHA256Hex {
  if (typeof value !== 'string' || !SHA256_RE.test(value)) {
    throw new TypeError(name + ' must be a lowercase SHA-256 hex digest')
  }
}

function assertUtcTimestamp(value: unknown, name: string): asserts value is string {
  assertNonEmptyString(value, name)
  if (!RFC3339_UTC_RE.test(value)) {
    throw new TypeError(name + ' must use second-precision UTC RFC3339')
  }
  const expectedIso = value.slice(0, -1) + '.000Z'
  const parsed = new Date(value)
  if (Number.isNaN(parsed.getTime()) || parsed.toISOString() !== expectedIso) {
    throw new TypeError(name + ' must be a real UTC calendar timestamp')
  }
}

function assertReportCore(core: unknown): asserts core is EvidenceReportCore {
  assertExactKeys(core, 'core', CORE_KEYS)
  const value = core as Record<string, unknown>

  assertId(value.report_id, 'core.report_id')
  assertNonEmptyString(value.title, 'core.title')
  assertUtcTimestamp(value.generated_at, 'core.generated_at')

  assertExactKeys(value.exact_head, 'core.exact_head', EXACT_HEAD_KEYS)
  const head = value.exact_head as Record<string, unknown>
  assertNonEmptyString(head.repository, 'core.exact_head.repository')
  if (!REPOSITORY_RE.test(head.repository)) {
    throw new TypeError('core.exact_head.repository must use owner/repository form')
  }
  assertNonEmptyString(head.commit_sha, 'core.exact_head.commit_sha')
  if (!GIT_OID_RE.test(head.commit_sha)) {
    throw new TypeError('core.exact_head.commit_sha must be a lowercase 40- or 64-hex git object id')
  }

  assertEnum(value.status, 'core.status', REPORT_STATUSES)
  assertEnum(value.epistemic_tier, 'core.epistemic_tier', EPISTEMIC_TIERS)
  assertEnum(value.admission, 'core.admission', ADMISSION_STATES)
  assertEnum(value.authority_effect, 'core.authority_effect', AUTHORITY_EFFECTS)
  assertNonEmptyString(value.scope, 'core.scope')
  assertNonEmptyString(value.summary, 'core.summary')

  if (!Array.isArray(value.evidence)) throw new TypeError('core.evidence must be an array')
  const evidenceIds = new Set<string>()
  for (let i = 0; i < value.evidence.length; i += 1) {
    const evidence = value.evidence[i]
    assertExactKeys(evidence, 'core.evidence[' + i + ']', EVIDENCE_KEYS)
    const item = evidence as Record<string, unknown>
    assertId(item.evidence_id, 'core.evidence[' + i + '].evidence_id')
    if (evidenceIds.has(item.evidence_id)) {
      throw new TypeError('duplicate evidence_id: ' + item.evidence_id)
    }
    evidenceIds.add(item.evidence_id)
    assertEnum(item.kind, 'core.evidence[' + i + '].kind', EVIDENCE_KINDS)
    assertNonEmptyString(item.locator, 'core.evidence[' + i + '].locator')
    if (item.sha256 !== undefined) {
      assertSha256(item.sha256, 'core.evidence[' + i + '].sha256')
    }
  }

  if (!Array.isArray(value.claims) || value.claims.length === 0) {
    throw new TypeError('core.claims must contain at least one claim')
  }
  const claimIds = new Set<string>()
  for (let i = 0; i < value.claims.length; i += 1) {
    const claim = value.claims[i]
    assertExactKeys(claim, 'core.claims[' + i + ']', CLAIM_KEYS)
    const item = claim as Record<string, unknown>
    assertId(item.claim_id, 'core.claims[' + i + '].claim_id')
    if (claimIds.has(item.claim_id)) {
      throw new TypeError('duplicate claim_id: ' + item.claim_id)
    }
    claimIds.add(item.claim_id)
    assertNonEmptyString(item.statement, 'core.claims[' + i + '].statement')
    assertEnum(item.status, 'core.claims[' + i + '].status', CLAIM_STATUSES)
    assertStringArray(item.evidence_ids, 'core.claims[' + i + '].evidence_ids')

    if ((item.status === 'VERIFIED' || item.status === 'FALSIFIED') && item.evidence_ids.length === 0) {
      throw new TypeError('verified or falsified claims require evidence_ids')
    }
    const claimEvidenceIds = new Set<string>()
    for (const evidenceId of item.evidence_ids) {
      if (claimEvidenceIds.has(evidenceId)) {
        throw new TypeError('claim contains duplicate evidence_id: ' + evidenceId)
      }
      claimEvidenceIds.add(evidenceId)
      if (!evidenceIds.has(evidenceId)) {
        throw new TypeError('claim references unknown evidence_id: ' + evidenceId)
      }
    }
  }

  assertStringArray(value.limitations, 'core.limitations')
  assertStringArray(value.next_actions, 'core.next_actions')
}

function assertMachineReport(machine: unknown): asserts machine is MachineReportV1 {
  assertExactKeys(machine, 'machine', MACHINE_KEYS)
  const value = machine as Record<string, unknown>
  if (value.format !== DUAL_REPORT_FORMAT) throw new TypeError('machine.format mismatch')
  if (value.report_version !== DUAL_REPORT_VERSION) throw new TypeError('machine.report_version mismatch')
  if (value.canonicalization !== DUAL_REPORT_CANONICALIZATION) {
    throw new TypeError('machine.canonicalization mismatch')
  }
  assertReportCore(value.core)
  assertExactKeys(value.integrity, 'machine.integrity', INTEGRITY_KEYS)
  const integrity = value.integrity as Record<string, unknown>
  assertSha256(integrity.core_sha256, 'machine.integrity.core_sha256')
  assertSha256(integrity.human_sha256, 'machine.integrity.human_sha256')
}

function inline(value: string): string {
  return value.replace(/\s+/g, ' ').trim()
}

function renderHumanProjection(core: Readonly<EvidenceReportCore>, coreSha256: SHA256Hex): string {
  const lines: string[] = [
    '# ' + inline(core.title),
    '',
    'Report ID: ' + core.report_id,
    'Generated: ' + core.generated_at,
    'Status: ' + core.status,
    'Epistemic tier: ' + core.epistemic_tier,
    'Admission: ' + core.admission,
    'Authority effect: ' + core.authority_effect,
    'Exact head: ' + core.exact_head.repository + '@' + core.exact_head.commit_sha,
    'Scope: ' + inline(core.scope),
    '',
    '## Summary',
    '',
    inline(core.summary),
    '',
    '## Claims',
    '',
  ]

  core.claims.forEach((claim, index) => {
    lines.push(
      String(index + 1) + '. [' + claim.status + '] ' + claim.claim_id + ': ' + inline(claim.statement)
    )
    lines.push('   Evidence: ' + (claim.evidence_ids.length > 0 ? claim.evidence_ids.join(', ') : 'none'))
  })

  lines.push('', '## Evidence', '')
  if (core.evidence.length === 0) {
    lines.push('- None recorded.')
  } else {
    for (const evidence of core.evidence) {
      let line = '- ' + evidence.evidence_id + ' | ' + evidence.kind + ' | ' + inline(evidence.locator)
      if (evidence.sha256 !== undefined) line += ' | sha256=' + evidence.sha256
      lines.push(line)
    }
  }

  lines.push('', '## Limitations', '')
  if (core.limitations.length === 0) {
    lines.push('- None recorded.')
  } else {
    for (const limitation of core.limitations) lines.push('- ' + inline(limitation))
  }

  lines.push('', '## Next actions', '')
  if (core.next_actions.length === 0) {
    lines.push('- None recorded.')
  } else {
    for (const action of core.next_actions) lines.push('- ' + inline(action))
  }

  lines.push(
    '',
    '## Integrity binding',
    '',
    'Canonicalization: ' + DUAL_REPORT_CANONICALIZATION,
    'Core SHA-256: ' + coreSha256,
    'Projection rule: this human report is deterministically rendered from the machine core.',
    'Boundary: the binding proves internal consistency; external evidence still requires its own verifier.',
    ''
  )

  return lines.join('\n')
}

export async function renderHumanReport(core: EvidenceReportCore): Promise<string> {
  assertReportCore(core)
  const cloned = structuredClone(core)
  assertReportCore(cloned)
  const frozenCore = deepFreeze(cloned) as Readonly<EvidenceReportCore>
  const coreSha256 = await hashValue(frozenCore)
  return renderHumanProjection(frozenCore, coreSha256)
}

export async function buildDualReport(core: EvidenceReportCore): Promise<BuiltDualReport> {
  assertReportCore(core)

  const cloned = structuredClone(core)
  assertReportCore(cloned)
  const frozenCore = deepFreeze(cloned) as Readonly<EvidenceReportCore>

  const coreSha256 = await hashValue(frozenCore)
  const human = renderHumanProjection(frozenCore, coreSha256)
  const humanSha256 = await hashString(human)

  const machine = deepFreeze({
    format: DUAL_REPORT_FORMAT,
    report_version: DUAL_REPORT_VERSION,
    canonicalization: DUAL_REPORT_CANONICALIZATION,
    core: frozenCore,
    integrity: {
      core_sha256: coreSha256,
      human_sha256: humanSha256,
    },
  }) as Readonly<MachineReportV1>

  return deepFreeze({ machine, human }) as Readonly<BuiltDualReport>
}

export async function verifyDualReport(machine: unknown, human: string): Promise<DualReportVerification> {
  try {
    assertMachineReport(machine)
  } catch (error) {
    return {
      ok: false,
      code: 'INVALID_REPORT',
      detail: error instanceof Error ? error.message : 'unknown report validation error',
    }
  }

  const actualCoreSha256 = await hashValue(machine.core)
  if (actualCoreSha256 !== machine.integrity.core_sha256) {
    return {
      ok: false,
      code: 'CORE_DIGEST_MISMATCH',
      detail: 'machine core does not match its bound SHA-256 digest',
    }
  }

  const expectedHuman = renderHumanProjection(machine.core, actualCoreSha256)
  if (human !== expectedHuman) {
    return {
      ok: false,
      code: 'HUMAN_RENDER_MISMATCH',
      detail: 'human projection is not the deterministic rendering of the machine core',
    }
  }

  const actualHumanSha256 = await hashString(human)
  if (actualHumanSha256 !== machine.integrity.human_sha256) {
    return {
      ok: false,
      code: 'HUMAN_DIGEST_MISMATCH',
      detail: 'human projection does not match its bound SHA-256 digest',
    }
  }

  return {
    ok: true,
    code: 'VERIFIED',
    detail: 'machine and human projections are bound to one validated evidence core',
  }
}
