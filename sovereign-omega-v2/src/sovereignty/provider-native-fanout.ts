// AEGIS bounded provider-native fan-out/fan-in V1. Authority effect: NONE.
// Native SDK admission, credentials, billing grants and process sandboxing are
// external. A hash-consistent receipt is not a provider signature or truth proof.
import type { SHA256Hex } from '../core/types.js'
import { canonicalizeJCSString } from '../core/canonicalize.js'
import { hashValue } from '../core/hashing.js'
import type { ProviderMeshSnapshotV1 } from './provider-mesh.js'
import {
  buildProviderNativeAgentRegistryV1, selectProviderNativeAgentV1,
  type ProviderNativeAgentRegistryV1, type ProviderNativeAgentSelectionReceiptV1,
} from './provider-native-agents.js'

export const MAX_FANOUT_PROVIDERS_V1 = 3
export const MAX_FANOUT_BATCHES_PER_INSTANCE_V1 = 256
const prefixes = {
  openai: 'AEGIS_OPENAI_NATIVE_AGENT',
  anthropic: 'AEGIS_ANTHROPIC_NATIVE_AGENT',
  'google-cloud': 'AEGIS_GOOGLE_ADK_NATIVE_AGENT',
} as const
export interface FanoutInputV1 {
  snapshot: ProviderMeshSnapshotV1
  registry: ProviderNativeAgentRegistryV1
  batch_id: string
  task: string
  providers: readonly string[]
  max_parallel: number
  min_verified: number
  timeout_ms: number
  current_generation: string
  max_observation_age_generations: string
}
export interface FanoutNativeOutputV1 {
  readonly final_output: string
  readonly model: string
  readonly run_id?: string
  readonly session_id?: string
}
export interface FanoutAdapterResultV1 {
  readonly selection: ProviderNativeAgentSelectionReceiptV1
  readonly output: FanoutNativeOutputV1 | null
  readonly receipt: object | null
}
/** Structurally compatible with execute() in #589/#591/#592. Old adapters may
 * ignore signal. An abort request must never be promoted to confirmed cancellation. */
export interface FanoutAdapterV1 {
  readonly provider_id: string
  execute(input: {
    readonly snapshot: ProviderMeshSnapshotV1
    readonly registry: ProviderNativeAgentRegistryV1
    readonly task: string
    readonly current_generation: string
    readonly max_observation_age_generations: string
    readonly signal: AbortSignal
  }): Promise<FanoutAdapterResultV1>
}
export interface FanoutVerifierV1 {
  readonly verifier_id: string
  readonly policy_hash: SHA256Hex
  verify(input: {
    readonly provider_id: string
    readonly task: string
    readonly output: string
    readonly native_receipt_root: SHA256Hex
    readonly subject_root: SHA256Hex
    readonly signal: AbortSignal
  }): Promise<{ readonly passed: boolean; readonly evidence_hash: SHA256Hex }>
}
interface Configuration {
  readonly adapter_ids: readonly string[]
  readonly verifier_id: string
  readonly policy_hash: SHA256Hex
}
interface Verification {
  readonly verifier_id: string
  readonly policy_hash: SHA256Hex
  readonly subject_root: SHA256Hex
  readonly passed: boolean
  readonly evidence_hash: SHA256Hex
}
type Status = 'DENIED' | 'NOT_DISPATCHED' | 'FAILED' | 'TIMED_OUT' | 'VERIFIER_REJECTED' | 'VERIFIED'
interface LeafBody {
  readonly provider_id: string
  readonly selection: ProviderNativeAgentSelectionReceiptV1
  readonly status: Status
  readonly reason_code: string
  readonly dispatched: boolean
  readonly native_result: FanoutAdapterResultV1 | null
  readonly verification: Verification | null
  readonly cancellation_requested: boolean
  readonly cancellation_confirmed: false
}
export interface FanoutLeafV1 extends LeafBody { readonly leaf_root: SHA256Hex }
export interface FanoutReceiptV1 {
  readonly schema_version: '1.0.0'
  readonly request: FanoutInputV1
  readonly configuration: Configuration
  readonly request_root: SHA256Hex
  readonly leaves: readonly FanoutLeafV1[]
  readonly dispatched_count: number
  readonly verified_count: number
  readonly outcome: 'DENIED' | 'INSUFFICIENT_VERIFIED_RESULTS' | 'SYNTHESIZED'
  readonly synthesis_policy: 'PROVENANCE_BUNDLE_V1'
  readonly synthesis_hash: SHA256Hex | null
  readonly consensus_claim: 'NONE'
  readonly durable_apply_performed: false
  readonly authority_effect: 'NONE'
  readonly receipt_root: SHA256Hex
}
export interface FanoutResultV1 { readonly synthesis: string | null; readonly receipt: FanoutReceiptV1 }
const hash = (domain: string, body: unknown) => hashValue({ domain, body })
const same = (a: unknown, b: unknown) => canonicalizeJCSString(a) === canonicalizeJCSString(b)
function requireValue(ok: unknown, message: string): asserts ok { if (!ok) throw new TypeError(message) }
function boundedText(value: unknown, limit: number): value is string {
  return typeof value === 'string' && value.trim().length > 0 && new TextEncoder().encode(value).length <= limit
}
const isHash = (value: unknown): value is SHA256Hex => typeof value === 'string' && /^[0-9a-f]{64}$/.test(value)
function freeze<T>(value: T): T {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value) }
  return value
}
function validateRequest(input: FanoutInputV1): void {
  requireValue(boundedText(input.batch_id,128) && /^[a-zA-Z0-9._:-]+$/.test(input.batch_id),'invalid batch_id')
  requireValue(boundedText(input.task,16384),'task must be non-empty and at most 16384 UTF-8 bytes')
  requireValue(Array.isArray(input.providers) && input.providers.length > 0 && input.providers.length <= MAX_FANOUT_PROVIDERS_V1,'invalid provider count')
  requireValue(new Set(input.providers).size === input.providers.length,'duplicate requested provider')
  requireValue(input.providers.every(id => Object.hasOwn(prefixes,id)),'unsupported fanout provider')
  for (const [name,value,max] of [['max_parallel',input.max_parallel,3],['min_verified',input.min_verified,input.providers.length],['timeout_ms',input.timeout_ms,30000]] as const) {
    requireValue(Number.isSafeInteger(value) && value > 0 && value <= max,`invalid ${name}`)
  }
  requireValue(Array.isArray(input.snapshot?.descriptors) && input.snapshot.descriptors.length <= 128,'snapshot descriptor bound')
  requireValue(Array.isArray(input.snapshot?.observations) && input.snapshot.observations.length <= 128,'snapshot observation bound')
  requireValue(Array.isArray(input.registry?.agents) && input.registry.agents.length <= 128,'registry bound')
}
function validateConfiguration(config: Configuration): void {
  requireValue(boundedText(config.verifier_id,128) && isHash(config.policy_hash),'invalid verifier configuration')
  requireValue(config.adapter_ids.length > 0 && config.adapter_ids.length <= 3 && new Set(config.adapter_ids).size === config.adapter_ids.length,'invalid adapter configuration')
  requireValue(config.adapter_ids.every(id=>Object.hasOwn(prefixes,id)),'unsupported adapter configuration')
}
async function prepare(request: FanoutInputV1, config: Configuration) {
  validateRequest(request); validateConfiguration(config)
  const expectedRegistry = await buildProviderNativeAgentRegistryV1(request.snapshot.descriptors.filter(d=>request.registry.agents.some(a=>a.provider_id===d.provider_id)))
  // #588 checks a reconstructed root but not every supplied registry body field.
  // Compare the complete body here before parallel native calls are possible.
  requireValue(same(request.registry,expectedRegistry),'native registry body/root verification failed')
  const selections = await Promise.all(request.providers.map(provider_id=>selectProviderNativeAgentV1(request.snapshot,request.registry,{
    required_capabilities:['AGENT_EXECUTION','MODEL_INFERENCE'],
    allowed_providers:config.adapter_ids.includes(provider_id)?[provider_id]:[],
    preferred_provider_order:[provider_id], current_generation:request.current_generation,
    max_observation_age_generations:request.max_observation_age_generations,
  })))
  const request_root=await hash('AEGIS_PROVIDER_FANOUT_REQUEST_V1',{request,configuration:config})
  // The native task includes the full request commitment, not just free text.
  // A receipt from a different batch/policy/budget cannot be silently replayed.
  const task=canonicalizeJCSString({domain:'AEGIS_PROVIDER_FANOUT_NATIVE_TASK_V1',batch_id:request.batch_id,request_root,task:request.task})
  return {selections,request_root,task}
}

/** Validate existing per-provider receipt schemas, not merely a 64-hex string.
 * This establishes structural integrity; authenticity requires an external verifier. */
async function verifyNative(provider_id: string, task: string, selection: ProviderNativeAgentSelectionReceiptV1, native: FanoutAdapterResultV1): Promise<SHA256Hex> {
  requireValue(selection.outcome==='SELECTED' && selection.provider_id===provider_id,'provider not selected')
  requireValue(native && same(native.selection,selection),'native selection mismatch')
  requireValue(native.receipt && typeof native.receipt==='object' && native.output,'native result missing')
  const output=native.output; const receipt=native.receipt as Record<string,unknown>
  requireValue(boundedText(output.final_output,65536) && boundedText(output.model,256),'invalid native output')
  const openai=provider_id==='openai'; const id=openai?output.run_id:output.session_id
  requireValue(boundedText(id,256),'native execution identity missing')
  requireValue(same(output,{final_output:output.final_output,model:output.model,...(openai?{run_id:id}:{session_id:id})}),'unexpected native output fields')
  requireValue(same(native,{selection:native.selection,output:native.output,receipt:native.receipt}),'unexpected native result fields')
  const prefix=prefixes[provider_id as keyof typeof prefixes]
  const expected={schema_version:'1.0.0',provider_id,agent_id:`provider-agent:${provider_id}`,provider_selection_receipt_root:selection.receipt_root,
    ...(openai?{native_run_id:id}:{native_session_id:id}),model:output.model,
    task_hash:await hashValue({domain:`${prefix}_TASK_V1`,task}),
    output_hash:await hashValue({domain:`${prefix}_OUTPUT_V1`,...(openai?{native_run_id:id}:{session_id:id}),model:output.model,final_output:output.final_output}),
    write_authority:'NOT_GRANTED',merge_authority:'NOT_GRANTED',deploy_authority:'NOT_GRANTED',financial_authority:'NOT_GRANTED',authority_effect:'NONE'}
  const receipt_root=await hashValue({domain:`${prefix}_EXECUTION_RECEIPT_V1`,receipt:expected})
  requireValue(same(receipt,{...expected,receipt_root}),'native receipt integrity/binding mismatch')
  return receipt_root
}
function initialLeaf(provider_id: string, selection: ProviderNativeAgentSelectionReceiptV1): LeafBody {
  const denied=selection.outcome!=='SELECTED'
  return {provider_id,selection,status:denied?'DENIED':'NOT_DISPATCHED',reason_code:denied?'PROVIDER_SELECTION_DENIED':'PREFLIGHT_QUORUM_NOT_MET',dispatched:false,native_result:null,verification:null,cancellation_requested:false,cancellation_confirmed:false}
}
async function finish(request: FanoutInputV1, configuration: Configuration, request_root: SHA256Hex, bodies: readonly LeafBody[]): Promise<FanoutResultV1> {
  const leaves=await Promise.all(bodies.map(async body=>({...body,leaf_root:await hash('AEGIS_PROVIDER_FANOUT_LEAF_V1',body)})))
  const verified=leaves.filter(leaf=>leaf.status==='VERIFIED')
  const dispatched_count=leaves.filter(leaf=>leaf.dispatched).length
  const outcome: FanoutReceiptV1['outcome']=dispatched_count===0?'DENIED':verified.length<request.min_verified?'INSUFFICIENT_VERIFIED_RESULTS':'SYNTHESIZED'
  const synthesis=outcome==='SYNTHESIZED'?canonicalizeJCSString({policy:'PROVENANCE_BUNDLE_V1',consensus_claim:'NONE',items:verified.map(leaf=>({provider_id:leaf.provider_id,output:leaf.native_result!.output!.final_output,native_receipt_root:(leaf.native_result!.receipt as Record<string,unknown>).receipt_root}))}):null
  const body={schema_version:'1.0.0' as const,request,configuration,request_root,leaves,dispatched_count,verified_count:verified.length,outcome,
    synthesis_policy:'PROVENANCE_BUNDLE_V1' as const,synthesis_hash:synthesis===null?null:await hash('AEGIS_PROVIDER_FANOUT_SYNTHESIS_V1',synthesis),consensus_claim:'NONE' as const,durable_apply_performed:false as const,authority_effect:'NONE' as const}
  const receipt_root=await hash('AEGIS_PROVIDER_FANOUT_RECEIPT_V1',body)
  return freeze({synthesis,receipt:{...body,receipt_root}})
}

export function createProviderNativeFanoutV1(options: {readonly adapters: readonly FanoutAdapterV1[]; readonly verifier: FanoutVerifierV1}) {
  requireValue(options.adapters.length>0 && options.adapters.length<=3,'invalid adapter count')
  const adapters=new Map(options.adapters.map(a=>[a.provider_id,a.execute.bind(a)]))
  requireValue(adapters.size===options.adapters.length,'duplicate provider adapter')
  const config=freeze({adapter_ids:[...adapters.keys()].sort(),verifier_id:options.verifier.verifier_id,policy_hash:options.verifier.policy_hash})
  validateConfiguration(config)
  const verify=options.verifier.verify.bind(options.verifier)
  const usedBatches=new Set<string>(); let busy=false
  return {
    async execute(input: FanoutInputV1): Promise<FanoutResultV1> {
      requireValue(!busy,'fanout busy: prior work may still be in-flight')
      validateRequest(input)
      requireValue(!usedBatches.has(input.batch_id),'batch_id already used')
      requireValue(usedBatches.size<MAX_FANOUT_BATCHES_PER_INSTANCE_V1,'batch lifetime capacity exhausted')
      // Capture every selection/task field synchronously, before the first await.
      const request=freeze({...structuredClone(input),providers:[...input.providers].sort()})
      busy=true; usedBatches.add(request.batch_id)
      let outstanding=0; let schedulingDone=false
      try {
        const prepared=await prepare(request,config)
        const bodies=request.providers.map((id,i)=>initialLeaf(id,prepared.selections[i]!))
        const eligible=bodies.map((leaf,i)=>leaf.selection.outcome==='SELECTED'?i:-1).filter(i=>i>=0)
        if(eligible.length>=request.min_verified) {
          for(const i of eligible) bodies[i]={...bodies[i]!,reason_code:'TIMEOUT_CAPACITY_HELD'}
          let next=0
          const worker=async()=>{
            for(;;) {
              const index=eligible[next++]; if(index===undefined)return
              const base=bodies[index]!; const controller=new AbortController()
              outstanding++
              const work=(async():Promise<LeafBody>=>{
                try {
                  const raw=await adapters.get(base.provider_id)!({snapshot:request.snapshot,registry:request.registry,task:prepared.task,current_generation:request.current_generation,max_observation_age_generations:request.max_observation_age_generations,signal:controller.signal})
                  const native=freeze(structuredClone(raw))
                  const native_receipt_root=await verifyNative(base.provider_id,prepared.task,base.selection,native)
                  const subject_root=await hash('AEGIS_PROVIDER_FANOUT_VERIFICATION_SUBJECT_V1',{request_root:prepared.request_root,provider_id:base.provider_id,native_receipt_root})
                  let evidence:{readonly passed:boolean;readonly evidence_hash:SHA256Hex}
                  try {
                    evidence=await verify(Object.freeze({provider_id:base.provider_id,task:prepared.task,output:native.output!.final_output,native_receipt_root,subject_root,signal:controller.signal}))
                    requireValue(typeof evidence.passed==='boolean' && isHash(evidence.evidence_hash),'malformed verifier evidence')
                  } catch {return {...base,status:'FAILED',reason_code:'VERIFIER_FAILED',dispatched:true}}
                  const verification=freeze({verifier_id:config.verifier_id,policy_hash:config.policy_hash,subject_root,passed:evidence.passed,evidence_hash:evidence.evidence_hash})
                  return {...base,status:evidence.passed?'VERIFIED':'VERIFIER_REJECTED',reason_code:evidence.passed?'NATIVE_RECEIPT_AND_VERIFIER_PASS':'VERIFIER_REJECTED',dispatched:true,native_result:native,verification}
                } catch {return {...base,status:'FAILED',reason_code:'ADAPTER_OR_NATIVE_RECEIPT_FAILED',dispatched:true}}
              })()
              // Work always resolves to a leaf. Late completion cannot edit bodies.
              void work.then(()=>{outstanding--;if(schedulingDone&&outstanding===0)busy=false})
              const timeout=Symbol('timeout'); let timer:ReturnType<typeof setTimeout>|undefined
              const result=await Promise.race([work,new Promise<typeof timeout>(resolve=>{timer=setTimeout(()=>resolve(timeout),request.timeout_ms)})])
              if(timer!==undefined)clearTimeout(timer)
              if(result===timeout) {
                controller.abort()
                bodies[index]={...base,status:'TIMED_OUT',reason_code:'DEADLINE_EXCEEDED_CANCELLATION_UNCONFIRMED',dispatched:true,cancellation_requested:true}
                // Do not reuse this slot while a non-cooperative runner is alive.
                return
              }
              bodies[index]=result
            }
          }
          await Promise.all(Array.from({length:Math.min(request.max_parallel,eligible.length)},worker))
        }
        return await finish(request,config,prepared.request_root,bodies)
      } finally {schedulingDone=true;if(outstanding===0)busy=false}
    },
  }
}

/** Independent structural replay. Does not rerun SDKs or authenticate provider
 * identities/verifier policy. Callers must trust the configured verifier separately. */
export async function certifyProviderNativeFanoutV1(input: FanoutInputV1, result: FanoutResultV1): Promise<boolean> {
  try {
    const request=freeze({...structuredClone(input),providers:[...input.providers].sort()})
    const receipt=result.receipt; const config=receipt.configuration
    const prepared=await prepare(request,config)
    requireValue(same(receipt.request,request) && receipt.request_root===prepared.request_root,'request mismatch')
    requireValue(receipt.leaves.length===request.providers.length,'leaf count mismatch')
    const bodies:LeafBody[]=[]
    for(let i=0;i<receipt.leaves.length;i++) {
      const leaf=receipt.leaves[i]!; const {leaf_root,...body}=leaf
      requireValue(leaf.provider_id===request.providers[i] && same(leaf.selection,prepared.selections[i]),'leaf selection/order mismatch')
      requireValue(leaf_root===await hash('AEGIS_PROVIDER_FANOUT_LEAF_V1',body),'leaf root mismatch')
      requireValue(leaf.cancellation_confirmed===false,'unproven cancellation')
      const selected=leaf.selection.outcome==='SELECTED'
      if(leaf.status==='VERIFIED'||leaf.status==='VERIFIER_REJECTED') {
        requireValue(selected && leaf.dispatched===true && leaf.cancellation_requested===false && leaf.native_result && leaf.verification,'missing verification')
        const native_receipt_root=await verifyNative(leaf.provider_id,prepared.task,leaf.selection,leaf.native_result)
        const v=leaf.verification
        requireValue(v.verifier_id===config.verifier_id && v.policy_hash===config.policy_hash && isHash(v.evidence_hash) && v.passed===(leaf.status==='VERIFIED'),'verifier mismatch')
        requireValue(v.subject_root===await hash('AEGIS_PROVIDER_FANOUT_VERIFICATION_SUBJECT_V1',{request_root:prepared.request_root,provider_id:leaf.provider_id,native_receipt_root}),'verification subject mismatch')
        requireValue(leaf.reason_code===(v.passed?'NATIVE_RECEIPT_AND_VERIFIER_PASS':'VERIFIER_REJECTED'),'verifier reason mismatch')
      } else {
        requireValue(leaf.native_result===null && leaf.verification===null,'failure contains unaccepted evidence')
        const permitted:Record<string,readonly string[]>={DENIED:['PROVIDER_SELECTION_DENIED'],NOT_DISPATCHED:['PREFLIGHT_QUORUM_NOT_MET','TIMEOUT_CAPACITY_HELD'],FAILED:['ADAPTER_OR_NATIVE_RECEIPT_FAILED','VERIFIER_FAILED'],TIMED_OUT:['DEADLINE_EXCEEDED_CANCELLATION_UNCONFIRMED']}
        requireValue(permitted[leaf.status]?.includes(leaf.reason_code),'invalid status/reason')
        requireValue(leaf.dispatched===(leaf.status==='FAILED'||leaf.status==='TIMED_OUT'),'invalid dispatch')
        requireValue(selected===(leaf.status!=='DENIED'),'invalid selection status')
        requireValue(leaf.cancellation_requested===(leaf.status==='TIMED_OUT'),'invalid cancellation')
      }
      bodies.push(body)
    }
    const selectedCount=prepared.selections.filter(s=>s.outcome==='SELECTED').length
    requireValue(selectedCount>=request.min_verified || bodies.every(b=>!b.dispatched),'preflight quorum violation')
    return same(result,await finish(request,config,prepared.request_root,bodies))
  } catch {return false}
}
