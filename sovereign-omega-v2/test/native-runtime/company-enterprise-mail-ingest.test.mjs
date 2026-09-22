import test from 'node:test'
import assert from 'node:assert/strict'
import { loadRepositoryTypescript } from './load-repository-ts.mjs'

const loaded = await loadRepositoryTypescript([
  'sovereignty/company-enterprise-mail-ingest.ts',
])
test.after(() => loaded.cleanup())

const {
  proposeEnterpriseTransitionFromMailV1: propose,
  deriveEnterpriseOutboundMetricV1: metric,
} = loaded.modules['sovereignty/company-enterprise-mail-ingest.ts']

const mail = (overrides = {}) => ({
  provider: 'GMAIL',
  message_id: 'm1',
  thread_id: 't1',
  direction: 'OUTBOUND',
  mail_state: 'SENT',
  classification: 'OUTREACH',
  observed_generation: '1',
  ...overrides,
})

test('observed sent outreach proposes only DISCOVERED to CONTACTED', () => {
  const p = propose('DISCOVERED', mail())
  assert.equal(p.target_stage, 'CONTACTED')
  assert.equal(p.evidence_kind, 'OUTBOUND_SENT')
  assert.equal(p.evidence_authority, 'DIRECT_OBSERVATION')
  assert.equal(p.external_authority, 'NOT_GRANTED')
  assert.equal(p.authority_effect, 'NONE')
  assert.equal(propose('CONTACTED', mail()), null)
})

test('draft outreach never advances a commercial opportunity', () => {
  assert.equal(propose('DISCOVERED', mail({ mail_state: 'DRAFT' })), null)
})

test('qualifying inbound reply proposes CONTACTED to QUALIFIED_REPLY', () => {
  const p = propose('CONTACTED', mail({
    message_id: 'm2',
    direction: 'INBOUND',
    mail_state: 'RECEIVED',
    classification: 'QUALIFYING_REPLY',
    observed_generation: '2',
  }))
  assert.equal(p.target_stage, 'QUALIFIED_REPLY')
  assert.equal(p.evidence_kind, 'QUALIFYING_REPLY')
  assert.equal(p.evidence_authority, 'DERIVED_FROM_VERIFIED')
})

test('nonqualifying reply does not advance pipeline', () => {
  assert.equal(propose('CONTACTED', mail({
    message_id: 'm2',
    direction: 'INBOUND',
    mail_state: 'RECEIVED',
    classification: 'NONQUALIFYING_REPLY',
  })), null)
})

test('mail observation can never infer payment or audit-start stages', () => {
  for (const current of [
    'QUALIFIED_REPLY','SCOPING_CALL_HELD','WRITTEN_SCOPE_AGREED','PAYMENT_RECEIVED',
  ]) {
    const p = propose(current, mail({
      message_id: `m-${current}`,
      direction: 'INBOUND',
      mail_state: 'RECEIVED',
      classification: 'QUALIFYING_REPLY',
    }))
    assert.equal(p, null)
  }
})

test('outbound metric is based on unique observed sent threads, not landing-page visits', () => {
  const observations = Array.from({ length: 11 }, (_, i) => mail({
    message_id: `sent-${i}`,
    thread_id: `thread-${i}`,
    observed_generation: String(i + 1),
  }))
  const m = metric(observations)
  assert.equal(m.outbound_sent, 11)
  assert.equal(m.qualified_replies, 0)
  assert.equal(m.rate, 0)
  assert.equal(m.measurement_state, 'MEASURED')
  assert.equal(m.denominator_source, 'OBSERVED_SENT_LOG')
  assert.equal(m.landing_page_visits_used, false)
})

test('qualifying replies count only when tied to an observed outbound thread', () => {
  const m = metric([
    mail({ message_id:'s1', thread_id:'t1' }),
    mail({ message_id:'r1', thread_id:'t1', direction:'INBOUND', mail_state:'RECEIVED', classification:'QUALIFYING_REPLY', observed_generation:'2' }),
    mail({ message_id:'r2', thread_id:'unseen', direction:'INBOUND', mail_state:'RECEIVED', classification:'QUALIFYING_REPLY', observed_generation:'3' }),
  ])
  assert.equal(m.outbound_sent, 1)
  assert.equal(m.qualified_replies, 1)
  assert.equal(m.rate, 1)
})

test('duplicate provider-message observations fail closed instead of inflating metrics', () => {
  assert.throws(() => metric([mail(), mail()]), /DUPLICATE_MAIL_OBSERVATION/)
})
