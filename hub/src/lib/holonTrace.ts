/**
 * HOLON MAXIMUS OPTIMUS — bounded, human-led creative lineage.
 * An SHA-256 chain detects accidental/unauthorized edits to exported records.
 * It is NOT a signature, authorship authentication, timestamp attestation,
 * authorization receipt, or proof that a pasted model suggestion came from a model.
 */
export const HOLON_SCHEMA = 'AEGIS_HOLON_MAXIMUS_TRACE_V1' as const
export const MAX_HOLON_EVENTS = 128
export const MAX_HOLON_TEXT = 1600
export type HolonRole = 'human' | 'model' | 'agent'
export type HolonOrigin = 'direct_human' | 'pasted_external'
export type HolonKind = 'seed' | 'branch' | 'select' | 'weave' | 'artifact'
export type HolonLens = 'imagination' | 'structure' | 'critique' | 'none'
export type HolonEvent = Readonly<{
  id: string; seq: number; kind: HolonKind; actor: HolonRole; origin: HolonOrigin;
  lens: HolonLens; text: string; parents: readonly string[];
  recorded_at: string; previous_hash: string; hash: string
}>
export type HolonTrace = Readonly<{schema: typeof HOLON_SCHEMA; events: readonly HolonEvent[]}>
export type HolonDraft = Readonly<{
  id: string; kind: HolonKind; actor: HolonRole; origin: HolonOrigin;
  lens: HolonLens; text: string; parents: readonly string[]; recorded_at: string
}>
export const emptyHolonTrace = (): HolonTrace => ({schema: HOLON_SCHEMA, events: []})
function fail(message: string): never { throw new Error('HOLON_TRACE_INVALID: ' + message) }
function record(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value)
}
function hex(buffer: ArrayBuffer): string {
  return Array.from(new Uint8Array(buffer), b => b.toString(16).padStart(2, '0')).join('')
}
async function digest(value: object): Promise<string> {
  return hex(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(JSON.stringify(value))))
}
function payload(d: HolonDraft, seq: number, previous_hash: string) {
  return {
    id:d.id, seq, kind:d.kind, actor:d.actor, origin:d.origin,
    lens:d.lens, text:d.text, parents:[...d.parents],
    recorded_at:d.recorded_at, previous_hash
  }
}
function checkDraft(d: HolonDraft, previous: readonly HolonEvent[]): void {
  if (!record(d)) fail('draft is not an object')
  if (typeof d.id !== 'string' || !/^[a-zA-Z0-9-]{10,80}$/.test(d.id)) fail('invalid id')
  if (previous.some(e=>e.id===d.id)) fail('duplicate id')
  if (!['seed','branch','select','weave','artifact'].includes(d.kind)) fail('invalid kind')
  if (!['human','model','agent'].includes(d.actor)) fail('invalid actor')
  if (!['direct_human','pasted_external'].includes(d.origin)) fail('invalid origin')
  if (!['imagination','structure','critique','none'].includes(d.lens)) fail('invalid lens')
  if (typeof d.text!=='string' || !d.text.trim() || d.text.length>MAX_HOLON_TEXT) fail('invalid text')
  if (!Array.isArray(d.parents) || d.parents.length>4 || new Set(d.parents).size!==d.parents.length) fail('invalid parents')
  if (typeof d.recorded_at!=='string' || !Number.isFinite(Date.parse(d.recorded_at))) fail('invalid time')
  if ((d.actor==='human') !== (d.origin==='direct_human')) fail('actor/source disagreement')
  if (d.kind!=='branch' && d.actor!=='human') fail('only a human may decide or finalize')
  if (d.kind==='seed' && (previous.length!==0 || d.parents.length!==0 || d.lens!=='none')) fail('seed must be first and parentless')
  if (d.kind!=='seed' && (!previous.length || !d.parents.length)) fail('missing parents')
  const byId = new Map(previous.map(e=>[e.id,e]))
  if (d.parents.some(id=>typeof id!=='string'||!byId.has(id))) fail('parent not in prior history')
  if (d.kind==='branch' && (d.parents.length!==1 || !['seed','branch','weave'].includes(byId.get(d.parents[0])!.kind))) fail('branch must extend a source idea')
  if (d.kind==='select' && (d.parents.length!==1 || byId.get(d.parents[0])?.kind!=='branch')) fail('human choice must identify a branch')
  if (d.kind==='weave') {
    if (d.parents.length<2 || d.parents.some(id=>byId.get(id)?.kind!=='select')) fail('weave requires two human choices')
    if (new Set(d.parents.map(id=>byId.get(id)!.parents[0])).size!==d.parents.length) fail('cannot weave duplicate ideas')
  }
  if (d.kind==='artifact' && (d.parents.length!==1 || byId.get(d.parents[0])?.kind!=='weave')) fail('artifact requires a human weave')
}
export async function verifyHolonTrace(value: unknown): Promise<HolonTrace> {
  if (!record(value) || value.schema!==HOLON_SCHEMA || !Array.isArray(value.events)) fail('invalid schema')
  if (value.events.length>MAX_HOLON_EVENTS) fail('event budget exceeded')
  let accepted: HolonEvent[]=[]
  for (const raw of value.events) {
    if (!record(raw)) fail('malformed event')
    const d = {id:raw.id,kind:raw.kind,actor:raw.actor,origin:raw.origin,
      lens:raw.lens,text:raw.text,parents:raw.parents,recorded_at:raw.recorded_at} as HolonDraft
    checkDraft(d,accepted)
    const previous_hash=accepted.at(-1)?.hash??'GENESIS'
    if (raw.seq!==accepted.length+1 || raw.previous_hash!==previous_hash) fail('chain order mismatch')
    const canonical=payload(d,accepted.length+1,previous_hash)
    const expected=await digest(canonical)
    if (raw.hash!==expected) fail('hash mismatch')
    if (Object.keys(raw).sort().join('|')!==[...Object.keys(canonical),'hash'].sort().join('|')) fail('unexpected fields')
    accepted.push({...canonical,hash:expected})
  }
  return {schema:HOLON_SCHEMA,events:accepted}
}
export async function appendHolonEvent(value: unknown, draft: HolonDraft): Promise<HolonTrace> {
  const journal=await verifyHolonTrace(value)
  if (journal.events.length>=MAX_HOLON_EVENTS) fail('event budget exceeded')
  checkDraft(draft,journal.events)
  const previous_hash=journal.events.at(-1)?.hash??'GENESIS'
  const canonical=payload(draft,journal.events.length+1,previous_hash)
  const hash=await digest(canonical)
  return {schema:HOLON_SCHEMA,events:[...journal.events,{...canonical,hash}]}
}
export function selectedHolonBranches(journal: HolonTrace): readonly HolonEvent[] {
  const branches=new Map(journal.events.filter(e=>e.kind==='branch').map(e=>[e.id,e]))
  const seen=new Set<string>()
  const selected:HolonEvent[]=[]
  for(const e of journal.events) if(e.kind==='select') {
    const id=e.parents[0]
    if(!seen.has(id)&&branches.has(id)){selected.push(branches.get(id)!);seen.add(id)}
  }
  return selected
}
