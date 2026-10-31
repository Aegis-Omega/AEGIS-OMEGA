import { describe, expect, it } from 'vitest'
import {
  observeGitLabCiJobV1, type GitLabCiJobEvidenceV1,
} from '../../src/sovereignty/provider-adapters/gitlab-ci.js'
import {
  buildProviderMeshSnapshotV1, selectProviderV1, DECLARED_PROVIDER_CATALOG_V1,
} from '../../src/sovereignty/provider-mesh.js'

// Source-bound values independently read from GitLab project 84781556,
// pipeline 2953906140, job 17223279657 on 2026-10-31.
// These are historical 2026-10-16 receipts, NOT PR #569 exact-head proof.
const historicHead = '69cbb9b398c8fe036ed340e37fb630872d8c0706'
const currentPrHeadAtDiscovery = '6b30c856077c7ab296ba8faa83a87114d84c58da'
const historical: GitLabCiJobEvidenceV1 = {
  project_id: '84781556',
  pipeline_id: '2953906140',
  job_id: '17223279657',
  job_pipeline_id: '2953906140',
  pipeline_head_sha: historicHead,
  job_head_sha: historicHead,
  expected_head_sha: historicHead,
  pipeline_status: 'success',
  job_status: 'success',
  runner_id: 54907241,
  started_at: '2026-10-16T06:23:07.965Z',
  finished_at: '2026-10-16T06:23:41.483Z',
}
const observe = (overrides: Partial<GitLabCiJobEvidenceV1> = {}) =>
  observeGitLabCiJobV1({...historical, ...overrides}, '42')

describe('GitLab CI exact-source evidence adapter', () => {
  it('recognizes executed historical job but gives no execution authority', async () => {
    const r = await observe()
    expect(r.provider_id).toBe('gitlab-ci')
    expect(r.state).toBe('OBSERVED_AVAILABLE')
    expect(r.observed_capabilities).toEqual(['DURABLE_RUNNER','REPOSITORY_WORKFLOW'])
    expect(r.authority_effect).toBe('NONE')
    expect(r.evidence_hash).toMatch(/^[0-9a-f]{64}$/)
  })
  it('refuses to reuse a historical success for the current PR SHA', async () => {
    const r = await observe({expected_head_sha:currentPrHeadAtDiscovery})
    expect(r.state).toBe('UNKNOWN')
    expect(r.observed_capabilities).toEqual([])
    const mesh = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[r])
    const selected = await selectProviderV1(mesh,{
      required_capabilities:['REPOSITORY_WORKFLOW'],
      current_generation:'42',max_observation_age_generations:'0',
      allowed_providers:['gitlab-ci'],
    })
    expect(selected.outcome).toBe('DENIED')
    expect(selected.authority_effect).toBe('NONE')
  })
  it('rejects mismatched pipeline and job association', async () => {
    expect((await observe({job_pipeline_id:'2953906141'})).state).toBe('UNKNOWN')
    expect((await observe({job_head_sha:'a'.repeat(40)})).state).toBe('UNKNOWN')
  })
  it('does not promote pending, running or cancelled pipeline or job', async () => {
    for (const patch of [
      {pipeline_status:'running',job_status:'running'} as const,
      {pipeline_status:'canceled',job_status:'canceled'} as const,
      {pipeline_status:'success',job_status:'skipped'} as const,
    ]) {
      const r = await observe(patch)
      expect(r.state).toBe('UNKNOWN')
      expect(r.observed_capabilities).toEqual([])
    }
  })
  it('rejects phantom runner, missing start or end timestamps', async () => {
    expect((await observe({runner_id:null})).state).toBe('UNKNOWN')
    expect((await observe({runner_id:0})).state).toBe('UNKNOWN')
    expect((await observe({started_at:null})).state).toBe('UNKNOWN')
    expect((await observe({finished_at:null})).state).toBe('UNKNOWN')
  })
  it('recognizes that an executed failed workload still proves runner use', async () => {
    const r = await observe({pipeline_status:'failed',job_status:'failed'})
    expect(r.state).toBe('OBSERVED_AVAILABLE')
    expect(r.authority_effect).toBe('NONE')
  })
  it('rejects string-coercible IDs, SHA values and generations', async () => {
    await expect(observe({job_id:17223279657 as never})).rejects.toThrow('job_id')
    await expect(observe({pipeline_head_sha:({toString:()=>historicHead}) as never})).rejects.toThrow('pipeline_head_sha')
    await expect(observeGitLabCiJobV1(historical,42 as never)).rejects.toThrow('observation_generation')
  })
  it('rejects impossible or malformed runner timestamps', async () => {
    await expect(observe({started_at:'2026-10-16'})).rejects.toThrow('started_at')
    await expect(observe({finished_at:'2026-10-16T06:21:00.000Z'})).rejects.toThrow('finished_at')
    await expect(observe({runner_id:-1})).rejects.toThrow('runner_id')
  })
  it('hashes evidence deterministically without conflating runs', async () => {
    const a=await observe(), b=await observe(), c=await observe({job_id:'17223279658'})
    expect(a.evidence_hash).toBe(b.evidence_hash)
    expect(a.evidence_hash).not.toBe(c.evidence_hash)
  })
})
