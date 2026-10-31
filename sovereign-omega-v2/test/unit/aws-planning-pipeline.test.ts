import { describe, expect, it } from 'vitest'
import { inspectAwsProviderForPlanningV1 } from '../../src/sovereignty/aws-planning-pipeline.js'
import type { AwsReadCallV1, AwsReadRequestV1 } from '../../src/sovereignty/aws-readonly-collector.js'

function fixture(arn = 'arn:aws:iam::123456789012:root', modelCount = 3) {
  const calls: AwsReadRequestV1[] = []
  const fields: Record<string, string> = {
    ListBuckets:'Buckets', DescribeRegions:'Regions',
    ListBillingViews:'billingViews', DescribeBudgets:'Budgets',
    GetFreeTierUsage:'freeTierUsages', ListFoundationModels:'modelSummaries',
    GetDatabases:'DatabaseList', ListFunctions:'Functions',
    ListTables:'TableNames', ListTableBuckets:'tableBuckets',
  }
  const call: AwsReadCallV1 = async request => {
    calls.push(request)
    if (request.operation_name === 'GetCallerIdentity') {
      return {Account:'123456789012',Arn:arn,UserId:'SENSITIVE_STS_ID'}
    }
    if (request.operation_name === 'ListFoundationModels') {
      return {modelSummaries:Array.from({length:modelCount}, (_,i) => ({modelId:'private-'+i}))}
    }
    const field = fields[request.operation_name]
    if (!field) throw new Error('unexpected API operation')
    return {[field]:[]}
  }
  return {call,calls}
}
const request = {
  observation_generation:'73',
  region:'eu-central-1',
  required_capabilities:['SERVERLESS_FUNCTION' as const],
}

describe('AWS single-call read-only planning pipeline', () => {
  it('keeps root principal UNKNOWN, denies execution and preserves HOLD',async()=>{
    const f=fixture()
    const r=await inspectAwsProviderForPlanningV1(f.call,request)
    expect(r.schema).toBe('AEGIS_AWS_PLANNING_PIPELINE_V1')
    expect(r.inventory.aws?.principal_kind).toBe('ROOT')
    expect(r.snapshot.observations.find(x=>x.provider_id==='aws')?.state).toBe('UNKNOWN')
    expect(r.selection.outcome).toBe('DENIED')
    expect(r.selection.provider_id).toBeNull()
    expect(r.disposition).toBe('HOLD')
    expect(r.authority_effect).toBe('NONE')
  })
  it('keeps a recognized IAM principal observational, never executable',async()=>{
    const f=fixture('arn:aws:iam::123456789012:role/ScopedReadOnly')
    const r=await inspectAwsProviderForPlanningV1(f.call,request)
    expect(r.snapshot.observations.find(x=>x.provider_id==='aws')?.state).toBe('ACCOUNT_CONFIGURED')
    expect(r.snapshot.observations.find(x=>x.provider_id==='aws')?.observed_capabilities).toEqual([])
    expect(r.selection.outcome).toBe('DENIED')
  })
  it('never calls Cost Explorer or optional discovery by default',async()=>{
    const f=fixture()
    await inspectAwsProviderForPlanningV1(f.call,request)
    const calls=f.calls.map(x=>x.operation_name)
    expect(calls).not.toContain('GetCostAndUsage')
    expect(calls).not.toContain('ListFoundationModels')
  })
  it('opt-in discovery is hashed yet exposes neither IDs nor inference authority',async()=>{
    const a=fixture(undefined,3)
    const b=fixture(undefined,4)
    const first=await inspectAwsProviderForPlanningV1(a.call,{...request,include_service_discovery:true})
    const second=await inspectAwsProviderForPlanningV1(b.call,{...request,include_service_discovery:true})
    expect(first.inventory.aws?.service_discovery?.bedrock?.count).toBe(3)
    expect(second.inventory.aws?.service_discovery?.bedrock?.count).toBe(4)
    expect(first.inventory.integrity_root).not.toBe(second.inventory.integrity_root)
    expect(first.selection.outcome).toBe('DENIED')
    expect(JSON.stringify(first)).not.toContain('SENSITIVE_STS_ID')
    expect(JSON.stringify(first)).not.toContain('private-')
    expect(JSON.stringify(first)).not.toContain('123456789012')
  })
  it('rejects malformed generation before any AWS read',async()=>{
    const f=fixture()
    await expect(inspectAwsProviderForPlanningV1(f.call,{
      ...request,observation_generation:'01',
    })).rejects.toThrow('canonical unsigned decimal')
    expect(f.calls).toEqual([])
  })
  it('rejects empty or undeclared required capability before any AWS read',async()=>{
    for(const caps of [[],['SYMBOLIC_COMPUTE' as const]]) {
      const f=fixture()
      await expect(inspectAwsProviderForPlanningV1(f.call,{
        ...request,required_capabilities:caps,
      })).rejects.toThrow(/nonempty|declared for AWS/)
      expect(f.calls).toEqual([])
    }
  })
  it('rejects duplicated capability requirements before any AWS read',async()=>{
    const f=fixture()
    await expect(inspectAwsProviderForPlanningV1(f.call,{
      ...request,required_capabilities:['SERVERLESS_FUNCTION','SERVERLESS_FUNCTION'],
    })).rejects.toThrow('unique')
    expect(f.calls).toEqual([])
  })
  it('rejects numeric or boolean generation before any AWS API request',async()=>{
    for(const generation of [73,true]) {
      const f=fixture()
      await expect(inspectAwsProviderForPlanningV1(f.call,{
        ...request,observation_generation:generation as never,
      })).rejects.toThrow('canonical unsigned decimal')
      expect(f.calls).toEqual([])
    }
  })
})
