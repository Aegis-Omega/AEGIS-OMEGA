import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const ts = createRequire(import.meta.url)('typescript')

async function load(path) {
  const src = readFileSync(new URL('../../src/' + path, import.meta.url), 'utf8')
  const js = ts.transpileModule(src, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
    reportDiagnostics: true,
  }).outputText
  return import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'))
}

const bindingModule = await load(
  'sovereignty/provider-adapters/openai-managed-agents-client-binding.ts',
)
const router = await load('sovereignty/company-model-router.ts')

function client(items) {
  const calls = []
  return {
    calls,
    beta: {
      agents: {
        sessions: {
          create: async (input) => (
            calls.push(['create', input]),
            {
              id: 's1',
              status: 'idle',
              required_actions: [],
              usage: { input_tokens: 10, output_tokens: 2, total_tokens: 12 },
            }
          ),
          retrieve: async (id) => ({ id, status: 'idle', required_actions: [] }),
          items: {
            list: (id, query) => (
              calls.push(['items', id, query]),
              { data: items }
            ),
          },
        },
      },
    },
  }
}

test('client binding maps documented session fields and terminal assistant output', async () => {
  const api = client([{
    id: 'm1',
    type: 'message',
    role: 'assistant',
    status: 'completed',
    phase: 'final_answer',
    content: [{ type: 'output_text', text: 'done' }],
  }])
  const binding = bindingModule.createOpenAIManagedAgentsClientBindingV1(api)
  const session = await binding.create({ agent: {} })
  assert.equal(session.id, 's1')
  assert.equal(session.usage.total_tokens, 12)
  assert.equal(await binding.finalOutput('s1'), 'done')
  assert.deepEqual(api.calls.at(-1), ['items', 's1', { order: 'asc', limit: 100 }])
})

test('binding ignores user/partial content and rejects missing terminal assistant output', async () => {
  const api = client([
    {
      type: 'message',
      role: 'user',
      status: 'completed',
      content: [{ type: 'input_text', text: 'x' }],
    },
    {
      type: 'message',
      role: 'assistant',
      status: 'in_progress',
      phase: 'final_answer',
      content: [{ type: 'output_text', text: 'partial' }],
    },
  ])
  const binding = bindingModule.createOpenAIManagedAgentsClientBindingV1(api)
  await assert.rejects(binding.finalOutput('s1'), /FINAL_OUTPUT_MISSING/)
})

test('completed commentary is not accepted as terminal output', async () => {
  const api = client([{
    type: 'message',
    role: 'assistant',
    status: 'completed',
    phase: 'commentary',
    content: [{ type: 'output_text', text: 'intermediate' }],
  }])
  const binding = bindingModule.createOpenAIManagedAgentsClientBindingV1(api)
  await assert.rejects(binding.finalOutput('s1'), /FINAL_OUTPUT_MISSING/)
})

test('binding supports async-iterable cursor pages', async () => {
  const api = client([])
  api.beta.agents.sessions.items.list = () => ({
    async *[Symbol.asyncIterator]() {
      yield {
        type: 'message',
        role: 'assistant',
        status: 'completed',
        content: [{ type: 'output_text', text: 'streamed' }],
      }
    },
  })
  const binding = bindingModule.createOpenAIManagedAgentsClientBindingV1(api)
  assert.equal(await binding.finalOutput('s1'), 'streamed')
})

test('model router uses Luna Terra Sol Astra with explicit complimentary boundary', () => {
  assert.equal(
    router.routeCompanyModelV1({ work_class: 'INTAKE', tools_required: false }).model,
    'gpt-5.6-luna',
  )
  assert.equal(
    router.routeCompanyModelV1({ work_class: 'ROUTINE', tools_required: false }).model,
    'gpt-5.6-terra',
  )
  assert.equal(
    router.routeCompanyModelV1({ work_class: 'DEEP_REASONING', tools_required: false }).model,
    'gpt-5.6-sol',
  )
  assert.equal(
    router.routeCompanyModelV1({
      work_class: 'ROUTINE',
      tools_required: false,
      computer_use: true,
    }).model,
    'gpt-6-astra',
  )
  assert.equal(
    router.routeCompanyModelV1({ work_class: 'ROUTINE', tools_required: true })
      .tool_use_excluded_from_complimentary,
    true,
  )
})
