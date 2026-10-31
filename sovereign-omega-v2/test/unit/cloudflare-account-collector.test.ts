import { describe, expect, it, vi } from 'vitest'
import {
  collectCloudflareAccountResourcesV1,
  type CloudflareReadOnlyFetchV1,
} from '../../src/sovereignty/cloudflare-account-collector.js'

const account_id='abcdef0123456789abcdef0123456789'
const api_token='test-only-secret-DO-NOT-LOG'
const generation='42'
const endpoints=[
  '/ai-gateway/billing/credit-balance',
  '/ai-gateway/billing/topup/config',
  '/workers/account-settings',
  '/workers/scripts',
]
function collector(responses: unknown[], statuses: number[]=[200,200,200,200]) {
  let index=0
  const fetch_read=vi.fn(async (_url:string, _init: RequestInit) => {
    const i=index++
    return {
      status:statuses[i] ?? 0,
      json:async () => responses[i],
    }
  })
  return fetch_read
}
function normal() {
  return [
    {success:true,result:{balance:0,token:'NEVER_EXPOSED',has_default_payment_method:false}},
    {success:true,result:{threshold:0,amount:0,debugSecret:'NO_OUTPUT'}},
    {success:true,result:{default_usage_model:'standard',apiKey:'NEVER_EXPOSED'}},
    {success:true,result:[{id:'aegisomega',secret:'NEVER_EXPOSED'}]},
  ]
}
const execute=async (fetch_read: CloudflareReadOnlyFetchV1) =>
  collectCloudflareAccountResourcesV1({account_id,api_token,observation_generation:generation,fetch_read})

describe('Cloudflare read-only collector for AEGIS Resource Mesh', () => {
  it('fetches exactly four fixed, HTTPS account GETs with redirect blocked', async () => {
    const fetch_read=collector(normal())
    const result=await execute(fetch_read)
    expect(fetch_read).toHaveBeenCalledTimes(4)
    for(const [index, path] of endpoints.entries()) {
      const [url,init] = fetch_read.mock.calls[index]!
      expect(url).toBe('https://api.cloudflare.com/client/v4/accounts/'+account_id+path)
      expect(init.method).toBe('GET')
      expect(init.redirect).toBe('error')
      expect((init.headers as Record<string,string>).Authorization).toBe('Bearer '+api_token)
      expect(init.body).toBeUndefined()
    }
    expect(result.methods).toEqual(['GET'])
    expect(result.endpoints).toEqual(endpoints)
    expect(result.inventory.cloudflare.ai_gateway_prepaid).toBe('ZERO_CONFIRMED')
    expect(result.inventory.cloudflare.ai_gateway_auto_topup).toBe('OFF_CONFIRMED')
    expect(result.inventory.cloudflare.worker_script_count).toBe(1)
    expect(result.inventory.cloudflare.workers_ai_free_quota).toBe('UNKNOWN')
    expect(result.inventory.zero_spend_admission).toBe('HOLD')
    expect(result.authority_effect).toBe('NONE')
  })
  it('does not include credentials, raw account id or upstream secrets in the result', async () => {
    const result=await execute(collector(normal()))
    const encoded=JSON.stringify(result)
    expect(encoded).not.toContain(api_token)
    expect(encoded).not.toContain(account_id)
    expect(encoded).not.toContain('NEVER_EXPOSED')
    expect(encoded).not.toContain('NO_OUTPUT')
    expect(result.account_fingerprint).toMatch(/^[0-9a-f]{64}$/)
  })
  it('is deterministic for equivalent API observations', async () => {
    const a=await execute(collector(normal()))
    const b=await execute(collector(normal()))
    expect(a.collector_root).toBe(b.collector_root)
  })
  it('keeps 403/401 account permissions UNKNOWN; does not treat errors as credits', async () => {
    const f=collector(normal(),[403,401,200,200])
    const r=await execute(f)
    expect(r.inventory.cloudflare.ai_gateway_prepaid).toBe('UNKNOWN')
    expect(r.inventory.cloudflare.ai_gateway_auto_topup).toBe('UNKNOWN')
    expect(r.inventory.zero_spend_admission).toBe('HOLD')
  })
  it('rejects redirects or invalid JSON without leaking response payloads', async () => {
    const f=vi.fn(async (_url:string,_init:RequestInit)=>({
      status:200,
      json:async()=>{throw Error('sensitive upstream parse payload')},
    }))
    const r=await execute(f)
    expect(r.inventory.cloudflare.ai_gateway_prepaid).toBe('UNKNOWN')
    expect(JSON.stringify(r)).not.toContain('sensitive upstream')
  })
  it('rejects malicious account identifiers before any request', async () => {
    const f=collector(normal())
    for(const bad of ['../../../ai/run','',account_id+'/run','not-a-hex-account-id']){
      await expect(collectCloudflareAccountResourcesV1({
        account_id:bad,api_token,observation_generation:generation,fetch_read:f,
      })).rejects.toThrow('32 hex')
    }
    expect(f).not.toHaveBeenCalled()
  })
  it('rejects invalid or empty credential before requests', async () => {
    const f=collector(normal())
    for(const bad of ['', 'token with whitespace', 'token\nnewline']){
      await expect(collectCloudflareAccountResourcesV1({
        account_id,api_token:bad,observation_generation:generation,fetch_read:f,
      })).rejects.toThrow('credential')
    }
    expect(f).not.toHaveBeenCalled()
  })
  it('does not infer free Workers AI neuron balance from AI Gateway prepaid credit', async () => {
    const f=normal();f[0]={success:true,result:{balance:100000,token:'NEVER_EXPOSED',has_default_payment_method:false}}
    const r=await execute(collector(f))
    expect(r.inventory.cloudflare.ai_gateway_prepaid).toBe('POSITIVE_NOT_FREE')
    expect(r.inventory.cloudflare.workers_ai_free_quota).toBe('UNKNOWN')
    expect(r.inventory.zero_spend_admission).toBe('HOLD')
  })
  it('fails closed on network failure while still producing a safe inventory', async () => {
    const fetch_read=vi.fn(async () => {throw new Error('untrusted network failure and token')})
    const r=await execute(fetch_read)
    expect(fetch_read).toHaveBeenCalledTimes(4)
    expect(r.inventory.cloudflare.worker_script_count).toBeNull()
    expect(r.inventory.zero_spend_admission).toBe('HOLD')
    expect(JSON.stringify(r)).not.toContain('network failure')
  })
  it('refuses to claim free GPU quota from unrelated account read', async () => {
    const r=await execute(collector(normal()))
    expect(r.inventory.hugging_face.free_gpu_quota).toBe('UNKNOWN')
    expect(r.inventory.hugging_face.jobs_total).toBeNull()
  })
})
