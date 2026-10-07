import { BrowserMcpClient, sha256, validateDemoTrace } from './client.mjs'

const $ = id => document.getElementById(id)
const steps = [...document.querySelectorAll('#steps li')]
let client
let evidence
let running = false
function showResult(verdict, title, detail) {
  const box = $('result')
  box.dataset.verdict = verdict
  box.replaceChildren()
  for (const [tag, text, className] of [['p', verdict === 'PASS' ? 'LOCAL PROTOCOL VERIFIED' : verdict, 'eyeline'],
    ['strong', title, ''], ['p', detail, '']]) {
    const node = document.createElement(tag); node.textContent = text; node.className = className; box.append(node)
  }
}
function renderTrace() {
  const trace = client?.trace ?? []
  $('trace').textContent = JSON.stringify(trace, null, 2)
  trace.forEach((entry, index) => {
    const row = steps[index]
    if (!row) return
    const good = !entry.client_error && (entry.status === 200 || entry.status === 202)
    const denied = index === 4 && good && entry.response?.result?.isError === true
    row.className = good ? (denied ? 'denied' : 'complete') : ''
    row.querySelector('.step-state').textContent = entry.client_error ? 'Failed' : denied ? 'Denied' : good ? `HTTP ${entry.status}` : 'Running'
  })
}
$('run').addEventListener('click', async () => {
  if (running) return
  running = true; $('run').disabled = true; $('download').disabled = true; evidence = undefined
  window.aegisEvidence = null
  $('protocol-version').textContent = 'Not negotiated'; $('policy-hash').textContent = 'Not read'
  $('effect').textContent = 'Not observed'; $('trace').textContent = 'No exchanges yet.'
  const previousClient = client; client = undefined
  steps.forEach(row => { row.className = ''; row.querySelector('.step-state').textContent = 'Pending' })
  $('status').textContent = 'Opening a local, authority-unbound MCP session…'
  showResult('RUNNING', 'Inspecting the boundary', 'Results come from this run, not a stored example.')
  try {
    await previousClient?.close()
    const response = await fetch('/bootstrap', { cache: 'no-store', redirect: 'error', signal: AbortSignal.timeout(10000) })
    if (!response.ok) throw new Error(`Local bootstrap HTTP ${response.status}`)
    const bootstrap = await response.json()
    if (bootstrap.authorityBinding !== 'UNBOUND') throw new Error('Unexpected authority binding')
    client = new BrowserMcpClient({ endpoint: new URL('/mcp', location.origin).href, localToken: bootstrap.localToken })
    const initialized = await client.initialize(); renderTrace()
    $('protocol-version').textContent = initialized.protocolVersion
    await client.listTools(); renderTrace()
    const read = await client.callTool('aegis_authority_policy', {}); renderTrace()
    if (read.isError) throw new Error('Repository policy could not be read')
    const policy = JSON.parse(read.content.find(item => item.type === 'text').text)
    $('policy-hash').textContent = policy.source.sha256
    await client.callTool('aegis_governed_claude_call', { prompt: 'Explain the locally observed AEGIS policy. This request has no execution approval.' }); renderTrace()
    const verified = await validateDemoTrace(client.trace)
    const trace = structuredClone(client.trace)
    evidence = { schema_version: '1.0.0', observed_at: new Date().toISOString(), observation: 'ACTUAL_BROWSER_STREAMABLE_HTTP',
      verification: verified, trace_sha256: await sha256(JSON.stringify(trace)), trace,
      limits: ['Local observation, not a signed attestation.', 'No Alexa runtime or gated Amazon SDK was used.',
        'No model request or AWS service is executed by this sequence.', 'HTTP identity is unbound; approved remote execution is outside this lane.'] }
    window.aegisEvidence = structuredClone(evidence)
    $('effect').textContent = verified.external_effect
    showResult('PASS', 'Read verified. Action denied.', 'The policy bytes match their SHA-256. The consequential request stopped at IDENTITY_UNAVAILABLE, before a bridge call.')
    $('status').textContent = 'Five exchanges verified. Execution authority was not expanded.'
    $('download').disabled = false
  } catch (error) {
    evidence = undefined; window.aegisEvidence = null; renderTrace()
    showResult('FAIL', 'Not verified', error instanceof Error ? error.message : String(error))
    $('status').textContent = 'Stopped. An incomplete or failed sequence is not evidence of success.'
  } finally {
    try { await client?.close() } catch { $('status').textContent += ' Session cleanup failed; stop the local server to clear it.' }
    running = false; $('run').disabled = false
  }
})
$('download').addEventListener('click', () => {
  if (!evidence) return
  const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2) + '\n'], { type: 'application/json' }))
  const link = document.createElement('a'); link.href = url; link.download = 'AEGIS_local_MCP_evidence.json'; link.click()
  setTimeout(() => URL.revokeObjectURL(url), 1000)
})
