/** Static archive verification only. This module never opens an MCP session or grants authority. */
export const SOURCE = '897fa55556a639a04a67d25481b7a432af007d04'
export const PINS = Object.freeze({
  receipt: 'b9fbbe2eb4edbef7407b3caa1e7993527e27f62404d57b2beae5b1b542673983',
  trace: '11426c19a437a78d2c7afed6f7b799fb30a640bc8f5c30320c8e6cadbcd8489b',
  friction: '20bbf6d07ca7b91970458fe126d5a6f9f2ed7da5dffabae8ad855f67dae7e854',
  policy: '705591e5f8874db09b5d666363b92ff638e2d65ff12bc8494a4c9a294675e3a3',
})
const STAGES = ['build', 'browser-client', 'streamable-http', 'legacy-resources', 'legacy-automaton3', 'browser-e2e']
const METHODS = ['initialize', 'notifications/initialized', 'tools/list', 'tools/call', 'tools/call']
const requireThat = (condition, message) => { if (!condition) throw new Error(message) }
export async function sha256(bytes) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', typeof bytes === 'string' ? new TextEncoder().encode(bytes) : bytes)
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}
function textResult(event) {
  const content = event.response?.result?.content
  requireThat(Array.isArray(content) && content.length === 1 && content[0].type === 'text', 'Missing recorded tool content')
  return JSON.parse(content[0].text)
}
export async function inspectArchive(receipt, recorded) {
  requireThat(receipt.source_commit === SOURCE && receipt.verdict === 'PASS', 'Source or recorded verdict mismatch')
  requireThat(receipt.observation === 'EXECUTED_REPLAY_NOT_SIGNED_ATTESTATION' &&
    recorded.observation === 'ACTUAL_BROWSER_STREAMABLE_HTTP', 'Unexpected evidence kind')
  requireThat(receipt.admission === 'NOT_ADMITTED' && receipt.submission === 'NOT_SUBMITTED', 'Archive must not grant admission or imply submission')
  requireThat(Array.isArray(receipt.stages) && receipt.stages.length === STAGES.length &&
    receipt.stages.every((s, i) => s.name === STAGES[i] && s.status === 'PASS' && s.exit_code === 0), 'Incomplete or failed recorded stage')
  requireThat(recorded.bridge_requests_observed === 0, 'Recorded bridge activity was not zero')
  const events = recorded.trace
  requireThat(Array.isArray(events) && events.length === 5, 'Five recorded exchanges required')
  const version = events[0].response?.result?.protocolVersion
  requireThat(version === '2025-11-25', 'Unexpected recorded protocol')
  let previousTime = 0
  for (let i = 0; i < events.length; i++) {
    const e = events[i], r = e.request, time = Date.parse(e.observed_at)
    requireThat(e.sequence === i + 1 && e.method === METHODS[i] && r?.method === METHODS[i] &&
      r.jsonrpc === '2.0' && !e.client_error && Number.isFinite(time) && time >= previousTime, 'Invalid recorded sequence')
    previousTime = time
    if (i === 1) requireThat(e.status === 202 && e.response === null && !Object.hasOwn(r, 'id'), 'Invalid notification acknowledgment')
    else requireThat(e.status === 200 && e.response?.jsonrpc === '2.0' && e.response.id === r.id &&
      r.id === [1, null, 2, 3, 4][i] && Object.hasOwn(e.response, 'result') && !Object.hasOwn(e.response, 'error'), 'Uncorrelated or failed recorded RPC')
    if (i > 0) requireThat(e.request_headers?.session_present === true && e.request_headers.protocol_version === version, 'Missing negotiated session or protocol')
  }
  const tools = events[2].response.result.tools
  requireThat(Array.isArray(tools) && ['aegis_authority_policy', 'aegis_governed_claude_call'].every(name => tools.some(t => t.name === name)), 'Recorded tools missing')
  requireThat(events[3].request.params.name === 'aegis_authority_policy' && events[3].response.result.isError !== true, 'Read-only call did not succeed')
  const policy = textResult(events[3])
  requireThat(policy.source?.path === 'harness/policies/consequence-policy.v1.json' && policy.source.sha256 === PINS.policy &&
    typeof policy.policy_json === 'string' && await sha256(policy.policy_json) === PINS.policy &&
    JSON.stringify(JSON.parse(policy.policy_json)) === JSON.stringify(policy.policy) &&
    policy.policy.classes.D3.approval === 'EXPLICIT' && policy.authority_effect === 'NONE' && policy.external_effect === 'NONE', 'Recorded policy bytes or authority semantics mismatch')
  const denial = textResult(events[4])
  requireThat(events[4].request.params.name === 'aegis_governed_claude_call' && events[4].response.result.isError === true &&
    denial.authority?.outcome === 'DENIED' && JSON.stringify(denial.authority.denial_codes) === '["IDENTITY_UNAVAILABLE"]' &&
    denial.external_effect === 'NOT_EXECUTED', 'Recorded action was not denied before execution')
  requireThat(await sha256(JSON.stringify(events)) === recorded.trace_sha256, 'Inner trace digest mismatch')
  requireThat(receipt.artifacts?.some(a => a.path === 'browser-desktop-trace.json' && a.sha256 === PINS.trace) &&
    receipt.source_manifest?.some(s => s.path === policy.source.path && s.sha256 === PINS.policy), 'Receipt does not bind this trace and policy')
  return { status: 'RECORDED_EVIDENCE_VERIFIED', source_commit: SOURCE, observed_at: recorded.observed_at,
    protocol_version: version, policy_sha256: PINS.policy, authority_outcome: 'DENIED', external_effect: 'NOT_EXECUTED',
    bridge_requests_observed: 0, live_execution: false, admission: 'NOT_ADMITTED', submission: 'NOT_SUBMITTED',
    exchanges: structuredClone(events) }
}
export async function verifyArchive(receiptBytes, traceBytes) {
  for (const [kind, bytes] of [['receipt', receiptBytes], ['trace', traceBytes]]) {
    requireThat(bytes instanceof Uint8Array && bytes.byteLength > 0 && bytes.byteLength <= 262144, 'Invalid or oversized archive bytes')
    requireThat(await sha256(bytes) === PINS[kind], `${kind}: bytes differ from the pinned recorded artifact`)
  }
  const decode = bytes => JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
  return inspectArchive(decode(receiptBytes), decode(traceBytes))
}
