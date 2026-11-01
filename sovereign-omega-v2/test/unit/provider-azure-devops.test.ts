import { describe, expect, it } from 'vitest'
import {
  observeAzureDevOpsJobV1, type AzureDevOpsJobEvidenceV1,
} from '../../src/sovereignty/provider-adapters/azure-devops.js'
import {
  buildProviderMeshSnapshotV1, selectProviderV1, DECLARED_PROVIDER_CATALOG_V1,
} from '../../src/sovereignty/provider-mesh.js'

// HYPOTHETICAL fixture only. No actual Azure project, pipeline, or run is claimed.
const exampleHead='69cbb9b398c8fe036ed340e37fb630872d8c0706'
const sample: AzureDevOpsJobEvidenceV1={
  requested_organization:'aegisomega',run_organization:'aegisomega',
  requested_project:'AEGIS-OMEGA',run_project:'AEGIS-OMEGA',
  requested_pipeline_id:'14',run_pipeline_id:'14',
  run_id:'25',timeline_build_id:'25',
  expected_head_sha:exampleHead,run_repository_version:exampleHead,
  run_state:'completed',run_result:'succeeded',
  timeline_record_type:'Job',timeline_job_state:'completed',
  timeline_job_result:'succeeded',worker_name:'linux-runner',
  job_started_at:'2026-10-31T06:00:00Z',
  job_finished_at:'2026-10-31T06:01:00Z',
}
const observe=(patch:Partial<AzureDevOpsJobEvidenceV1>={},generation='42')=>
  observeAzureDevOpsJobV1({...sample,...patch},generation)
describe('Azure DevOps exact-source pipeline + timeline evidence adapter',()=>{
  it('hypothetically proves only runner availability, not authority',async()=>{
    const r=await observe()
    expect(r.state).toBe('OBSERVED_AVAILABLE')
    expect(r.provider_id).toBe('azure-devops-pipelines')
    expect(r.authority_effect).toBe('NONE')
    expect(r.observed_capabilities).toEqual(['DURABLE_RUNNER','REPOSITORY_WORKFLOW'])
    expect(r.evidence_hash).toMatch(/^[0-9a-f]{64}$/)
  })
  it('never promotes an executed historical run to another requested commit',async()=>{
    const r=await observe({expected_head_sha:'a'.repeat(40)})
    expect(r.state).toBe('UNKNOWN')
    expect(r.observed_capabilities).toEqual([])
    const mesh=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[r])
    const selected=await selectProviderV1(mesh,{
      required_capabilities:['REPOSITORY_WORKFLOW'],allowed_providers:['azure-devops-pipelines'],
      current_generation:'42',max_observation_age_generations:'0',
    })
    expect(selected.outcome).toBe('DENIED')
    expect(selected.authority_effect).toBe('NONE')
  })
  it('rejects wrong project or organization binding',async()=>{
    expect((await observe({requested_project:'OTHER'})).state).toBe('UNKNOWN')
    expect((await observe({run_organization:'other'})).state).toBe('UNKNOWN')
  })
  it('rejects mismatched pipeline and timeline build IDs',async()=>{
    expect((await observe({run_pipeline_id:'15'})).state).toBe('UNKNOWN')
    expect((await observe({timeline_build_id:'26'})).state).toBe('UNKNOWN')
  })
  it('rejects running, canceled and skipped execution',async()=>{
    for(const patch of [
      {run_state:'inProgress'}, {run_result:'canceled'},
      {timeline_job_state:'inProgress'}, {timeline_job_result:'skipped'},
      {timeline_record_type:'Task'},
    ] as const) expect((await observe(patch)).state).toBe('UNKNOWN')
  })
  it('requires an actual worker name and completed job timestamps',async()=>{
    for(const patch of [
      {worker_name:null}, {worker_name:' '},
      {job_started_at:null},{job_finished_at:null},
    ]) expect((await observe(patch)).state).toBe('UNKNOWN')
  })
  it('executed failed workload is still runner-substrate evidence',async()=>{
    expect((await observe({run_result:'failed',timeline_job_result:'failed'})).state)
      .toBe('OBSERVED_AVAILABLE')
  })
  it('rejects coerced numeric IDs and forged string-like Git SHAs',async()=>{
    await expect(observe({run_id:25 as never})).rejects.toThrow('run_id')
    await expect(observe({expected_head_sha:({toString:()=>exampleHead}) as never}))
      .rejects.toThrow('expected_head_sha')
    await expect(observeAzureDevOpsJobV1(sample,42 as never))
      .rejects.toThrow('observation_generation')
  })
  it('rejects malformed or reversed timestamps',async()=>{
    await expect(observe({job_started_at:'2026-10-31'})).rejects.toThrow('job_started_at')
    await expect(observe({job_finished_at:'2026-10-31T05:00:00Z'}))
      .rejects.toThrow('job_finished_at')
  })
  it('rejects impossible UTC calendar dates that JavaScript normalizes',async()=>{
    for (const impossible of [
      '2026-02-30T06:00:00Z',
      '2025-02-29T00:00:00Z',
      '2026-04-31T00:00:00Z',
    ]) {
      await expect(observe({job_started_at:impossible,job_finished_at:'2027-01-01T00:00:00Z'}))
        .rejects.toThrow('job_started_at')
      await expect(observe({job_started_at:'2024-01-01T00:00:00Z',job_finished_at:impossible}))
        .rejects.toThrow('job_finished_at')
    }
    const leap=await observe({
      job_started_at:'2024-02-29T00:00:00Z',
      job_finished_at:'2024-02-29T00:00:00.123456Z',
    })
    expect(leap.state).toBe('OBSERVED_AVAILABLE')
  })
  it('rejects sub-millisecond reversed job durations including nanoseconds',async()=>{
    for (const [start,finish] of [
      ['2026-10-31T06:00:00.0009Z','2026-10-31T06:00:00.0001Z'],
      ['2026-10-31T06:00:00.123456Z','2026-10-31T06:00:00.123455Z'],
      ['2026-10-31T06:00:00.123456789Z','2026-10-31T06:00:00.123456788Z'],
    ]) {
      await expect(observe({job_started_at:start,job_finished_at:finish}))
        .rejects.toThrow('job_finished_at')
    }
    expect((await observe({
      job_started_at:'2026-10-31T06:00:00.100000Z',
      job_finished_at:'2026-10-31T06:00:00.1Z',
    })).state).toBe('OBSERVED_AVAILABLE')
    expect((await observe({
      job_started_at:'2026-10-31T06:00:00.999999Z',
      job_finished_at:'2026-10-31T06:00:01.000001Z',
    })).state).toBe('OBSERVED_AVAILABLE')
  })
  it('compares supplied femtosecond fractions without Date.parse truncation',async()=>{
    await expect(observe({
      job_started_at:'2026-10-31T06:00:00.000000000000001Z',
      job_finished_at:'2026-10-31T06:00:00.000000000000000Z',
    })).rejects.toThrow('job_finished_at')
    const forward=await observe({
      job_started_at:'2026-10-31T06:00:00.000000000000000Z',
      job_finished_at:'2026-10-31T06:00:00.000000000000001Z',
    })
    expect(forward.state).toBe('OBSERVED_AVAILABLE')
    expect(forward.authority_effect).toBe('NONE')
    expect((await observe({
      job_started_at:'2026-10-31T06:00:00.999999999999999Z',
      job_finished_at:'2026-10-31T06:00:01.000000000000000Z',
    })).state).toBe('OBSERVED_AVAILABLE')
    expect((await observe({
      job_started_at:'2026-10-31T06:00:00.1Z',
      job_finished_at:'2026-10-31T06:00:00.100000000000000Z',
    })).state).toBe('OBSERVED_AVAILABLE')
  })
  it('rejects fractional evidence beyond the 15-digit precision contract',async()=>{
    await expect(observe({
      job_started_at:'2026-10-31T06:00:00.0000000000000001Z',
    })).rejects.toThrow('job_started_at')
    await expect(observe({
      job_finished_at:'2026-10-31T06:01:00.1234567890123456Z',
    })).rejects.toThrow('job_finished_at')
  })
  it('hashes normalized execution evidence deterministically',async()=>{
    const a=await observe(),b=await observe(),
      c=await observe({run_id:'26',timeline_build_id:'26'})
    expect(a.evidence_hash).toBe(b.evidence_hash)
    expect(a.evidence_hash).not.toBe(c.evidence_hash)
  })
  it('rejects missing Azure records instead of manufacturing availability',async()=>{
    await expect(observeAzureDevOpsJobV1(null as never,'42')).rejects.toThrow('missing Azure')
  })
})
