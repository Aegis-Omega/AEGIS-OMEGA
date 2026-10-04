import { describe, expect, it } from 'vitest'
import type { EvidenceReportCore } from '../../src/reporting/dual-report'
import {
  buildDualReport,
  renderHumanReport,
  verifyDualReport,
} from '../../src/reporting/dual-report'

const MAIN_SHA = '495bfd85d79abcb2b4f6898fe9c156488492426a'

const BASE_CORE: EvidenceReportCore = {
  report_id: 'aegis.dual-report.selftest.v1',
  title: 'AEGIS Dual Report Contract Self-Test',
  generated_at: '2026-10-04T06:58:00Z',
  exact_head: {
    repository: 'Aegis-Omega/AEGIS-OMEGA',
    commit_sha: MAIN_SHA,
  },
  status: 'PASS',
  epistemic_tier: 'T0',
  admission: 'NOT_APPLICABLE',
  authority_effect: 'NONE',
  scope: 'Deterministic machine and human report binding.',
  summary: 'One evidence core must produce one stable machine envelope and one stable human projection.',
  claims: [
    {
      claim_id: 'claim.binding',
      statement: 'The report projections are derived from the same validated evidence core.',
      status: 'VERIFIED',
      evidence_ids: ['evidence.main'],
    },
  ],
  evidence: [
    {
      evidence_id: 'evidence.main',
      kind: 'github_commit',
      locator: 'Aegis-Omega/AEGIS-OMEGA@' + MAIN_SHA,
    },
  ],
  limitations: [
    'The contract proves internal consistency, not independent authenticity of external evidence.',
  ],
  next_actions: [
    'Verify evidence locators with their native verifier before promotion or admission.',
  ],
}

describe('Dual Report Contract V1', () => {
  it('is byte-deterministic for identical evidence cores', async () => {
    const first = await buildDualReport(BASE_CORE)
    const second = await buildDualReport(BASE_CORE)

    expect(first.machine).toEqual(second.machine)
    expect(first.human).toBe(second.human)
  })

  it('binds exact head, machine core, and human projection', async () => {
    const built = await buildDualReport(BASE_CORE)
    const result = await verifyDualReport(built.machine, built.human)

    expect(result).toEqual({
      ok: true,
      code: 'VERIFIED',
      detail: 'machine and human projections are bound to one validated evidence core',
    })
    expect(built.human).toContain('Exact head: Aegis-Omega/AEGIS-OMEGA@' + MAIN_SHA)
    expect(built.human).toContain('Core SHA-256: ' + built.machine.integrity.core_sha256)
  })

  it('freezes the emitted machine artifact and nested core', async () => {
    const built = await buildDualReport(BASE_CORE)

    expect(Object.isFrozen(built.machine)).toBe(true)
    expect(Object.isFrozen(built.machine.core)).toBe(true)
    expect(Object.isFrozen(built.machine.core.claims)).toBe(true)
    expect(Object.isFrozen(built.machine.core.claims[0])).toBe(true)
  })

  it('fails closed when the machine core is tampered after emission', async () => {
    const built = await buildDualReport(BASE_CORE)
    const tampered = structuredClone(built.machine) as unknown as Record<string, unknown>
    const core = tampered.core as Record<string, unknown>
    core.summary = 'tampered summary'

    const result = await verifyDualReport(tampered, built.human)
    expect(result.ok).toBe(false)
    expect(result.code).toBe('CORE_DIGEST_MISMATCH')
  })

  it('fails closed when the human projection is edited independently', async () => {
    const built = await buildDualReport(BASE_CORE)
    const result = await verifyDualReport(built.machine, built.human + 'tampered\n')

    expect(result.ok).toBe(false)
    expect(result.code).toBe('HUMAN_RENDER_MISMATCH')
  })

  it('rejects verified claims without evidence', async () => {
    const invalid: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      claims: [
        {
          claim_id: 'claim.no-evidence',
          statement: 'This cannot be verified without evidence.',
          status: 'VERIFIED',
          evidence_ids: [],
        },
      ],
    }

    await expect(buildDualReport(invalid)).rejects.toThrow('verified or falsified claims require evidence_ids')
  })

  it('rejects claims that reference unknown evidence ids', async () => {
    const invalid: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      claims: [
        {
          claim_id: 'claim.bad-ref',
          statement: 'This references evidence that is not present.',
          status: 'VERIFIED',
          evidence_ids: ['evidence.missing'],
        },
      ],
    }

    await expect(buildDualReport(invalid)).rejects.toThrow('unknown evidence_id')
  })

  it('rejects duplicate claim and evidence identifiers', async () => {
    const duplicateEvidence: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      evidence: [
        ...BASE_CORE.evidence,
        structuredClone(BASE_CORE.evidence[0]!),
      ],
    }
    await expect(buildDualReport(duplicateEvidence)).rejects.toThrow('duplicate evidence_id')

    const duplicateClaim: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      claims: [
        ...BASE_CORE.claims,
        structuredClone(BASE_CORE.claims[0]!),
      ],
    }
    await expect(buildDualReport(duplicateClaim)).rejects.toThrow('duplicate claim_id')
  })

  it('rejects malformed or uppercase exact-head identifiers', async () => {
    for (const commitSha of ['deadbeef', MAIN_SHA.toUpperCase()]) {
      const invalid: EvidenceReportCore = {
        ...structuredClone(BASE_CORE),
        exact_head: {
          ...BASE_CORE.exact_head,
          commit_sha: commitSha,
        },
      }
      await expect(buildDualReport(invalid)).rejects.toThrow('git object id')
    }
  })

  it('allows unverified claims without evidence while keeping them explicit', async () => {
    const core: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      claims: [
        {
          claim_id: 'claim.open',
          statement: 'This statement is intentionally still open.',
          status: 'UNVERIFIED',
          evidence_ids: [],
        },
      ],
      evidence: [],
    }

    const built = await buildDualReport(core)
    expect(built.human).toContain('[UNVERIFIED] claim.open')
    expect((await verifyDualReport(built.machine, built.human)).ok).toBe(true)
  })

  it('normalizes line breaks only in the human projection, never in the machine core', async () => {
    const core: EvidenceReportCore = {
      ...structuredClone(BASE_CORE),
      summary: 'line one\nline two',
    }
    const built = await buildDualReport(core)

    expect(built.machine.core.summary).toBe('line one\nline two')
    expect(built.human).toContain('line one line two')
    expect(built.human).not.toContain('line one\nline two')
  })

  it('rejects unsupported envelope versions before digest verification', async () => {
    const built = await buildDualReport(BASE_CORE)
    const tampered = structuredClone(built.machine) as unknown as Record<string, unknown>
    tampered.report_version = '9.9.9'

    const result = await verifyDualReport(tampered, built.human)
    expect(result.ok).toBe(false)
    expect(result.code).toBe('INVALID_REPORT')
  })

  it('renders a stable human projection from an already-validated core', async () => {
    const built = await buildDualReport(BASE_CORE)
    const rerendered = renderHumanReport(
      built.machine.core,
      built.machine.integrity.core_sha256
    )

    expect(rerendered).toBe(built.human)
  })
})
