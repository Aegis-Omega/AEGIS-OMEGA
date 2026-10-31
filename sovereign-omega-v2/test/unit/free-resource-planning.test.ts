import { describe, expect, it } from 'vitest'
import { buildProviderMeshSnapshotV1, DECLARED_PROVIDER_CATALOG_V1, PROVIDER_MESH_SCHEMA_VERSION, type ProviderObservationV1 } from '../../src/sovereignty/provider-mesh.js'
import { planFreeResourceV1, freeResourceEvidenceRootV1, type FreeResourceEvidenceV1 } from '../../src/sovereignty/free-resource-planning.js'

const obs: ProviderObservationV1 = {
  schema_version: PROVIDER_MESH_SCHEMA_VERSION, provider_id: 'cloudflare-anthropic',
  state: 'OBSERVED_AVAILABLE', observed_capabilities: ['MODEL_INFERENCE'],
  observation_generation: '10', evidence_hash: 'a'.repeat(64) as ProviderObservationV1['evidence_hash'], authority_effect: 'NONE',
}
const req = {required_capabilities: ['MODEL_INFERENCE'] as const, current_generation:'10', max_observation_age_generations:'1', unit:'NEURON' as const, worst_case_units:'100'}
const snapshot = () => buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [obs])
async function witness(patch: Partial<Omit<FreeResourceEvidenceV1,'evidence_root'>> = {}): Promise<FreeResourceEvidenceV1> {
  const currentSnapshot = await snapshot()
  const body = {provider_id:'cloudflare-anthropic', source_id:'synthetic-provider-billing-read',
    observation_generation:'10', snapshot_root:currentSnapshot.snapshot_root,
    observation_evidence_hash:obs.evidence_hash,
    unit:'NEURON' as const, remaining_units:'200',
    billing_mode:'FREE_ONLY' as const, overage:'HARD_DENY' as const, ...patch}
  return {...body, evidence_root:await freeResourceEvidenceRootV1(body)}
}
describe('zero-spend resource planning, no execution authority', () => {
  it('holds when quota evidence is absent', async () => {
    const x=await planFreeResourceV1(await snapshot(),req,[],[])
    expect(x.outcome).toBe('HOLD');expect(x.provider_id).toBeNull();expect(x.authority_effect).toBe('NONE')
  })
  it('holds untrusted quota evidence', async () => {
    const w=await witness();expect((await planFreeResourceV1(await snapshot(),req,[w],[])).outcome).toBe('HOLD')
  })
  it('allows evidence-bound planning only with a trusted hard-limit-free root', async () => {
    const w=await witness();const x=await planFreeResourceV1(await snapshot(),req,[w],[w.evidence_root])
    expect(x.outcome).toBe('PLANNING_ELIGIBLE');expect(x.provider_id).toBe(w.provider_id)
    expect(x.capacity_root).toBe(w.evidence_root);expect(x.selection.outcome).toBe('SELECTED')
  })
  it('rejects possible overage, unknown tier and insufficient free capacity', async () => {
    for(const p of [{overage:'POSSIBLE' as const},{billing_mode:'UNKNOWN' as const},{remaining_units:'99'}]){
      const w=await witness(p);expect((await planFreeResourceV1(await snapshot(),req,[w],[w.evidence_root])).outcome).toBe('HOLD')
    }
  })
  it('rejects stale, future, wrong-unit and nonmatching source generation', async () => {
    for(const p of [{observation_generation:'8'},{observation_generation:'11'},{unit:'TOKEN' as const}]){
      const w=await witness(p);expect((await planFreeResourceV1(await snapshot(),req,[w],[w.evidence_root])).outcome).toBe('HOLD')
    }
  })
  it('cannot gain authority by falsifying remaining units after attestation', async () => {
    const w=await witness()
    await expect(planFreeResourceV1(await snapshot(),req,[{...w,remaining_units:'999999'}],[w.evidence_root]))
      .rejects.toThrow('evidence root mismatch')
  })
  it('rejects duplicate evidence, zero consumption and invalid quota', async () => {
    const w=await witness()
    await expect(planFreeResourceV1(await snapshot(),req,[w,w],[w.evidence_root])).rejects.toThrow('duplicate')
    await expect(planFreeResourceV1(await snapshot(),{...req,worst_case_units:'0'},[],[])).rejects.toThrow('positive')
    const invalid=await witness({remaining_units:'-1'})
    await expect(planFreeResourceV1(await snapshot(),req,[invalid],[invalid.evidence_root])).rejects.toThrow('canonical unsigned decimal')
  })
  it('holds approved capacity when provider observation hash changes at the same generation', async () => {
    const w = await witness()
    const changed = await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1, [
      {...obs,evidence_hash:('b'.repeat(64) as ProviderObservationV1['evidence_hash'])},
    ])
    const result=await planFreeResourceV1(changed,req,[w],[w.evidence_root])
    expect(result.outcome).toBe('HOLD')
    expect(result.capacity_root).toBeNull()
  })
  it('holds when an approved witness targets another snapshot root', async () => {
    const w=await witness({snapshot_root:obs.evidence_hash})
    const result=await planFreeResourceV1(await snapshot(),req,[w],[w.evidence_root])
    expect(result.outcome).toBe('HOLD')
  })
  it('holds when witness observation hash is unrelated despite matching provider and generation', async () => {
    const expectedSnapshot=await snapshot()
    const w=await witness({observation_evidence_hash:expectedSnapshot.snapshot_root})
    expect((await planFreeResourceV1(expectedSnapshot,req,[w],[w.evidence_root])).outcome).toBe('HOLD')
  })
  it('holds approved legacy evidence without snapshot/observation binding', async () => {
    const w=await witness()
    const {evidence_root:_oldRoot,snapshot_root:_snapshotRoot,observation_evidence_hash:_observationHash,...legacy}=w
    const past={...legacy,evidence_root:await freeResourceEvidenceRootV1(legacy)}
    const result=await planFreeResourceV1(await snapshot(),req,[past],[past.evidence_root])
    expect(result.outcome).toBe('HOLD')
  })
  it('rejects tampering with attested snapshot binding after approval', async () => {
    const w=await witness()
    const tampered={...w,snapshot_root:obs.evidence_hash}
    await expect(planFreeResourceV1(await snapshot(),req,[tampered],[w.evidence_root]))
      .rejects.toThrow('evidence root mismatch')
  })
  it('respects capability gate and root revocation', async () => {
    const w=await witness()
    expect((await planFreeResourceV1(await snapshot(),{...req,required_capabilities:['GPU_COMPUTE']},[w],[w.evidence_root])).outcome).toBe('HOLD')
    expect((await planFreeResourceV1(await snapshot(),req,[w],[])).outcome).toBe('HOLD')
  })
})
