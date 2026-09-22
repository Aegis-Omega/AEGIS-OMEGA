import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const ts = createRequire(import.meta.url)('typescript')
const source = readFileSync(
  new URL('../../src/sovereignty/company-work-graph.ts', import.meta.url),
  'utf8',
)
const js = ts.transpileModule(source, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const api = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64'),
)
const hash = async (domain, value) =>
  createHash('sha256').update(domain + '\n' + JSON.stringify(value)).digest('hex')
const taskDigest = 'a'.repeat(64)

const graph = [
  { task_id: 'research', depends_on: [] },
  { task_id: 'draft', depends_on: ['research'] },
  { task_id: 'verify', depends_on: ['draft'] },
]

test('topological validation is deterministic', () => {
  assert.deepEqual(
    api.validateCompanyWorkGraphV1([...graph].reverse()).map((x) => x.task_id),
    ['research', 'draft', 'verify'],
  )
})

test('missing, duplicate and cyclic dependencies fail closed', () => {
  assert.throws(
    () => api.validateCompanyWorkGraphV1([{ task_id: 'a', depends_on: ['missing'] }]),
    /missing dependency/,
  )
  assert.throws(
    () => api.validateCompanyWorkGraphV1([
      { task_id: 'a', depends_on: [] },
      { task_id: 'a', depends_on: [] },
    ]),
    /duplicate task_id/,
  )
  assert.throws(
    () => api.validateCompanyWorkGraphV1([
      { task_id: 'a', depends_on: ['b'] },
      { task_id: 'b', depends_on: ['a'] },
    ]),
    /CYCLE/,
  )
})

test('only dependency-satisfied planned tasks become ready', () => {
  assert.deepEqual(
    api.readyCompanyTasksV1(
      graph,
      { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
    ),
    ['research'],
  )
  assert.deepEqual(
    api.readyCompanyTasksV1(
      graph,
      { research: 'VERIFIED', draft: 'PLANNED', verify: 'PLANNED' },
    ),
    ['draft'],
  )
  assert.deepEqual(
    api.readyCompanyTasksV1(
      graph,
      { research: 'VERIFIED', draft: 'REJECTED', verify: 'PLANNED' },
    ),
    [],
  )
})

test('ready set is bounded and lexically stable', () => {
  const g = [
    { task_id: 'b', depends_on: [] },
    { task_id: 'a', depends_on: [] },
    { task_id: 'c', depends_on: [] },
  ]
  const s = { a: 'PLANNED', b: 'PLANNED', c: 'PLANNED' }
  assert.deepEqual(api.readyCompanyTasksV1(g, s, 2), ['a', 'b'])
})

test('lease can only be created for a ready task', async () => {
  await assert.rejects(
    api.createCompanyTaskLeaseV1({
      graph,
      states: { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
      task_id: 'draft',
      worker_id: 'w1',
      task_digest: taskDigest,
      current_generation: '10',
      ttl_generations: 2,
    }, hash),
    /NOT_READY/,
  )
  const lease = await api.createCompanyTaskLeaseV1({
    graph,
    states: { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
    task_id: 'research',
    worker_id: 'w1',
    task_digest: taskDigest,
    current_generation: '10',
    ttl_generations: 2,
  }, hash)
  assert.equal(lease.acquired_generation, '10')
  assert.equal(lease.expires_generation, '12')
  assert.equal(lease.external_authority, 'NOT_GRANTED')
})

test('exact lease verifies only inside generation interval and task digest', async () => {
  const lease = await api.createCompanyTaskLeaseV1({
    graph,
    states: { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
    task_id: 'research',
    worker_id: 'w1',
    task_digest: taskDigest,
    current_generation: '10',
    ttl_generations: 2,
  }, hash)
  assert.equal(await api.verifyCompanyTaskLeaseV1(lease, taskDigest, '11', hash), true)
  assert.equal(await api.verifyCompanyTaskLeaseV1(lease, taskDigest, '13', hash), false)
  assert.equal(
    await api.verifyCompanyTaskLeaseV1(lease, 'b'.repeat(64), '11', hash),
    false,
  )
})

test('lease substitution fails digest verification', async () => {
  const lease = await api.createCompanyTaskLeaseV1({
    graph,
    states: { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
    task_id: 'research',
    worker_id: 'w1',
    task_digest: taskDigest,
    current_generation: '10',
    ttl_generations: 2,
  }, hash)
  assert.equal(
    await api.verifyCompanyTaskLeaseV1(
      { ...lease, worker_id: 'other' },
      taskDigest,
      '11',
      hash,
    ),
    false,
  )
})

test('state domain mismatch and excessive TTL fail closed', async () => {
  assert.throws(
    () => api.readyCompanyTasksV1(
      graph,
      { research: 'PLANNED', draft: 'PLANNED' },
    ),
    /domain mismatch/,
  )
  await assert.rejects(
    api.createCompanyTaskLeaseV1({
      graph,
      states: { research: 'PLANNED', draft: 'PLANNED', verify: 'PLANNED' },
      task_id: 'research',
      worker_id: 'w1',
      task_digest: taskDigest,
      current_generation: '10',
      ttl_generations: 17,
      max_ttl_generations: 16,
    }, hash),
    /ttl_generations/,
  )
})
