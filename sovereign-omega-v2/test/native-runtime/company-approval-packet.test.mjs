import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { createRequire } from 'node:module'

const ts = createRequire(import.meta.url)('typescript')
const src = readFileSync(
  new URL('../../src/sovereignty/company-approval-packet.ts', import.meta.url),
  'utf8',
)
const js = ts.transpileModule(src, {
  compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ES2022 },
}).outputText
const api = await import(
  'data:text/javascript;base64,' + Buffer.from(js).toString('base64')
)

const sha = async (domain, value) =>
  createHash('sha256').update(domain + '\n' + JSON.stringify(value)).digest('hex')

function packet(overrides = {}) {
  return {
    packet_id: 'p1',
    task_id: 't1',
    action_class: 'EXTERNAL_MESSAGE',
    target: 'recipient@example.test',
    action: 'send the reviewed message',
    reason: 'verified follow-up is due',
    evidence_refs: ['sha256:abc', 'gmail:thread-1'],
    risk_class: 'MEDIUM',
    cost_class: 'NONE',
    max_cost_minor_units: null,
    currency: null,
    rollback: 'cancel before send; no rollback after provider accepts message',
    expires_generation: '12',
    ...overrides,
  }
}

test('approval is bound to exact packet digest', async () => {
  const made = await api.createConsequentialActionPacketV1(packet(), sha)
  const grant = {
    packet_digest: made.packet_digest,
    decision: 'APPROVED',
    grant_id: 'g1',
    granted_generation: '10',
  }
  assert.equal(
    await api.verifyConsequentialActionGrantV1(
      made.packet_digest, made.packet, grant, '11', sha,
    ),
    true,
  )
  assert.equal(
    await api.verifyConsequentialActionGrantV1(
      '0'.repeat(64), made.packet, grant, '11', sha,
    ),
    false,
  )
})

test('expired packet cannot execute even with matching approval', async () => {
  const made = await api.createConsequentialActionPacketV1(packet(), sha)
  const grant = {
    packet_digest: made.packet_digest,
    decision: 'APPROVED',
    grant_id: 'g1',
    granted_generation: '10',
  }
  assert.equal(
    await api.verifyConsequentialActionGrantV1(
      made.packet_digest, made.packet, grant, '13', sha,
    ),
    false,
  )
})


test('packet substitution is rejected even with copied valid digest and grant', async () => {
  const made = await api.createConsequentialActionPacketV1(packet(), sha)
  const grant = {
    packet_digest: made.packet_digest,
    decision: 'APPROVED',
    grant_id: 'g1',
    granted_generation: '10',
  }
  const substituted = Object.freeze({
    ...made.packet,
    target: 'different-target.example.test',
  })
  assert.equal(
    await api.verifyConsequentialActionGrantV1(
      made.packet_digest, substituted, grant, '11', sha,
    ),
    false,
  )
})

test('cost-bearing action requires explicit bounded cost and currency', async () => {
  await assert.rejects(
    api.createConsequentialActionPacketV1(
      packet({ cost_class: 'BOUNDED', max_cost_minor_units: null, currency: null }),
      sha,
    ),
    /minor units/,
  )
  const made = await api.createConsequentialActionPacketV1(
    packet({
      action_class: 'FINANCIAL',
      cost_class: 'BOUNDED',
      max_cost_minor_units: 300000,
      currency: 'USD',
    }),
    sha,
  )
  assert.equal(made.packet.max_cost_minor_units, 300000)
})

test('duplicate evidence references fail closed', async () => {
  await assert.rejects(
    api.createConsequentialActionPacketV1(
      packet({ evidence_refs: ['same', 'same'] }),
      sha,
    ),
    /duplicate evidence_ref/,
  )
})
