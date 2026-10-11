// Static, dependency-free SQL admission guards. NOT PostgreSQL execution.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const sql = readFileSync(new URL('../../../migrations/20261011070000_agent_result_outbox_retention_v1.sql', import.meta.url), 'utf8')
const base = readFileSync(new URL('../../../migrations/20261011052000_agent_result_outbox_v1.sql', import.meta.url), 'utf8')
const claim = readFileSync(new URL('../../../migrations/20261010190000_agent_dispatch_claims_v1.sql', import.meta.url), 'utf8')

test('purge does not remove once-only paid dispatch records', () => {
  assert.match(sql, /delete from public\.aegis_agent_result_outbox_v1/i)
  assert.doesNotMatch(sql, /delete\s+from\s+public\.aegis_agent_dispatch_claims_v1/i)
  assert.match(claim, /event_digest\s+text\s+primary\s+key/i)
})
test('only expired ciphertext is eligible for physical purge', () => {
  assert.match(sql, /o\.expires_at\s*<=\s*now\(\)/i)
  assert.match(base, /expires_at\s+timestamptz\s+not null default \(now\(\) \+ interval '24 hours'\)/i)
})
test('purge is bounded and concurrent invocations skip locked records', () => {
  assert.match(sql, /p_batch_limit\s+between\s+1\s+and\s+500/i)
  assert.match(sql, /limit p_batch_limit/i)
  assert.match(sql, /for update skip locked/i)
})
test('privileged deletion is restricted to the bounded SECURITY DEFINER function', () => {
  assert.match(sql, /language sql security definer set search_path = ''/i)
  assert.doesNotMatch(sql, /grant delete on public\.aegis_agent_result_outbox_v1 to service_role/i)
})
test('anon and authenticated do not receive EXECUTE permission', () => {
  assert.match(sql, /revoke all on function public\.aegis_outbox_purge_expired_v1\(integer\)\s+from public, anon, authenticated/i)
  assert.match(sql, /grant execute on function public\.aegis_outbox_purge_expired_v1\(integer\)\s+to service_role/i)
  assert.match(base, /revoke all on public\.aegis_agent_result_outbox_v1 from public, anon, authenticated/i)
})
test('ambiguous SENDING deletions are counted for the operator', () => {
  assert.match(sql, /count\(\*\) filter \(where delivery_state = 'SENDING'\)::bigint/i)
  assert.match(sql, /returns table\(deleted_count bigint, unresolved_count bigint\)/i)
})
test('retention does not silently enable scheduled production mutations', () => {
  assert.doesNotMatch(sql, /\bcron\.schedule\s*\(/i)
  assert.doesNotMatch(sql, /\bpg_cron\b/i)
})
