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

it('classifies STS root without persisting ARN, account or UserId',async()=>{
  const seen: string[]=[]
  const call:AwsReadCallV1=async r=>{
    seen.push(r.operation_name)
    if(r.operation_name==='GetCallerIdentity')return {
      Account:'123456789012',Arn:'arn:aws:iam::123456789012:root',UserId:'PRIVATE_USER_ID',
    }
    const fields:Record<string,string>={
      ListBuckets:'Buckets',DescribeRegions:'Regions',ListBillingViews:'billingViews',
      DescribeBudgets:'Budgets',GetFreeTierUsage:'freeTierUsages',
    }
    const field=fields[r.operation_name]
    if(!field) throw new Error('unexpected AWS operation: '+r.operation_name)
    return {[field]:[]}
  }
  const result=await collectAwsResourceReadsV1(call,{region:'eu-central-1'})
  expect(result.principal_kind).toBe('ROOT')
  expect(result.sts?.outcome).toBe('SUCCESS')
  expect(JSON.stringify(result)).not.toContain('123456789012')
  expect(JSON.stringify(result)).not.toContain('PRIVATE_USER_ID')
  expect(seen).not.toContain('GetCostAndUsage')
})
it('classifies an assumed IAM role only for the same STS account',async()=>{
  const roleCall:AwsReadCallV1=async r=>r.operation_name==='GetCallerIdentity'
    ? {Account:'123456789012',Arn:'arn:aws:sts::123456789012:assumed-role/ScopedRole/session'}
    : {Buckets:[],Regions:[],billingViews:[],Budgets:[],freeTierUsages:[]}
  const result=await collectAwsResourceReadsV1(roleCall,{region:'eu-central-1'})
  expect(result.principal_kind).toBe('IAM_PRINCIPAL')
  expect(JSON.stringify(result)).not.toContain('ScopedRole')
})
it('unknown or cross-account STS ARN never proves non-root identity',async()=>{
  for(const Arn of [undefined,'arn:aws:iam::999999999999:role/Scope','arn:aws:iam::123456789012:root/fake']){
    const call:AwsReadCallV1=async r=>r.operation_name==='GetCallerIdentity'
      ? {Account:'123456789012',Arn}
      : {Buckets:[],Regions:[],billingViews:[],Budgets:[],freeTierUsages:[]}
    const result=await collectAwsResourceReadsV1(call,{region:'eu-central-1'})
    expect(result.principal_kind).toBe('UNKNOWN')
  }
})

describe('AWS optional read-only service discovery',()=>{
  async function discover(overrides:Record<string,unknown> = {},errors:Record<string,unknown> = {}){
    const calls:string[]=[]
    const call:AwsReadCallV1=async r=>{
      calls.push(r.operation_name)
      if (r.operation_name in errors) throw errors[r.operation_name]
      const fields:Record<string,string>={
        ListBuckets:'Buckets',DescribeRegions:'Regions',ListBillingViews:'billingViews',
        DescribeBudgets:'Budgets',GetFreeTierUsage:'freeTierUsages',
        ListFoundationModels:'modelSummaries',GetDatabases:'DatabaseList',
        ListFunctions:'Functions',ListTables:'TableNames',ListTableBuckets:'tableBuckets',
      }
      if(r.operation_name==='GetCallerIdentity')
        return {Account:'123456789012',Arn:'arn:aws:iam::123456789012:root'}
      const field=fields[r.operation_name]
      if(!field) throw new Error('unexpected AWS operation: '+r.operation_name)
      return overrides[r.operation_name]??{[field]:[]}
    }
    return {result:await collectAwsResourceReadsV1(call,{region:'eu-central-1',include_service_discovery:true}),calls}
  }
  it('does not call Bedrock, Glue, Lambda, DynamoDB or S3 Tables by default',async()=>{
    const calls: string[]=[]
    const call:AwsReadCallV1=async r=>{
      calls.push(r.operation_name)
      if (r.operation_name==='GetCallerIdentity')return {Account:'123456789012'}
      const fields:Record<string,string>={ListBuckets:'Buckets',DescribeRegions:'Regions',
        ListBillingViews:'billingViews',DescribeBudgets:'Budgets',GetFreeTierUsage:'freeTierUsages'}
      const field=fields[r.operation_name]
    if(!field) throw new Error('unexpected AWS operation: '+r.operation_name)
    return {[field]:[]}
    }
    const d=await collectAwsResourceReadsV1(call,{region:'eu-central-1'})
    expect(d.service_discovery).toBeUndefined()
    expect(calls).not.toContain('ListFoundationModels')
    expect(calls).not.toContain('GetCostAndUsage')
  })
  it('measures 55 Bedrock metadata rows and zero Glue databases without enabling inference',async()=>{
    const {result}=await discover(
      {ListFoundationModels:{modelSummaries:Array.from({length:55},(_,n)=>({modelId:'private-'+n}))}},
      {ListFunctions:Object.assign(new Error('Private error'),{code:'SubscriptionRequiredException'}),
        ListTables:Object.assign(new Error('Private error'),{code:'SubscriptionRequiredException'}),
        ListTableBuckets:Object.assign(new Error('Private error'),{code:'ForbiddenException'})})
    expect(result.service_discovery?.bedrock?.count).toBe(55)
    expect(result.service_discovery?.glue?.count).toBe(0)
    expect(result.service_discovery?.lambda?.error_code).toBe('SubscriptionRequiredException')
    expect(result.service_discovery?.dynamodb?.error_code).toBe('SubscriptionRequiredException')
    expect(result.service_discovery?.s3tables?.error_code).toBe('ForbiddenException')
    const observed=await observeConnectedResourcesV1({
      observation_generation:'7',
      cloudflare:{ai_gateway_credit_balance:null,ai_gateway_topup_config:null,worker_account_settings:null,worker_scripts:null},
      hugging_face:{account_plan:'UNKNOWN',jobs_total:null},
      aws:result,
    })
    expect(observed.aws?.service_discovery?.bedrock?.count).toBe(55)
    // Collector and intake must agree on safe, standard AWS denial codes.
    expect(observed.aws?.service_discovery?.s3tables?.outcome).toBe('ERROR')
    expect(observed.aws?.service_discovery?.s3tables?.error_code).toBe('ForbiddenException')
    expect(observed.aws?.service_discovery?.s3tables?.count).toBeNull()
    expect(observed.aws?.paid_aws_workloads).toBe('HOLD')
    expect(observed.authority_effect).toBe('NONE')
    expect(JSON.stringify(observed)).not.toContain('private-')
    expect(JSON.stringify(observed)).not.toContain('Private error')
  })
  it('does not include secret-bearing or unrecognized errors in the normalized digest',async()=>{
    const {result}=await discover({},{
      ListTableBuckets:Object.assign(new Error('internal secret'),{code:'NotAnAwsError'}),
    })
    const observed=await observeConnectedResourcesV1({
      observation_generation:'7',
      cloudflare:{ai_gateway_credit_balance:null,ai_gateway_topup_config:null,
        worker_account_settings:null,worker_scripts:null},
      hugging_face:{account_plan:'UNKNOWN',jobs_total:null},
      aws:result,
    })
    expect(observed.aws?.service_discovery?.s3tables?.error_code).toBeNull()
    expect(JSON.stringify(observed)).not.toContain('internal secret')
    expect(observed.aws?.paid_aws_workloads).toBe('HOLD')
  })
  it('treats service-specific pagination markers as unknown rather than complete',async()=>{
    const {result}=await discover({
      ListFunctions:{Functions:[],NextMarker:'more'},
      ListTables:{TableNames:[],LastEvaluatedTableName:'next'},
      ListTableBuckets:{tableBuckets:[],continuationToken:'next'},
    })
    expect(result.service_discovery?.lambda?.outcome).toBe('UNKNOWN')
    expect(result.service_discovery?.dynamodb?.outcome).toBe('UNKNOWN')
    expect(result.service_discovery?.s3tables?.outcome).toBe('UNKNOWN')
  })
  it('hash changes when actual Bedrock discovery count changes',async()=>{
    const a=(await discover({ListFoundationModels:{modelSummaries:[]}})).result
    const b=(await discover({ListFoundationModels:{modelSummaries:[{modelId:'one'}]}})).result
    const toInventory=(aws:typeof a)=>observeConnectedResourcesV1({
      observation_generation:'7',
      cloudflare:{ai_gateway_credit_balance:null,ai_gateway_topup_config:null,worker_account_settings:null,worker_scripts:null},
      hugging_face:{account_plan:'UNKNOWN' as const,jobs_total:null},aws,
    })
    const ia=await toInventory(a)
    const ib=await toInventory(b)
    expect(ia.integrity_root).not.toBe(ib.integrity_root)
    expect(ib.aws?.remaining_credit_verified).toBe('UNKNOWN')
    expect(ib.zero_spend_admission).toBe('HOLD')
  })
})
