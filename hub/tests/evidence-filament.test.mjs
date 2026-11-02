import test from 'node:test'
import assert from 'node:assert/strict'
import { selectEvidenceFilament } from '../src/lib/evidenceFilament.ts'

const records = Object.freeze([
  Object.freeze({ id: 'math', index: '01', title: 'Formal conjectures', kind: 'SOURCE', status: 'OPEN', question: 'Is the hypothesis closed?', boundaries: Object.freeze(['Compile is not a proof', 'Head-bound evidence required']) }),
  Object.freeze({ id: 'biology', index: '02', title: 'Genomics', kind: 'PRIVATE', status: 'RESTRICTED', question: 'Does it reproduce?', boundaries: Object.freeze(['Holdouts are unavailable']) }),
])

test('empty data is empty, never fabricated', () => {
  assert.equal(selectEvidenceFilament([], 'math'), null)
  assert.equal(selectEvidenceFilament([], null), null)
})
test('selection binds to an actual source and its precise question', () => {
  const flow = selectEvidenceFilament(records, 'biology')
  assert.equal(flow.source, records[1])
  assert.deepEqual(flow.links.map(link => link.label), ['Does it reproduce?', 'Holdouts are unavailable'])
  assert.deepEqual(flow.links.map(link => link.relationship), ['recorded_open_question', 'declared_boundary'])
})
test('stale selection falls back only to first filtered source', () => {
  assert.equal(selectEvidenceFilament(records.slice(1), 'math').source.id, 'biology')
})
test('all edges are local to selected source; no cross-source proof edge', () => {
  const flow = selectEvidenceFilament(records, 'math')
  assert.equal(flow.links.length, 1 + records[0].boundaries.length)
  assert(flow.links.every(link => link.from.includes('math') && link.to.includes('math')))
  assert(!flow.links.some(link => link.label.includes('Holdouts')))
})
test('derivation does not mutate frozen source data', () => {
  selectEvidenceFilament(records, 'math')
  assert.equal(records[0].boundaries[0], 'Compile is not a proof')
})
