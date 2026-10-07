import { verifyArchive } from './verify.mjs'
const $ = id => document.getElementById(id)
const rows = [...document.querySelectorAll('[data-step]')]
let verified, receiptBytes, traceBytes, busy = false
function show(verdict, title, detail) {
  const result = $('result'); result.dataset.verdict = verdict; result.replaceChildren()
  const heading = document.createElement('strong'), text = document.createElement('p')
  heading.textContent = title; text.textContent = detail; result.append(heading, text)
}
function reset() {
  verified = undefined; receiptBytes = undefined; traceBytes = undefined
  $('observed').textContent = 'Not verified'; $('source').textContent = 'Not verified'; $('policy').textContent = 'Not verified'
  $('tamper').disabled = true; $('tamper-status').textContent = 'Negative control not run.'
  $('exchange').textContent = 'No recorded response has been selected.'; $('exchange-note').textContent = 'Verification required'
  rows.forEach(row => { row.disabled = true; row.removeAttribute('aria-pressed'); row.querySelector('.state').textContent = 'Not verified' })
}
async function readArtifact(name) {
  // Fixed same-origin paths only. Hosting cookies stay on this origin; no redirects, RPC requests or localhost probes.
  const response = await fetch(new URL(name, import.meta.url), { method: 'GET', credentials: 'same-origin', redirect: 'error',
    cache: 'no-store', headers: { Accept: 'application/json' }, signal: AbortSignal.timeout(10000) })
  if (!response.ok || !response.headers.get('content-type')?.startsWith('application/json')) throw new Error('Evidence download failed or returned non-JSON content')
  const reader = response.body?.getReader(); if (!reader) throw new Error('Evidence response body missing')
  const chunks = []; let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read(); if (done) break
      size += value.byteLength; if (size > 262144) throw new Error('Evidence exceeds the download limit')
      chunks.push(value)
    }
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
  const bytes = new Uint8Array(size); let offset = 0
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
  return bytes
}
function select(index) {
  if (!verified) return
  const event = verified.exchanges[index]
  rows.forEach((row, i) => row.setAttribute('aria-pressed', String(i === index)))
  $('exchange-title').textContent = `${String(index + 1).padStart(2, '0')} · ${event.method}`
  $('exchange-note').textContent = `Recorded HTTP ${event.status} · ${index === 4 ? 'tool denied' : 'protocol response'}`
  $('exchange').textContent = JSON.stringify({ request: event.request, status: event.status, response: event.response }, null, 2)
}
rows.forEach((row, i) => row.addEventListener('click', () => select(i)))
$('verify').addEventListener('click', async () => {
  if (busy) return
  busy = true; $('verify').disabled = true; reset()
  show('VERIFYING', 'Checking the recorded bytes…', 'No live MCP call is being made.')
  $('status').textContent = 'Reading the two pinned archive files…'
  try {
    [receiptBytes, traceBytes] = await Promise.all([readArtifact('receipt.json'), readArtifact('trace.json')])
    verified = await verifyArchive(receiptBytes, traceBytes)
    $('observed').textContent = verified.observed_at
    $('source').textContent = verified.source_commit; $('policy').textContent = verified.policy_sha256
    rows.forEach((row, i) => { row.disabled = false; row.querySelector('.state').textContent = i === 4 ? 'Denied' : `HTTP ${verified.exchanges[i].status}` })
    show('VERIFIED', 'Read verified. Action denied.', 'Recorded evidence verified: exact artifact bytes, policy digest, source binding and missing-identity denial. This is not a new execution.')
    $('status').textContent = 'Recorded evidence verified in this browser. No execution authority changed.'
    $('tamper').disabled = false; select(4)
  } catch (error) {
    reset(); show('FAILED', 'Evidence not verified.', error instanceof Error ? error.message : String(error))
    $('status').textContent = 'Stopped. Failed or incomplete evidence is not a verified result.'
  } finally { busy = false; $('verify').disabled = false }
})
$('tamper').addEventListener('click', async () => {
  if (!verified || busy) return
  busy = true; $('tamper').disabled = true; $('verify').disabled = true
  try {
    const altered = JSON.parse(new TextDecoder().decode(traceBytes))
    const denial = JSON.parse(altered.trace[4].response.result.content[0].text)
    denial.external_effect = 'EXECUTED'
    altered.trace[4].response.result.content[0].text = JSON.stringify(denial)
    let rejected = false
    try { await verifyArchive(receiptBytes, new TextEncoder().encode(JSON.stringify(altered))) } catch { rejected = true }
    if (!rejected) throw new Error('Tamper negative control unexpectedly passed')
    $('tamper-status').textContent = 'REJECTED — altered denial bytes failed verification. Original archive unchanged.'
  } catch (error) {
    reset(); show('FAILED', 'Negative control failed.', error instanceof Error ? error.message : String(error))
    $('status').textContent = 'Stopped. Do not rely on this verification.'
  } finally { busy = false; $('verify').disabled = false; $('tamper').disabled = !verified }
})
