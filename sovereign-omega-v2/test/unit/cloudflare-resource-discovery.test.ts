import { describe, expect, it, vi } from 'vitest'
import { discoverCloudflareAccountResourcesV1, type CloudflareDiscoveryRequestV1 } from '../../src/sovereignty/cloudflare-resource-discovery.js'

const account_id='abcdef0123456789abcdef0123456789'
const api_token='TEST_TOKEN_DO_NOT_LEAK'
const generation='24'
function fixture(responseMap?:Record<number, {status:number, json:unknown}>) {
  const defaults=[
    {status:200,json:{success:true,result:[{id:'aegisomega',secret:'not-for-output'}]}},
    {status:200,json:{success:true,result:[],result_info:{total_count:0}}},
    {status:200,json:{success:true,result:[],result_info:{total_count:0}}},
    {status:200,json:{success:true,result:[],result_info:{total_count:0}}},
    {status:200,json:{success:true,result:[]}},
    {status:200,json:{success:true,result:[],result_info:{total_count:0}}},
    {status:403,json:{success:false,errors:[{code:10042,message:'enable R2 via dashboard'}]}},
  ]
  const responses=defaults.map((x,i)=>responseMap?.[i]??x)
  let n=0
  const fetch_read=vi.fn(async (_url:string,_init:RequestInit) => {
    const next=responses[n++]
    if(!next) throw new Error('unexpected request')
    return {status:next.status,json:async()=>next.json}
  })
  const opts:CloudflareDiscoveryRequestV1={account_id,api_token,observation_generation:generation,fetch_read}
  return {fetch_read,opts}
}
describe('Cloudflare account resource discovery (non-authorizing)',()=>{
  it('reads seven fixed endpoints with GET, disabled redirects, no body',async()=>{
    const {opts,fetch_read}=fixture()
    const r=await discoverCloudflareAccountResourcesV1(opts)
    expect(fetch_read).toHaveBeenCalledTimes(7)
    const paths=['/workers/scripts','/d1/database','/pages/projects','/queues',
      '/vectorize/v2/indexes','/ai-gateway/gateways','/r2/buckets']
    for(let i=0;i<7;i++){
      const [url,config]=fetch_read.mock.calls[i]!
      expect(url).toBe('https://api.cloudflare.com/client/v4/accounts/'+account_id+paths[i])
      expect(config.method).toBe('GET');expect(config.redirect).toBe('error');expect(config.body).toBeUndefined()
    }
    expect(r.services.map(s=>s.state)).toEqual([
      'PRESENT','EMPTY','EMPTY','EMPTY','EMPTY','EMPTY','SETUP_REQUIRED',
    ])
    expect(r.services[0]?.observed_first_page_count).toBe(1)
    expect(r.routing_authority).toBe('NONE');expect(r.cost_authority).toBe('NONE')
    expect(r.free_quota_verified).toBe(false)
  })
  it('excludes credentials, account ids, upstream names, and error messages',async()=>{
    const {opts}=fixture()
    const r=await discoverCloudflareAccountResourcesV1(opts)
    const json=JSON.stringify(r)
    for(const secret of [api_token,account_id,'aegisomega','not-for-output','enable R2 via dashboard']){
      expect(json).not.toContain(secret)
    }
    expect(r.evidence_root).toMatch(/^[0-9a-f]{64}$/)
  })
  it('distinguishes R2 setup-required from generic 403',async()=>{
    const {opts}=fixture({6:{status:403,json:{success:false,errors:[{code:10100}]}}})
    expect((await discoverCloudflareAccountResourcesV1(opts)).services[6]?.state).toBe('UNKNOWN')
  })
  it('never calls JSON on unrelated error statuses or redirects',async()=>{
    const {opts}=fixture({0:{status:302,json:{success:true,result:[{id:'FAKE'}]}},1:{status:403,json:{success:true,result:[]}}})
    const result=await discoverCloudflareAccountResourcesV1(opts)
    expect(result.services[0]?.state).toBe('UNKNOWN')
    expect(result.services[1]?.state).toBe('UNKNOWN')
  })
  it('keeps contradictory total count unknown, never silently empty',async()=>{
    const {opts}=fixture({1:{status:200,json:{success:true,result:[],result_info:{total_count:3}}}})
    const r=await discoverCloudflareAccountResourcesV1(opts)
    expect(r.services[1]?.state).toBe('UNKNOWN')
  })
  it('preserves first-page evidence without pretending it is the complete inventory',async()=>{
    const {opts}=fixture({1:{status:200,json:{success:true,result:[{id:1},{id:2}],result_info:{total_count:250}}}})
    const x=(await discoverCloudflareAccountResourcesV1(opts)).services[1]!
    expect(x.state).toBe('PRESENT')
    expect(x.observed_first_page_count).toBe(2)
    expect(x.total_count).toBe(250)
  })
  it('handles malformed provider JSON and network failures safely',async()=>{
    const {opts}=fixture()
    const broken=vi.fn(async()=>{throw new Error('upstream secret in error')})
    const r=await discoverCloudflareAccountResourcesV1({...opts,fetch_read:broken})
    expect(r.services.every(s=>s.state==='UNKNOWN')).toBe(true)
    expect(JSON.stringify(r)).not.toContain('upstream secret')
  })
  it('does not accept a fabricated count from an unexpected JSON envelope',async()=>{
    const {opts}=fixture({0:{status:200,json:{success:true,result:{credit:999999}}}})
    const r=await discoverCloudflareAccountResourcesV1(opts)
    expect(r.services[0]?.state).toBe('UNKNOWN')
  })
  it('rejects account id and token injection before contacting provider',async()=>{
    const {fetch_read,opts}=fixture()
    await expect(discoverCloudflareAccountResourcesV1({...opts,account_id:'../../bad'})).rejects.toThrow('32 hexadecimal')
    await expect(discoverCloudflareAccountResourcesV1({...opts,api_token:'BAD\nVALUE'})).rejects.toThrow('credential')
    expect(fetch_read).not.toHaveBeenCalled()
  })
  it('makes a reproducible digest and changes it on material account evidence',async()=>{
    const first=await discoverCloudflareAccountResourcesV1(fixture().opts)
    const second=await discoverCloudflareAccountResourcesV1(fixture().opts)
    expect(first.evidence_root).toBe(second.evidence_root)
    const third=await discoverCloudflareAccountResourcesV1(fixture({1:{status:200,json:{success:true,result:[{id:'one'}]}}}).opts)
    expect(first.evidence_root).not.toBe(third.evidence_root)
  })
})
