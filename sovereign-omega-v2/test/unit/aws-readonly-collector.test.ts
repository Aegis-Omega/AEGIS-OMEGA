import { describe, expect, it } from 'vitest'
import { collectAwsResourceReadsV1, type AwsReadCallV1, type AwsReadRequestV1 } from '../../src/sovereignty/aws-readonly-collector.js'
import { observeConnectedResourcesV1 } from '../../src/sovereignty/connected-resource-intake.js'

function mockAWS(options?:{ bucketCount?:number; invalidIdentity?:boolean; overrides?:Record<string,unknown>; errors?:Record<string,unknown> }) {
  const calls:AwsReadRequestV1[]=[]
  const data:Record<string,unknown>={
    GetCallerIdentity:{Account:options?.invalidIdentity?'not-an-id':'123456789012',Arn:'NEVER_LOG_ARN'},
    ListBuckets:{Buckets:Array.from({length:options?.bucketCount??2},(_,i)=>({Name:'private-'+i}))},
    DescribeRegions:{Regions:[{RegionName:'eu-central-1'},{RegionName:'us-east-1'}]},
    ListBillingViews:{billingViews:[{arn:'NEVER_LOG_BILLING_ARN'}]},
    DescribeBudgets:{Budgets:[]},GetFreeTierUsage:{freeTierUsages:[{}]},
    GetCostAndUsage:{ResultsByTime:[{Total:{UnblendedCost:{Amount:'100'}}}]},
    ...options?.overrides,
  }
  const call:AwsReadCallV1=async request=>{
    calls.push(request)
    if (options?.errors && request.operation_name in options.errors) throw options.errors[request.operation_name]
    return data[request.operation_name]
  }
  return {calls,call}
}
const options={region:'eu-central-1'}
async function inventory(aws:Awaited<ReturnType<typeof collectAwsResourceReadsV1>>) {
  return observeConnectedResourcesV1({
    observation_generation:'44',
    cloudflare:{ai_gateway_credit_balance:null,ai_gateway_topup_config:null,worker_account_settings:null,worker_scripts:null},
    hugging_face:{account_plan:'UNKNOWN',jobs_total:null},aws,
  })
}
describe('AWS read-only collector, provider-bound input not hardcoded',()=>{
  it('derives bucket count from real callback output',async()=>{
    for (const count of [0,2,7]) {
      const {call,calls}=mockAWS({bucketCount:count})
      const result=await collectAwsResourceReadsV1(call,options)
      expect(result.s3?.count).toBe(count)
      expect(result.free_tier?.count).toBe(1)
      expect(result.billing_views?.count).toBe(1)
      expect(result.cost_explorer?.outcome).toBe('UNKNOWN')
      expect(calls.some(x=>x.operation_name==='GetCostAndUsage')).toBe(false)
      expect(calls.find(x=>x.operation_name==='DescribeBudgets')?.params).toEqual({AccountId:'123456789012'})
      expect(JSON.stringify(result)).not.toContain('123456789012')
    }
  })
  it('retains HOLD and records actual counts in hash',async()=>{
    const a=await inventory(await collectAwsResourceReadsV1(mockAWS({bucketCount:2}).call,options))
    const b=await inventory(await collectAwsResourceReadsV1(mockAWS({bucketCount:3}).call,options))
    expect(a.aws?.s3_bucket_count).toBe(2)
    expect(a.aws?.ec2_region_count).toBe(2)
    expect(a.aws?.remaining_credit_verified).toBe('UNKNOWN')
    expect(a.aws?.paid_aws_workloads).toBe('HOLD')
    expect(a.authority_effect).toBe('NONE')
    expect(a.zero_spend_admission).toBe('HOLD')
    expect(a.integrity_root).not.toBe(b.integrity_root)
  })
  it('preserves known AWS failure codes without raw error text',async()=>{
    const {call}=mockAWS({errors:{
      ListBuckets:Object.assign(new Error('private secret'),{code:'NotSignedUp'}),
      DescribeRegions:new Error('An error occurred (OptInRequired)'),
      GetCostAndUsage:Object.assign(new Error('private secret'),{Code:'SubscriptionRequiredException'}),
    }})
    const result=await collectAwsResourceReadsV1(call,{
      ...options,include_cost_explorer:true,cost_period:{start:'2026-10-01',end:'2026-11-01'},
    })
    expect(result.s3?.error_code).toBe('NotSignedUp')
    expect(result.ec2?.error_code).toBe('OptInRequired')
    expect(result.cost_explorer?.error_code).toBe('SubscriptionRequiredException')
    expect(JSON.stringify(result)).not.toContain('private secret')
  })
  it('blocks budget lookup if STS identity cannot be validated',async()=>{
    const {call,calls}=mockAWS({invalidIdentity:true})
    const result=await collectAwsResourceReadsV1(call,options)
    expect(result.sts?.outcome).toBe('UNKNOWN')
    expect(result.budgets?.outcome).toBe('UNKNOWN')
    expect(calls.some(x=>x.operation_name==='DescribeBudgets')).toBe(false)
  })
  it('marks unpaginated lists UNKNOWN instead of presenting partial count',async()=>{
    const {call}=mockAWS({overrides:{
      ListBillingViews:{billingViews:[],nextToken:'MORE'},
      GetFreeTierUsage:{freeTierUsages:[],NextToken:'MORE'},
    }})
    const r=await collectAwsResourceReadsV1(call,options)
    expect(r.billing_views?.outcome).toBe('UNKNOWN')
    expect(r.free_tier?.outcome).toBe('UNKNOWN')
  })
  it('ignores unknown error codes and untrusted secret-bearing payloads',async()=>{
    const {call}=mockAWS({errors:{ListBuckets:new Error('SENSITIVE SECRET'),ListBillingViews:Object.assign(new Error('another secret'),{code:'NotAStandardError'})}})
    const result=await collectAwsResourceReadsV1(call,options)
    expect(result.s3?.error_code).toBeNull()
    expect(result.billing_views?.error_code).toBeNull()
    expect(JSON.stringify(result)).not.toContain('SENSITIVE')
  })
  it('requires explicit Cost Explorer opt-in and a real calendar interval',async()=>{
    const {call,calls}=mockAWS()
    await expect(collectAwsResourceReadsV1(call,{...options,include_cost_explorer:true})).rejects.toThrow('cost_period')
    await expect(collectAwsResourceReadsV1(call,{...options,include_cost_explorer:true,cost_period:{start:'2026-02-29',end:'2026-03-01'}})).rejects.toThrow('cost_period')
    expect(calls).toHaveLength(0)
    const r=await collectAwsResourceReadsV1(call,{...options,include_cost_explorer:true,cost_period:{start:'2026-10-01',end:'2026-11-01'}})
    expect(r.cost_explorer?.outcome).toBe('SUCCESS')
    expect(calls.filter(x=>x.operation_name==='GetCostAndUsage')).toHaveLength(1)
  })
  it('does not emit AWS identifiers or ARNs in the final checksum envelope',async()=>{
    const result=await inventory(await collectAwsResourceReadsV1(mockAWS().call,options))
    const text=JSON.stringify(result)
    expect(text).not.toContain('123456789012')
    expect(text).not.toContain('NEVER_LOG_')
    expect(result.integrity_root).toMatch(/^[a-f0-9]{64}$/)
  })
  it('identical observations generate identical hashes',async()=>{
    const a=await inventory(await collectAwsResourceReadsV1(mockAWS().call,options))
    const b=await inventory(await collectAwsResourceReadsV1(mockAWS().call,options))
    expect(a.integrity_root).toBe(b.integrity_root)
  })
})
