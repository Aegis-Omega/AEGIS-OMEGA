/**
 * Optional, fail-closed durable checkpoint boundary for signed free-resource
 * planning. Contract only: no storage adapter, credentials, migrations, or
 * production execution authority are provided here.
 *
 * Host MUST inject an authenticated, atomic, durable store. Its preseeded
 * policy-scoped row MUST survive process restarts and concurrent workers.
 * No row = UNAVAILABLE/HOLD, never auto-create a fresh floor.
 */
import {
  createTrustedFreeResourcePlannerV1,
  type TrustedFreeResourcePolicyV1,
  type SignedFreeResourceApprovalV1,
  type TrustedFreeResourcePlannerV1,
} from './trusted-free-resource-planner.js'
import {
  planFreeResourceV1,
  type FreeResourceRequestV1,
  type FreeResourceEvidenceV1,
  type FreeResourceDecisionV1,
} from './free-resource-planning.js'
import type { ProviderMeshSnapshotV1 } from './provider-mesh.js'

const DEC=/^(0|[1-9][0-9]*)$/
const POLICY_ID=/^[a-zA-Z0-9._:-]{1,128}$/

/**
 * Every call MUST execute a single durable serializable transaction:
 *  1. Read existing row under a row-level/exclusive lock.
 *  2. Return UNAVAILABLE if row is missing, inaccessible, or untrusted.
 *  3. Return ROLLBACK for observed generation < persisted floor.
 *  4. Otherwise write MAX(persisted floor, observed) and COMMIT before
 *     returning ACCEPTED with the committed exact floor.
 * The adapter MUST NOT fabricate ACCEPTED on timeout or network failure.
 */
export interface AuthenticatedAtomicGenerationCheckpointV1 {
  observe_and_advance(
    policy_id:string,
    observed_generation:string,
  ):Promise<
    | {outcome:'ACCEPTED'; persisted_generation:string}
    | {outcome:'ROLLBACK'|'UNAVAILABLE'}
  >
}
export interface DurableFreeResourcePlannerV1 extends TrustedFreeResourcePlannerV1 {
  /** Planning ONLY, and never a provider-side quota reservation. */
  readonly authority_effect:'NONE'
}

/**
 * Call ONLY at trusted runtime bootstrap. Source of policy, generation clock
 * and transactional checkpoint must be authenticated independently.
 * This wrapper never connects to a provider, database or billing system.
 */
export function createDurableFreeResourcePlannerV1(
  authenticated_policy:TrustedFreeResourcePolicyV1,
  read_authenticated_generation:()=>string,
  checkpoint:AuthenticatedAtomicGenerationCheckpointV1,
):DurableFreeResourcePlannerV1 {
  const inner=createTrustedFreeResourcePlannerV1(
    authenticated_policy,read_authenticated_generation,
  )
  if(!POLICY_ID.test(authenticated_policy.policy_id)
    ||!checkpoint||typeof checkpoint.observe_and_advance!=='function') {
    throw new TypeError('trusted durable checkpoint is required')
  }
  const policyId=authenticated_policy.policy_id
  const readGeneration=():string|null=>{
    try {
      const value=read_authenticated_generation()
      return typeof value==='string'&&DEC.test(value)?value:null
    } catch {return null}
  }
  const observe=async(generation:string):Promise<boolean>=>{
    try {
      const answer=await checkpoint.observe_and_advance(policyId,generation)
      // Persisted floor must match the requested generation. Anything else
      // is not an independently verified, current generation checkpoint.
      return answer?.outcome==='ACCEPTED'
        && typeof answer.persisted_generation==='string'
        && DEC.test(answer.persisted_generation)
        && answer.persisted_generation===generation
    } catch {
      return false
    }
  }
  const hold=(
    snapshot:ProviderMeshSnapshotV1,
    request:FreeResourceRequestV1,
    evidence:readonly FreeResourceEvidenceV1[],
  )=>planFreeResourceV1(snapshot,request,evidence,[])

  return Object.freeze({
    authority_effect:'NONE' as const,
    async plan(
      snapshot:ProviderMeshSnapshotV1,
      request:FreeResourceRequestV1,
      evidence:readonly FreeResourceEvidenceV1[],
      signed:readonly SignedFreeResourceApprovalV1[],
    ):Promise<FreeResourceDecisionV1> {
      const initial=readGeneration()
      if(initial===null||request?.current_generation!==initial) {
        return hold(snapshot,request,evidence)
      }
      if(!await observe(initial)) return hold(snapshot,request,evidence)
      const result=await inner.plan(snapshot,request,evidence,signed)
      if(result.outcome!=='PLANNING_ELIGIBLE') return result
      // A different worker may advance the durable floor while Ed25519 and
      // planning awaits are in flight. Recheck atomically before returning.
      const final=readGeneration()
      if(final!==initial||final===null||!await observe(final)){
        return hold(snapshot,request,evidence)
      }
      return result
    },
  })
}
