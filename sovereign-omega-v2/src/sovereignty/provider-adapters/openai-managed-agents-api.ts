// AEGIS OpenAI Managed Agents API Runner V1
// T1 engineering contract; authority_effect = NONE.
// Host supplies the live OpenAI client binding. Task text never supplies tools,
// credentials, project selection, or authority.

export type ManagedStatusV1 = 'idle' | 'in_progress' | 'requires_action' | 'failed'
export type ManagedToolEffectV1 = 'NONE' | 'LOCAL_WORKSPACE' | 'EXTERNAL_MUTATION'
export type ManagedReasoningV1 = 'low' | 'medium' | 'high' | 'xhigh' | 'max'

export interface ManagedToolV1 {
  readonly id: string
  readonly effect: ManagedToolEffectV1
  readonly api_tool: Readonly<Record<string, unknown>>
}
export interface ManagedSnapshotV1 {
  readonly id: string
  readonly status: ManagedStatusV1
  readonly required_actions?: readonly { readonly type: string; readonly name?: string }[]
  readonly error?: string | null
  readonly usage?: Readonly<Record<string, number>> | null
}
export interface ManagedBindingV1 {
  create(input: Readonly<Record<string, unknown>>): Promise<ManagedSnapshotV1>
  retrieve(id: string): Promise<ManagedSnapshotV1>
  finalOutput(id: string): Promise<string>
}
export interface ManagedRunnerOptionsV1 {
  readonly binding: ManagedBindingV1
  readonly model: string
  readonly reasoning_effort?: ManagedReasoningV1
  readonly environment_type?: 'openai_hosted' | 'self_hosted' | 'none'
  readonly capability_directories?: readonly string[]
  readonly vault_ids?: readonly string[]
  readonly tools?: readonly ManagedToolV1[]
  readonly max_concurrent_subagents?: number
  readonly max_polls?: number
  readonly poll?: (attempt: number, id: string) => Promise<void>
  readonly metadata?: Readonly<Record<string, string>>
}

function text(v: unknown, label: string): string {
  if (typeof v !== 'string' || !v.trim()) throw new TypeError(label + ' must be non-empty')
  return v
}
function integer(v: unknown, fallback: number, min: number, max: number, label: string): number {
  const n = v === undefined ? fallback : v
  if (typeof n !== 'number' || !Number.isSafeInteger(n) || n < min || n > max) throw new TypeError('invalid ' + label)
  return n
}
function snapshot(v: ManagedSnapshotV1): ManagedSnapshotV1 {
  text(v?.id, 'managed session id')
  if (!['idle', 'in_progress', 'requires_action', 'failed'].includes(v.status)) throw new TypeError('invalid managed status')
  return v
}

export function createOpenAIManagedAgentsApiRunnerV1(options: ManagedRunnerOptionsV1) {
  if (!options?.binding || typeof options.binding.create !== 'function' ||
      typeof options.binding.retrieve !== 'function' || typeof options.binding.finalOutput !== 'function') {
    throw new TypeError('managed binding incomplete')
  }
  const model = text(options.model, 'model')
  const reasoning = options.reasoning_effort ?? 'high'
  if (!['low', 'medium', 'high', 'xhigh', 'max'].includes(reasoning)) throw new TypeError('invalid reasoning effort')
  const environment = options.environment_type ?? 'openai_hosted'
  if (!['openai_hosted', 'self_hosted', 'none'].includes(environment)) throw new TypeError('invalid environment')
  const maxSubagents = integer(options.max_concurrent_subagents, 3, 1, 8, 'max_concurrent_subagents')
  const maxPolls = integer(options.max_polls, 120, 1, 10_000, 'max_polls')
  const poll = options.poll ?? (async () => undefined)
  const vaultIds = Object.freeze([...(options.vault_ids ?? [])].map(v => text(v, 'vault id')))
  const capabilityDirs = Object.freeze([...(options.capability_directories ?? [])].map(v => text(v, 'capability directory')))
  const metadata = Object.freeze({ ...(options.metadata ?? {}) })
  const tools = Object.freeze([...(options.tools ?? [])].map(tool => {
    text(tool?.id, 'tool id')
    if (!['NONE', 'LOCAL_WORKSPACE', 'EXTERNAL_MUTATION'].includes(tool.effect)) throw new TypeError('invalid tool effect')
    if (tool.effect === 'EXTERNAL_MUTATION') throw new Error('OPENAI_MANAGED_EXTERNAL_TOOL_NOT_ADMITTED:' + tool.id)
    if (!tool.api_tool || typeof tool.api_tool !== 'object' || Array.isArray(tool.api_tool)) throw new TypeError('invalid API tool:' + tool.id)
    return Object.freeze({ ...tool.api_tool })
  }))

  return Object.freeze({
    async run(input: { readonly instructions: string; readonly task: string }) {
      const instructions = text(input?.instructions, 'instructions')
      const task = text(input?.task, 'task')
      const request = Object.freeze({
        agent: Object.freeze({
          name: 'AEGIS OpenAI Company Agent', model, instructions,
          reasoning: Object.freeze({ effort: reasoning }),
          multi_agent: Object.freeze({ enabled: true, max_concurrent_subagents: maxSubagents }),
          tools,
        }),
        environment: Object.freeze({
          type: environment,
          ...(capabilityDirs.length ? { capability_directories: capabilityDirs } : {}),
        }),
        vault_ids: vaultIds, input: task, metadata, stream: false,
      })
      let state = snapshot(await options.binding.create(request))
      const id = state.id
      for (let attempt = 0; state.status === 'in_progress'; attempt += 1) {
        if (attempt >= maxPolls) throw new Error('OPENAI_MANAGED_SESSION_POLL_BUDGET_EXCEEDED')
        await poll(attempt + 1, id)
        state = snapshot(await options.binding.retrieve(id))
        if (state.id !== id) throw new Error('OPENAI_MANAGED_SESSION_ID_DRIFT')
      }
      if (state.status === 'requires_action') {
        const names = (state.required_actions ?? []).map(a => a.name ?? a.type).join(',')
        throw new Error('OPENAI_MANAGED_SESSION_REQUIRES_ACTION' + (names ? ':' + names : ''))
      }
      if (state.status === 'failed') throw new Error('OPENAI_MANAGED_SESSION_FAILED' + (state.error ? ':' + state.error : ''))
      if (state.status !== 'idle') throw new Error('OPENAI_MANAGED_SESSION_NOT_TERMINAL')
      return Object.freeze({
        final_output: text(await options.binding.finalOutput(id), 'final output'),
        session_id: id, model, status: 'idle' as const, usage: state.usage ?? null,
        authority_effect: 'NONE' as const,
      })
    },
  })
}
