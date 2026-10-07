import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
const moduleURL = new URL('../public/labs/mcp/verify.mjs', import.meta.url)
const fixture = name => readFileSync(new URL(`../public/labs/mcp/${name}`, import.meta.url))

test('public verifier accepts only the pinned recorded archive, never a live-execution claim', async () => {
  assert.ok(existsSync(moduleURL), 'Missing public recorded-evidence verifier')
  const { verifyArchive } = await import(moduleURL)
  const result = await verifyArchive(fixture('receipt.json'), fixture('trace.json'))
  assert.equal(result.status, 'RECORDED_EVIDENCE_VERIFIED')
  assert.equal(result.source_commit, '897fa55556a639a04a67d25481b7a432af007d04')
  assert.equal(result.external_effect, 'NOT_EXECUTED')
  assert.equal(result.live_execution, false)
  assert.equal(result.bridge_requests_observed, 0)
  assert.equal(result.exchanges.length, 5)
})

test('altered, empty, oversized or swapped downloaded bytes are rejected', async t => {
  const { verifyArchive } = await import(moduleURL)
  const receipt = fixture('receipt.json'), trace = fixture('trace.json')
  const cases = [
    ['altered receipt', Buffer.concat([receipt, Buffer.from(' ')]), trace],
    ['altered trace', receipt, Buffer.concat([trace, Buffer.from(' ')] )],
    ['empty trace', receipt, Buffer.from('')],
    ['oversize', receipt, Buffer.alloc(262145)],
    ['swapped artifacts', trace, receipt],
  ]
  for (const [name, a, b] of cases) await t.test(name, async () => assert.rejects(() => verifyArchive(a, b)))
})

test('semantic checks reject forged authority, protocol and policy claims independently of byte pins', async t => {
  const { inspectArchive } = await import(moduleURL)
  const originalReceipt = JSON.parse(fixture('receipt.json')), originalTrace = JSON.parse(fixture('trace.json'))
  const edits = [
    ['wrong source', (r) => { r.source_commit = '0'.repeat(40) }],
    ['failed build', (r) => { r.stages[0].exit_code = 1 }],
    ['skipped stage', (r) => { r.stages.pop() }],
    ['positive bridge count', (_, b) => { b.bridge_requests_observed = 1 }],
    ['missing exchange', (_, b) => { b.trace.pop() }],
    ['mismatched response id', (_, b) => { b.trace[4].response.id = 99 }],
    ['missing session', (_, b) => { b.trace[4].request_headers.session_present = false }],
    ['changed policy bytes', (_, b) => { const p = JSON.parse(b.trace[3].response.result.content[0].text); p.policy_json += ' '; b.trace[3].response.result.content[0].text = JSON.stringify(p) }],
    ['forged admission', (_, b) => { const p = JSON.parse(b.trace[4].response.result.content[0].text); p.authority.outcome = 'ADMITTED'; b.trace[4].response.result.content[0].text = JSON.stringify(p) }],
    ['tool-error erased', (_, b) => { b.trace[4].response.result.isError = false }],
    ['execution claimed', (_, b) => { const p = JSON.parse(b.trace[4].response.result.content[0].text); p.external_effect = 'EXECUTED'; b.trace[4].response.result.content[0].text = JSON.stringify(p) }],
  ]
  for (const [name, edit] of edits) await t.test(name, async () => {
    const r = structuredClone(originalReceipt), b = structuredClone(originalTrace); edit(r, b)
    await assert.rejects(() => inspectArchive(r, b))
  })
})

test('verification does not modify evidence and its JSON is safe to display as text', async () => {
  const { verifyArchive } = await import(moduleURL)
  const r = fixture('receipt.json'), b = fixture('trace.json')
  const rb = Buffer.from(r), bb = Buffer.from(b)
  await verifyArchive(r, b); assert.deepEqual(r, rb); assert.deepEqual(b, bb)
})
