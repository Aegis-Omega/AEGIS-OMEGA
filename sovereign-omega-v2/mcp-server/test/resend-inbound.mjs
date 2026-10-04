import assert from 'node:assert/strict'
import { runResendInbound } from '../dist/resend-inbound.js'

function fakeResult(overrides = {}) {
  return { pid: 1, output: [], stdout: '', stderr: '', status: 0, signal: null, error: undefined, ...overrides }
}

let captured
const validSpawn = (command, args, options) => {
  captured = { command, args, options }
  return fakeResult({ stdout: JSON.stringify({ status: 'VERIFIED_NOT_ADMITTED', codes: ['UNMAPPED_CAPABILITY'], external_effect: 'NOT_EXECUTED' }) + '\n' })
}
const request = { raw_body_base64: 'e30=', headers: [['Content-Type', 'application/json']], method: 'POST' }
const valid = runResendInbound('/repo', request, validSpawn)
assert.equal(valid.status, 'VERIFIED_NOT_ADMITTED')
assert.equal(valid.external_effect, 'NOT_EXECUTED')
assert.deepEqual(captured.args, ['/repo/scripts/resend_inbound_ingest.py'])
assert.equal(captured.options.cwd, '/repo')
assert.deepEqual(JSON.parse(captured.options.input), request)
assert.equal(captured.options.env, process.env)
assert.equal(captured.options.timeout, 15000)
assert.equal(captured.options.maxBuffer, 1048576)

assert.deepEqual(
  runResendInbound('/repo', request, () => fakeResult({ status: 1 })),
  { status: 'REJECTED', codes: ['RESEND_INGEST_UNAVAILABLE'], external_effect: 'NOT_EXECUTED' },
)
assert.deepEqual(
  runResendInbound('/repo', request, () => fakeResult({ stdout: 'not-json' })),
  { status: 'REJECTED', codes: ['RESEND_INGEST_RESPONSE_INVALID'], external_effect: 'NOT_EXECUTED' },
)
assert.deepEqual(
  runResendInbound('/repo', request, () => fakeResult({ stdout: JSON.stringify({ status: 'REJECTED', external_effect: 'EXECUTED' }) })),
  { status: 'REJECTED', codes: ['RESEND_INGEST_RESPONSE_INVALID'], external_effect: 'NOT_EXECUTED' },
)
assert.deepEqual(
  runResendInbound('/repo', request, () => fakeResult({ stdout: JSON.stringify({ status: 'REJECTED', codes: [1], external_effect: 'NOT_EXECUTED' }) })),
  { status: 'REJECTED', codes: ['RESEND_INGEST_RESPONSE_INVALID'], external_effect: 'NOT_EXECUTED' },
)
console.log('RESEND_INBOUND_MCP_WRAPPER_PASS local process only; malformed output fails closed')
