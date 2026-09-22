import type { ManagedBindingV1, ManagedSnapshotV1 } from './openai-managed-agents-api.js'

type Dict = Record<string, unknown>

export interface OpenAIManagedClientLikeV1 {
  readonly beta: { readonly agents: { readonly sessions: {
    create(input: Readonly<Record<string, unknown>>): Promise<unknown>
    retrieve(sessionId: string): Promise<unknown>
    readonly items: {
      list(sessionId: string, query?: Readonly<Record<string, unknown>>): unknown
    }
  } } }
}

function object(value: unknown, label: string): Dict {
  if (!value || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError(`${label} must be object`)
  }
  return value as Dict
}

function text(value: unknown, label: string): string {
  if (typeof value !== 'string' || !value.trim()) {
    throw new TypeError(`${label} must be non-empty`)
  }
  return value
}

function normalizeSession(raw: unknown): ManagedSnapshotV1 {
  const value = object(raw, 'OpenAI agent session')
  const id = text(value.id, 'OpenAI agent session id')
  const status = value.status
  if (!['idle', 'in_progress', 'requires_action', 'failed'].includes(String(status))) {
    throw new TypeError('invalid OpenAI agent session status')
  }

  const actionsRaw = value.required_actions ?? []
  if (!Array.isArray(actionsRaw)) throw new TypeError('required_actions must be array')
  const required_actions = actionsRaw.map((entry) => {
    const action = object(entry, 'required action')
    return Object.freeze({
      type: text(action.type, 'required action type'),
      ...(typeof action.name === 'string' ? { name: action.name } : {}),
    })
  })

  const usageRaw = value.usage
  let usage: Readonly<Record<string, number>> | null = null
  if (usageRaw !== null && usageRaw !== undefined) {
    const source = object(usageRaw, 'session usage')
    const clean: Record<string, number> = {}
    for (const key of ['input_tokens', 'output_tokens', 'total_tokens']) {
      if (source[key] === undefined) continue
      if (typeof source[key] !== 'number' || !Number.isFinite(source[key]) || (source[key] as number) < 0) {
        throw new TypeError('invalid session usage')
      }
      clean[key] = source[key] as number
    }
    usage = Object.freeze(clean)
  }

  return Object.freeze({
    id,
    status: status as ManagedSnapshotV1['status'],
    required_actions,
    error: typeof value.error === 'string' ? value.error : null,
    usage,
  })
}

async function collectItems(source: unknown): Promise<unknown[]> {
  if (source && typeof (source as AsyncIterable<unknown>)[Symbol.asyncIterator] === 'function') {
    const output: unknown[] = []
    for await (const item of source as AsyncIterable<unknown>) output.push(item)
    return output
  }

  const resolved = await Promise.resolve(source)
  const page = object(resolved, 'OpenAI items page')
  if (!Array.isArray(page.data)) throw new TypeError('OpenAI items page missing data')
  return page.data
}

function outputText(item: unknown): string | null {
  const value = object(item, 'OpenAI session item')
  if (value.type !== 'message' || value.role !== 'assistant' || value.status !== 'completed') return null
  if (!Array.isArray(value.content)) throw new TypeError('assistant message content must be array')

  const parts = value.content
    .map((part) => object(part, 'assistant content part'))
    .filter((part) => part.type === 'output_text' && typeof part.text === 'string')
    .map((part) => part.text as string)

  const joined = parts.join('')
  return joined.trim() ? joined : null
}

export function createOpenAIManagedAgentsClientBindingV1(
  client: OpenAIManagedClientLikeV1,
): ManagedBindingV1 {
  if (
    !client?.beta?.agents?.sessions ||
    typeof client.beta.agents.sessions.create !== 'function' ||
    typeof client.beta.agents.sessions.retrieve !== 'function' ||
    typeof client.beta.agents.sessions.items?.list !== 'function'
  ) {
    throw new TypeError('OpenAI Agents client surface unavailable')
  }

  return Object.freeze({
    async create(input: Readonly<Record<string, unknown>>) {
      return normalizeSession(await client.beta.agents.sessions.create(input))
    },

    async retrieve(id: string) {
      return normalizeSession(
        await client.beta.agents.sessions.retrieve(text(id, 'session id')),
      )
    },

    async finalOutput(id: string) {
      const items = await collectItems(
        client.beta.agents.sessions.items.list(
          text(id, 'session id'),
          { order: 'asc', limit: 100 },
        ),
      )
      const outputs = items
        .map(outputText)
        .filter((value): value is string => value !== null)

      if (!outputs.length) throw new Error('OPENAI_MANAGED_FINAL_OUTPUT_MISSING')
      return outputs.at(-1) as string
    },
  })
}
