import assert from 'node:assert/strict'
import { test } from 'node:test'
import {
  encodeAdmittedGovernanceMutation,
  governanceEventDigest,
} from '../dist/bridgeControl.js'

function candidate(overrides = {}) {
  return {
    decision: {
      proposal_id: 'E4:test:0001', component_id: 'bridge-test-component', accepted: true,
      lcb_value: 0.125, e_value: 32, risk_spent: 0.05,
      sample_size: 20, method: 'anytime_valid_bernstein',
    },
    capabilityClass: 'SELF_MODIFYING',
    operatorId: 'bridge-test-operator',
    bridgeEpochId: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    sequence: 17,
    payload: Buffer.from('hello', 'utf8'),
    verifier: Uint8Array.of(0x00),
    context: Buffer.from([0x00, 0x7f, 0xff]),
    ...overrides,
  }
}

test('two deterministic frames bind the same exact bytes', () => {
  const source = candidate()
  const first = encodeAdmittedGovernanceMutation(source)
  const second = encodeAdmittedGovernanceMutation(source)
  assert.deepEqual(first, second)
  assert.equal(first.gate_signal.proposal_id, source.decision.proposal_id)
  assert.equal(first.gate_signal.component_id, 'bridge-test-component')
  assert.equal(first.gate_signal.operator_id, 'bridge-test-operator')
  assert.equal(first.gate_signal.capability_class, 'SELF_MODIFYING')
  assert.equal(first.gate_signal.bridge_epoch_id, source.bridgeEpochId)
  assert.equal(first.event.bridge_epoch_id, source.bridgeEpochId)
  assert.equal(first.gate_signal.sequence, 17)
  assert.equal(first.gate_signal.accepted, true)
  assert.equal(first.gate_signal.lcb, 0.125)
  assert.equal(first.gate_signal.e_value, 32)
  assert.equal(first.gate_signal.risk_spent, 0.05)
  assert.equal(first.gate_signal.sample_size, 20)
  assert.equal(first.gate_signal.method, 'anytime_valid_bernstein')
  assert.equal(first.gate_signal.event_sha256,
    governanceEventDigest(source.payload, source.verifier, source.context))
  assert.deepEqual(first.event, {
    proposal_id: 'E4:test:0001',
    component_id: 'bridge-test-component',
    capability_class: 'SELF_MODIFYING',
    operator_id: 'bridge-test-operator',
    bridge_epoch_id: 'aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa',
    payload_hex: '68656c6c6f',
    verifier_hex: '00',
    context_hex: '007fff',
  })
  assert.equal(Object.isFrozen(first), true)
  assert.equal(Object.isFrozen(first.gate_signal), true)
  assert.equal(Object.isFrozen(first.event), true)
})

test('event digest is length framed and domain separated', () => {
  const input = candidate()
  const initial = governanceEventDigest(input.payload, input.verifier, input.context)
  assert.match(initial, /^[0-9a-f]{64}$/)
  assert.notEqual(initial,
    governanceEventDigest(Buffer.from('hellO'), input.verifier, input.context))
  assert.notEqual(initial,
    governanceEventDigest(input.payload, Uint8Array.of(0x00, 0x00), input.context))
  assert.notEqual(initial,
    governanceEventDigest(input.payload, input.verifier, Buffer.from([0x00, 0x7f])))
  const splitA = governanceEventDigest(
    Buffer.from('a'), Uint8Array.of(0x00), Buffer.from('bc'))
  const splitB = governanceEventDigest(
    Buffer.from('ab'), Uint8Array.of(0x00), Buffer.from('c'))
  assert.notEqual(splitA, splitB)
})

test('rejects invalid E4 identifiers, sequence and untrusted decisions', () => {
  for (const proposal_id of ['', 'bad/id', '../x', 'x'.repeat(129), 1, null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
      decision: { ...candidate().decision, proposal_id },
    })))
  }
  for (const component_id of ['', 'bad/id', null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
      decision: { ...candidate().decision, component_id },
    })))
  }
  for (const operatorId of ['', 'bad/id', null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({ operatorId })))
  }
  for (const capabilityClass of ['INFERENCE_ONLY', '', null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({ capabilityClass })))
  }
  for (const bridgeEpochId of ['', 'a'.repeat(63), 'g'.repeat(64), 'A'.repeat(64), null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({ bridgeEpochId })))
  }
  for (const sequence of [-1, 1.1, NaN, Infinity, Number.MAX_SAFE_INTEGER + 1, '1', null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({ sequence })))
  }
  for (const lcb_value of [-0.1, 0, NaN, Infinity, -Infinity, '0.2', null]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
      decision: { ...candidate().decision, lcb_value },
    })))
  }
})

test('rejects non-governance or malformed verifier inputs', () => {
  for (const verifier of [
    new Uint8Array(), Uint8Array.of(0x01), Uint8Array.of(0xff),
    Uint8Array.of(0x01, 0x00), '00', null,
  ]) {
    assert.throws(() => encodeAdmittedGovernanceMutation(candidate({ verifier })))
  }
  assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
    payload: new Uint8Array(65537),
  })))
  assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
    verifier: new Uint8Array(257).fill(0),
  })))
  assert.throws(() => encodeAdmittedGovernanceMutation(candidate({
    context: new Uint8Array(4097),
  })))
})

test('ASCII, UTF-8 and binary fields generate deterministic governance frames', () => {
  const multilingual = candidate({
    decision: { ...candidate().decision, proposal_id: 'E4:holon:42' },
    sequence: 123456,
    payload: Buffer.from('AEGIS Ω | holon: značenje', 'utf8'),
    verifier: Uint8Array.of(0x00, 0xff),
    context: Uint8Array.of(0x00, 0x01, 0xfe, 0xff),
  })
  const frames = encodeAdmittedGovernanceMutation(multilingual)
  assert.equal(frames.gate_signal.proposal_id, 'E4:holon:42')
  assert.equal(frames.event.payload_hex,
    Buffer.from('AEGIS Ω | holon: značenje', 'utf8').toString('hex'))
  assert.match(frames.gate_signal.event_sha256, /^[0-9a-f]{64}$/)
})
