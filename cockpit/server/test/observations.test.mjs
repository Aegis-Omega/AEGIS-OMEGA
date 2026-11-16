import assert from 'node:assert/strict'
import { test } from 'node:test'
import { BrowserObservationCounter, parseBrowserObservation } from '../dist/observations.js'

test('accept only canonical, minimal RESPONSE_GENERATED observations', () => {
  assert.deepEqual(parseBrowserObservation({ type: 'RESPONSE_GENERATED', content_length: 0 }), {
    type: 'RESPONSE_GENERATED',
    content_length: 0,
  })
  assert.deepEqual(parseBrowserObservation({ type: 'RESPONSE_GENERATED', content_length: 15 }), {
    type: 'RESPONSE_GENERATED',
    content_length: 15,
  })
  for (const value of [
    null, undefined, [], '', 1, false,
    { type: 'RESPONSE_GENERATED' },
    { type: 'GATE_APPROVED', content_length: 1 },
    { type: 'RESPONSE_GENERATED', content_length: -1 },
    { type: 'RESPONSE_GENERATED', content_length: 1.5 },
    { type: 'RESPONSE_GENERATED', content_length: NaN },
    { type: 'RESPONSE_GENERATED', content_length: Infinity },
    { type: 'RESPONSE_GENERATED', content_length: 1000001 },
    { type: 'RESPONSE_GENERATED', content_length: '1' },
    { type: 'RESPONSE_GENERATED', content_length: 1, proposal_id: 'privileged' },
    { type: 'RESPONSE_GENERATED', content_length: 1, accepted: true },
  ]) {
    assert.equal(parseBrowserObservation(value), null, JSON.stringify(value))
  }
})

test('browser observations are labelled unverified and process-local', () => {
  const c = new BrowserObservationCounter()
  assert.deepEqual(c.snapshot(), {
    trust_class: 'UNVERIFIED_BROWSER_OBSERVATION',
    durability: 'PROCESS_LOCAL',
    response_generated_count: 0,
    reported_characters: 0,
  })
  assert.equal(c.record({ type: 'GATE_EVALUATED', content_length: 123 }), false)
  assert.equal(c.record({ type: 'RESPONSE_GENERATED', content_length: 32 }), true)
  assert.equal(c.record({ type: 'RESPONSE_GENERATED', content_length: 41 }), true)
  assert.deepEqual(c.snapshot(), {
    trust_class: 'UNVERIFIED_BROWSER_OBSERVATION',
    durability: 'PROCESS_LOCAL',
    response_generated_count: 2,
    reported_characters: 73,
  })
  assert.equal(c.snapshot().mutation_authority, undefined)
})

test('browser-origin request cannot spoof governance fields', () => {
  const c = new BrowserObservationCounter()
  const malicious = {
    type: 'RESPONSE_GENERATED',
    content_length: 20,
    accepted: true,
    lcb: 1,
    event_sha256: 'f'.repeat(64),
  }
  assert.equal(c.record(malicious), false)
  assert.equal(c.snapshot().response_generated_count, 0)
})
