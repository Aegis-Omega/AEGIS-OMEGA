import { describe, expect, it } from 'vitest'
import { observeConnectedResourcesV1, type ConnectedResourceReadsV1 } from '../../src/sovereignty/connected-resource-intake.js'

function fixture(): ConnectedResourceReadsV1 {
  return {
    observation_generation: '23',
    cloudflare: {
      ai_gateway_credit_balance: {status:200, success:true, result:{balance:0,has_default_payment_method:false,topup_config:{threshold:0,amount:0}}},
      ai_gateway_topup_config: {status:200, success:true, result:{threshold:0,amount:0}},
      worker_account_settings: {status:200, success:true, result:{default_usage_model:'standard',green_compute:false}},
      worker_scripts: {status:200, success:true, result:['aegisomega']},
    },
    hugging_face: {account_plan:'FREE', jobs_total:0},
  }
}

describe('connected provider resource reads cannot mint free quota authority', () => {
  it('observes actual account-shape facts without claiming free inference', async () => {
    const r=await observeConnectedResourcesV1(fixture())
    expect(r.cloudflare.ai_gateway_prepaid).toBe('ZERO_CONFIRMED')
    expect(r.cloudflare.ai_gateway_auto_topup).toBe('OFF_CONFIRMED')
    expect(r.cloudflare.worker_usage_model).toBe('STANDARD')
    expect(r.cloudflare.worker_script_count).toBe(1)
    expect(r.cloudflare.workers_ai_free_quota).toBe('UNKNOWN')
    expect(r.hugging_face.jobs_total).toBe(0)
    expect(r.hugging_face.free_gpu_quota).toBe('UNKNOWN')
    expect(r.zero_spend_admission).toBe('HOLD')
    expect(r.authority_effect).toBe('NONE')
    expect(r.integrity_root).toMatch(/^[0-9a-f]{64}$/)
  })
  it('remains HOLD on positive prepaid balance: prepaid is not free', async () => {
    const f=fixture();f.cloudflare.ai_gateway_credit_balance={status:200,success:true,result:{balance:50}}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.ai_gateway_prepaid).toBe('POSITIVE_NOT_FREE')
    expect(r.zero_spend_admission).toBe('HOLD')
  })
  it('ignores fabricated success payload on HTTP errors', async () => {
    const f=fixture();f.cloudflare.ai_gateway_credit_balance={status:403,success:false,result:{balance:100}}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.ai_gateway_prepaid).toBe('UNKNOWN')
  })
  it('does not assume the top-up is off if the dedicated read fails', async () => {
    const f=fixture();f.cloudflare.ai_gateway_topup_config={status:403,success:false,result:{threshold:0,amount:0}}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.ai_gateway_auto_topup).toBe('UNKNOWN')
  })
  it('does not promote unknown or potentially enabled auto topup', async () => {
    const f=fixture();f.cloudflare.ai_gateway_topup_config={status:200,success:true,result:{threshold:1,amount:5}}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.ai_gateway_auto_topup).toBe('POSSIBLE')
    expect(r.zero_spend_admission).toBe('HOLD')
  })
  it('parses Cloudflare native Worker objects without treating them as free quota', async () => {
    const f=fixture();f.cloudflare.worker_scripts={status:200,success:true,result:[{id:'aegisomega',created_on:'2026-01-01T00:00:00Z'}]}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.worker_script_count).toBe(1)
    expect(r.cloudflare.workers_ai_free_quota).toBe('UNKNOWN')
    expect(r.zero_spend_admission).toBe('HOLD')
  })
  it('does not infer Workers quota from a listed Worker script', async () => {
    const f=fixture();f.cloudflare.worker_scripts={status:200,success:true,result:['alpha','beta']}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.worker_script_count).toBe(2)
    expect(r.cloudflare.workers_ai_free_quota).toBe('UNKNOWN')
  })
  it('does not infer HF GPU quota from empty jobs', async () => {
    const f=fixture();f.hugging_face.jobs_total=0
    const r=await observeConnectedResourcesV1(f)
    expect(r.hugging_face.free_gpu_quota).toBe('UNKNOWN')
  })
  it('returns UNKNOWN if any Cloudflare reads are missing', async () => {
    const f=fixture();f.cloudflare={ai_gateway_credit_balance:null,ai_gateway_topup_config:null,worker_account_settings:null,worker_scripts:null}
    const r=await observeConnectedResourcesV1(f)
    expect(r.cloudflare.ai_gateway_prepaid).toBe('UNKNOWN')
    expect(r.cloudflare.ai_gateway_auto_topup).toBe('UNKNOWN')
    expect(r.cloudflare.worker_script_count).toBeNull()
    expect(r.zero_spend_admission).toBe('HOLD')
  })
  it('rejects malformed generation and job counts', async () => {
    const f=fixture();f.observation_generation='01'
    await expect(observeConnectedResourcesV1(f)).rejects.toThrow('canonical unsigned decimal')
    const g=fixture();g.hugging_face.jobs_total=-1
    await expect(observeConnectedResourcesV1(g)).rejects.toThrow('nonnegative')
  })
  it('hashes only whitelisted, harmless account facts', async () => {
    const f=fixture()
    const a=await observeConnectedResourcesV1(f)
    f.cloudflare.ai_gateway_credit_balance={status:200,success:true,result:{balance:0,api_key:'PRIVATE_VALUE_DO_NOT_EMIT'}}
    const b=await observeConnectedResourcesV1(f)
    expect(JSON.stringify(b)).not.toContain('PRIVATE_VALUE_DO_NOT_EMIT')
    expect(a.integrity_root).toBe(b.integrity_root)
  })
  it('changes the deterministic integrity root when a genuine fact changes', async () => {
    const a=await observeConnectedResourcesV1(fixture())
    const f=fixture();f.hugging_face.jobs_total=2
    const b=await observeConnectedResourcesV1(f)
    expect(a.integrity_root).not.toBe(b.integrity_root)
  })
})
