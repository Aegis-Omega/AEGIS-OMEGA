import { describe, expect, it } from 'vitest'
import { collectAwsResourceReadsV1, type AwsReadCallV1 } from '../../src/sovereignty/aws-readonly-collector.js'
import { observeConnectedResourcesV1, type AwsResourceReadsV1 } from '../../src/sovereignty/connected-resource-intake.js'
import { observeAwsAccountForProviderMeshV1 } from '../../src/sovereignty/provider-adapters/aws.js'
import { buildProviderMeshSnapshotV1, selectProviderV1, DECLARED_PROVIDER_CATALOG_V1 } from '../../src/sovereignty/provider-mesh.js'

function reads(override: Partial<AwsResourceReadsV1> = {}): AwsResourceReadsV1 {
  const success={outcome:'SUCCESS' as const,error_code:null,count:0}
  return {
    sts:success,s3:success,ec2:success,cost_explorer:success,
    billing_views:success,budgets:success,free_tier:success,
    operator_reported_credit_usd:'100.00',
    ...override,
  }
}
async function inventory(aws:AwsResourceReadsV1) {
  return observeConnectedResourcesV1({
    observation_generation:'61',
    cloudflare:{ai_gateway_credit_balance:null,ai_gateway_topup_config:null,
      worker_account_settings:null,worker_scripts:null},
    hugging_face:{account_plan:'UNKNOWN',jobs_total:null},
    aws,
  })
}
const selectionRequest={
  required_capabilities:['SERVERLESS_FUNCTION' as const],
  allowed_providers:['aws'],
  current_generation:'61',
  max_observation_age_generations:'0',
}

describe('AWS provider mesh observer: no compute admission from mere account access',()=>{
  it('declares AWS product capabilities without claiming runtime observation',async()=>{
    const d=DECLARED_PROVIDER_CATALOG_V1.find(x=>x.provider_id==='aws')
    expect(d).toBeDefined()
    expect(d?.authority_effect).toBe('NONE')
    expect(d?.declared_capabilities).toContain('SERVERLESS_FUNCTION')
    const i=await inventory(reads({principal_kind:'IAM_PRINCIPAL'}))
    const o=await observeAwsAccountForProviderMeshV1(i)
    expect(o.state).toBe('ACCOUNT_CONFIGURED')
    expect(o.observed_capabilities).toEqual([])
    expect(o.evidence_hash).toBe(i.integrity_root)
    expect(o.authority_effect).toBe('NONE')
  })
  it('the canonical provider selector rejects AWS despite successful reads',async()=>{
    const o=await observeAwsAccountForProviderMeshV1(await inventory(reads()))
    const snapshot=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[o])
    const selected=await selectProviderV1(snapshot,selectionRequest)
    expect(selected.outcome).toBe('DENIED')
    expect(selected.provider_id).toBeNull()
    expect(selected.denial_codes).toContain('PROVIDER_NOT_OBSERVED_AVAILABLE')
    expect(selected.authority_effect).toBe('NONE')
  })
  it('very large claimed credits cannot turn AWS into a selectable provider',async()=>{
    const o=await observeAwsAccountForProviderMeshV1(await inventory(reads({
      operator_reported_credit_usd:'999999999.99',
    })))
    const s=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[o])
    expect((await selectProviderV1(s,selectionRequest)).outcome).toBe('DENIED')
  })
  it('missing verified STS identity remains UNKNOWN and non-selectable',async()=>{
    const o=await observeAwsAccountForProviderMeshV1(await inventory(reads({sts:null})))
    expect(o.state).toBe('UNKNOWN')
    expect(o.observed_capabilities).toEqual([])
  })
  it('rejects modified inventory bytes even when the attached hash looks correct',async()=>{
    const i=await inventory(reads())
    await expect(observeAwsAccountForProviderMeshV1({
      ...i,observation_generation:'62',
    })).rejects.toThrow('checksum mismatch')
    await expect(observeAwsAccountForProviderMeshV1({
      ...i,authority_effect:'EXECUTE' as never,
    })).rejects.toThrow('non-HOLD')
  })
  it('requires explicit AWS HOLD fields and never processes missing AWS section',async()=>{
    const i=await inventory(reads())
    // Omit the optional field rather than assign undefined:
    // exactOptionalPropertyTypes must remain enabled.
    const withoutAws = {...i}
    delete withoutAws.aws
    await expect(observeAwsAccountForProviderMeshV1(withoutAws)).rejects.toThrow('non-HOLD')
    await expect(observeAwsAccountForProviderMeshV1({
      ...i,aws:{...i.aws!,paid_aws_workloads:'ENABLED' as never},
    })).rejects.toThrow('checksum mismatch')
  })
  it('dynamic AWS read counts produce distinct mesh evidence hashes',async()=>{
    const one=await inventory(reads({
      s3:{outcome:'SUCCESS',error_code:null,count:1},
    }))
    const two=await inventory(reads({
      s3:{outcome:'SUCCESS',error_code:null,count:2},
    }))
    const a=await observeAwsAccountForProviderMeshV1(one)
    const b=await observeAwsAccountForProviderMeshV1(two)
    expect(a.evidence_hash).not.toBe(b.evidence_hash)
    expect(a.observed_capabilities).toEqual([])
    expect(b.observed_capabilities).toEqual([])
  })
  it('closes the read-only collector -> intake -> mesh -> denied-selection chain',async()=>{
    const callback:AwsReadCallV1=async request=>{
      if(request.operation_name==='GetCallerIdentity')return {Account:'123456789012',Arn:'arn:aws:iam::123456789012:user/ScopedReadOnly'}
      const names:Record<string,string>={
        ListBuckets:'Buckets',DescribeRegions:'Regions',ListBillingViews:'billingViews',
        DescribeBudgets:'Budgets',GetFreeTierUsage:'freeTierUsages',
      }
      const field=names[request.operation_name]
      if(!field)throw new Error('unexpected operation')
      return {[field]:[]}
    }
    const raw=await collectAwsResourceReadsV1(callback,{region:'eu-central-1'})
    const i=await inventory(raw)
    const o=await observeAwsAccountForProviderMeshV1(i)
    const s=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[o])
    const decision=await selectProviderV1(s,selectionRequest)
    expect(decision.outcome).toBe('DENIED')
    expect(o.state).toBe('ACCOUNT_CONFIGURED')
    expect(raw.cost_explorer?.outcome).toBe('UNKNOWN')
  })
})

it('root AWS principal is not promoted even to ACCOUNT_CONFIGURED',async()=>{
  const i=await inventory(reads({principal_kind:'ROOT'}))
  const o=await observeAwsAccountForProviderMeshV1(i)
  expect(o.state).toBe('UNKNOWN')
  expect(o.observed_capabilities).toEqual([])
  const s=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[o])
  expect((await selectProviderV1(s,selectionRequest)).outcome).toBe('DENIED')
})
it('malformed forged AWS principal-kind is rejected',async()=>{
  await expect(inventory(reads({principal_kind:'ROOT_USER_WITH_ACCESS' as never})))
    .rejects.toThrow('principal_kind')
})

it('omitted AWS principal-kind is UNKNOWN even when STS is successful',async()=>{
  const i=await inventory(reads())
  const o=await observeAwsAccountForProviderMeshV1(i)
  expect(o.state).toBe('UNKNOWN')
  expect(o.observed_capabilities).toEqual([])
  const s=await buildProviderMeshSnapshotV1(DECLARED_PROVIDER_CATALOG_V1,[o])
  expect((await selectProviderV1(s,selectionRequest)).outcome).toBe('DENIED')
})

it('explicit UNKNOWN AWS principal-kind never promotes account configuration',async()=>{
  const i=await inventory(reads({principal_kind:'UNKNOWN'}))
  const o=await observeAwsAccountForProviderMeshV1(i)
  expect(o.state).toBe('UNKNOWN')
  expect(o.observed_capabilities).toEqual([])
})
