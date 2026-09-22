// Concrete provider-native runtimes. No SDK import or provider call at construction.
// Invocation authorization is supplied by the host, never by task text or the model.
export type NativeProviderIdV1 = 'openai' | 'anthropic' | 'google-cloud'
export type NativeSdkPackageV1 = '@openai/agents' | '@anthropic-ai/claude-agent-sdk' | '@google/adk'
export interface NativeInvocationRequestV1 {
  readonly provider_id: NativeProviderIdV1
  readonly model: string
  readonly task: string
}
export interface ProviderNativeSdkRuntimeOptionsV1 {
  readonly models: { readonly openai: string; readonly anthropic: string; readonly google_cloud: string }
  readonly authorize: (request: NativeInvocationRequestV1) => boolean | Promise<boolean>
  readonly maxTurns?: number
  readonly maxOutputTokens?: number
  readonly maxEvents?: number
  readonly maxTaskChars?: number
  /** Host-owned module loader seam for offline tests; never populated from task JSON. */
  readonly loadSdk?: (specifier: NativeSdkPackageV1) => Promise<unknown>
}
interface OpenAIRunInput {
  readonly agent_name: 'AEGIS OpenAI Provider Agent'
  readonly instructions: string
  readonly task: string
}
interface ClaudeRunInput {
  readonly system_prompt: string
  readonly allowed_tools: readonly []
  readonly task: string
}
interface GoogleRunInput {
  readonly agent_name: 'aegis_google_provider_agent'
  readonly instruction: string
  readonly tools: readonly []
  readonly task: string
}
interface SessionOutput { readonly final_output: string; readonly session_id: string; readonly model: string }
export interface ProviderNativeSdkRunnersV1 {
  readonly openai: {run(input: OpenAIRunInput): Promise<{final_output: string; run_id: string; model: string}>}
  readonly anthropic: {run(input: ClaudeRunInput): Promise<SessionOutput>}
  readonly google_cloud: {run(input: GoogleRunInput): Promise<SessionOutput>}
}
type Dict = Record<string, unknown>
function object(value: unknown, label: string): Dict {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) throw new TypeError(`${label} must be an object`)
  return value as Dict
}
function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) throw new TypeError(`${label} must be non-empty text`)
  return value
}
function integer(value: unknown, fallback: number, upper: number, label: string): number {
  const n = value === undefined ? fallback : value
  if (typeof n !== 'number' || !Number.isSafeInteger(n) || n < 1 || n > upper) throw new TypeError(`invalid ${label}`)
  return n
}
function noTools(value: unknown): void {
  if (!Array.isArray(value) || value.length !== 0) throw new TypeError('native runtime tools must be empty')
}
function callable(value: unknown, label: string): void {
  if (typeof value !== 'function') throw new TypeError(`SDK missing ${label}`)
}
function stream(value: unknown): AsyncIterable<unknown> {
  if (!value || typeof (value as AsyncIterable<unknown>)[Symbol.asyncIterator] !== 'function') throw new TypeError('SDK did not return an async stream')
  return value as AsyncIterable<unknown>
}

export function createProviderNativeSdkRunnersV1(options: ProviderNativeSdkRuntimeOptionsV1): ProviderNativeSdkRunnersV1 {
  object(options, 'runtime options')
  const models = Object.freeze({
    openai: text(options.models?.openai, 'OpenAI model'),
    anthropic: text(options.models?.anthropic, 'Anthropic model'),
    google_cloud: text(options.models?.google_cloud, 'Google model'),
  })
  const authorize = options.authorize
  callable(authorize, 'host invocation authorizer')
  const load = options.loadSdk ?? ((specifier: NativeSdkPackageV1) => import(specifier) as Promise<unknown>)
  callable(load, 'SDK loader')
  const maxTurns = integer(options.maxTurns, 2, 8, 'maxTurns')
  const maxOutputTokens = integer(options.maxOutputTokens, 2048, 32768, 'maxOutputTokens')
  const maxEvents = integer(options.maxEvents, 64, 1024, 'maxEvents')
  const maxTaskChars = integer(options.maxTaskChars, 64000, 1000000, 'maxTaskChars')
  async function admit(provider_id: NativeProviderIdV1, model: string, task: string): Promise<void> {
    text(task, 'task')
    if (task.length > maxTaskChars) throw new TypeError('task exceeds character budget')
    if (await authorize(Object.freeze({provider_id, model, task})) !== true) throw new Error('NATIVE_INVOCATION_NOT_AUTHORIZED')
  }

  return Object.freeze({
    openai: Object.freeze({
      async run(input: OpenAIRunInput) {
        const task = text(input.task, 'task')
        const instructions = text(input.instructions, 'instructions')
        if (input.agent_name !== 'AEGIS OpenAI Provider Agent') throw new TypeError('unexpected OpenAI agent name')
        await admit('openai', models.openai, task)
        const sdk = object(await load('@openai/agents'), 'OpenAI SDK')
        callable(sdk.Agent, 'Agent'); callable(sdk.Runner, 'Runner')
        const Agent = sdk.Agent as new (config: Dict) => unknown
        const Runner = sdk.Runner as new (config: Dict) => {run(agent: unknown, task: string, options: Dict): Promise<unknown>}
        const agent = new Agent({
          name: 'AEGIS OpenAI Provider Agent', instructions, model: models.openai,
          tools: [], handoffs: [], mcpServers: [],
          modelSettings: {maxTokens: maxOutputTokens, store: false},
        })
        const runner = new Runner({tracingDisabled: true, traceIncludeSensitiveData: false})
        const result = object(await runner.run(agent, task, {maxTurns}), 'OpenAI result')
        return {
          final_output: text(result.finalOutput, 'OpenAI final output'),
          run_id: text(result.lastResponseId, 'OpenAI native response id'),
          model: models.openai,
        }
      },
    }),
    anthropic: Object.freeze({
      async run(input: ClaudeRunInput): Promise<SessionOutput> {
        noTools(input.allowed_tools)
        const task = text(input.task, 'task')
        const systemPrompt = text(input.system_prompt, 'system prompt')
        await admit('anthropic', models.anthropic, task)
        const sdk = object(await load('@anthropic-ai/claude-agent-sdk'), 'Claude Agent SDK')
        callable(sdk.query, 'query')
        const query = sdk.query as (config: Dict) => unknown
        const messages = stream(query({prompt: task, options: {
          model: models.anthropic, systemPrompt, maxTurns,
          tools: [], allowedTools: [], agents: {},
          permissionMode: 'dontAsk', allowDangerouslySkipPermissions: false,
          canUseTool: async () => ({behavior: 'deny', message: 'AEGIS V1 grants no tool authority.'}),
          settingSources: [], mcpServers: {}, strictMcpConfig: true, plugins: [],
          persistSession: false,
        }}))
        let terminal: SessionOutput | null = null
        let count = 0
        for await (const raw of messages) {
          if (++count > maxEvents) throw new Error('Claude native event budget exceeded')
          const message = object(raw, 'Claude message')
          if (message.type !== 'result') continue
          if (terminal !== null) throw new Error('duplicate Claude terminal result')
          if (message.subtype !== 'success' || message.is_error !== false) throw new Error('Claude did not return a successful terminal result')
          terminal = {
            final_output: text(message.result, 'Claude final output'),
            session_id: text(message.session_id, 'Claude native session id'),
            model: models.anthropic,
          }
        }
        if (terminal === null) throw new Error('Claude terminal result missing')
        return terminal
      },
    }),
    google_cloud: Object.freeze({
      async run(input: GoogleRunInput): Promise<SessionOutput> {
        noTools(input.tools)
        const task = text(input.task, 'task')
        const instruction = text(input.instruction, 'instruction')
        if (input.agent_name !== 'aegis_google_provider_agent') throw new TypeError('unexpected Google agent name')
        await admit('google-cloud', models.google_cloud, task)
        const sdk = object(await load('@google/adk'), 'Google ADK')
        callable(sdk.LlmAgent, 'LlmAgent'); callable(sdk.InMemoryRunner, 'InMemoryRunner'); callable(sdk.isFinalResponse, 'isFinalResponse')
        const LlmAgent = sdk.LlmAgent as new (config: Dict) => unknown
        const InMemoryRunner = sdk.InMemoryRunner as new (config: Dict) => {
          sessionService: {createSession(config: Dict): Promise<unknown>}
          runAsync(config: Dict): unknown
        }
        const isFinalResponse = sdk.isFinalResponse as (event: Dict) => boolean
        const agent = new LlmAgent({
          name: 'aegis_google_provider_agent', instruction, model: models.google_cloud,
          tools: [], subAgents: [], disallowTransferToParent: true, disallowTransferToPeers: true,
          generateContentConfig: {maxOutputTokens},
        })
        const appName = 'aegis_provider_native_v1'
        const userId = 'aegis-provider-agent'
        const runner = new InMemoryRunner({agent, appName, plugins: []})
        const session = object(await runner.sessionService.createSession({appName, userId}), 'Google session')
        const sessionId = text(session.id, 'Google native session id')
        const events = stream(runner.runAsync({
          userId, sessionId, newMessage: {role: 'user', parts: [{text: task}]},
          runConfig: {maxLlmCalls: maxTurns, saveInputBlobsAsArtifacts: false},
        }))
        let output: string | null = null
        let count = 0
        for await (const raw of events) {
          if (++count > maxEvents) throw new Error('Google native event budget exceeded')
          const event = object(raw, 'Google event')
          if (event.errorCode || event.errorMessage) throw new Error('Google native execution failed')
          const content = event.content === undefined ? {} : object(event.content, 'Google content')
          const parts = content.parts === undefined ? [] : content.parts
          if (!Array.isArray(parts)) throw new TypeError('Google parts must be an array')
          const data = parts.map(part => object(part, 'Google content part'))
          if (data.some(part => part.functionCall !== undefined)) throw new Error('Google unexpected tool call')
          if (!isFinalResponse(event)) continue
          if (event.author !== 'aegis_google_provider_agent') throw new Error('Google final author mismatch')
          if (output !== null) throw new Error('duplicate Google terminal result')
          output = text(data.filter(part => part.thought !== true && typeof part.text === 'string').map(part => part.text).join(''), 'Google final output')
        }
        if (output === null) throw new Error('Google terminal result missing')
        return {final_output: output, session_id: sessionId, model: models.google_cloud}
      },
    }),
  })
}
