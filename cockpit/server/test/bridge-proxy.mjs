import assert from 'node:assert/strict'
import { createServer, get as httpGet } from 'node:http'
import { spawn } from 'node:child_process'
import { once } from 'node:events'
import { setTimeout as delay } from 'node:timers/promises'

const bridge = createServer(async (req, res) => {
  if (req.url === '/telemetry') {
    res.setHeader('Content-Type', 'application/json')
    res.end(JSON.stringify({ source: 'real-upstream-fixture', epoch: 7 }))
    return
  }
  if (req.url === '/platform/stream') {
    res.setHeader('Content-Type', 'text/event-stream')
    res.write('data: first\n\n')
    setTimeout(() => res.end('data: done\n\n'), 20)
    return
  }
  // Deliberately terminate the source mid-response, including SSE.
  // The downstream must close, not hang waiting for a final body/chunk.
  if (req.url === '/platform/abort-json') {
    res.writeHead(200, { 'Content-Type': 'application/json', 'Content-Length': '128' })
    res.write('{"partial":')
    setTimeout(() => res.destroy(), 40)
    return
  }
  if (req.url === '/platform/abort-sse') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream' })
    res.write('data: first\n\n')
    setTimeout(() => res.destroy(), 40)
    return
  }
  if (req.url === '/platform/unavailable') {
    res.writeHead(503).end('upstream unavailable')
    return
  }
  let body = ''
  for await (const chunk of req) body += chunk
  res.setHeader('Content-Type', 'application/json')
  res.end(JSON.stringify({ path: req.url, method: req.method, body,
    authenticated: req.headers['x-api-key'] === 'fixture-key' }))
})
bridge.listen(0, '127.0.0.1')
await once(bridge, 'listening')
const bridgeUrl = `http://127.0.0.1:${bridge.address().port}`
const portProbe = createServer()
portProbe.listen(0, '127.0.0.1')
await once(portProbe, 'listening')
const port = portProbe.address().port
await new Promise(resolve => portProbe.close(resolve))
const server = spawn(process.execPath, ['dist/index.js'], {
  env: { ...process.env, PORT: String(port), AEGIS_BRIDGE_URL: bridgeUrl,
    GOOGLE_CLOUD_PROJECT: '', ANTHROPIC_API_KEY: '' }, stdio: 'pipe',
})
let startupError = ''
server.stderr.on('data', chunk => { startupError += chunk.toString() })
const base = `http://127.0.0.1:${port}`

async function expectAbortedBody(route) {
  await new Promise((resolve, reject) => {
    let settled = false
    let sawData = false
    const timer = setTimeout(
      () => finish(new Error(`Bridge downstream hung after upstream abort: ${route}`)),
      2500,
    )
    const request = httpGet(`${base}${route}`, response => {
      if (response.statusCode !== 200) {
        finish(new Error(`Unexpected response status ${response.statusCode}: ${route}`))
        return
      }
      response.on('data', () => { sawData = true })
      response.on('end', () => finish(new Error(`Aborted upstream appeared complete: ${route}`)))
      response.on('close', () => {
        finish(sawData && !response.complete
          ? null
          : new Error(`Partial upstream response did not close correctly: ${route}`))
      })
      // An aborted IncomingMessage emits error before close on modern Node;
      // close is the authoritative terminal event and carries complete=false.
      response.on('error', () => {})
    })
    request.on('error', error => finish(error))
    function finish(error) {
      if (settled) return
      settled = true
      clearTimeout(timer)
      request.destroy()
      if (error) reject(error)
      else resolve()
    }
  })
}

try {
  let ready = false
  for (let attempt = 0; attempt < 100; attempt++) {
    if (server.exitCode !== null) throw new Error('Cockpit startup failed: ' + startupError)
    try { ready = (await fetch(`${base}/health`)).ok } catch { /* starting */ }
    if (ready) break
    await delay(50)
  }
  assert.ok(ready, 'Cockpit should start')
  assert.deepEqual(await (await fetch(`${base}/telemetry`)).json(),
    { source: 'real-upstream-fixture', epoch: 7 })
  const posted = await fetch(`${base}/platform/collaborate?mode=technical`, {
    method: 'POST', headers: { 'Content-Type': 'application/json', 'X-API-Key': 'fixture-key' },
    body: JSON.stringify({ objective: 'local proxy test' }),
  })
  assert.deepEqual(await posted.json(), { path: '/platform/collaborate?mode=technical',
    method: 'POST', body: '{"objective":"local proxy test"}', authenticated: true })
  const stream = await fetch(`${base}/platform/stream`)
  assert.match(stream.headers.get('content-type'), /text\/event-stream/)
  assert.equal(await stream.text(), 'data: first\n\ndata: done\n\n')
  assert.equal((await fetch(`${base}/platform/unavailable`)).status, 503)
  await expectAbortedBody('/platform/abort-json')
  await expectAbortedBody('/platform/abort-sse')
  await new Promise(resolve => bridge.close(resolve))
  assert.equal((await fetch(`${base}/telemetry`)).status, 502)
  console.log('PASS: telemetry, request path/body/auth, SSE, mid-body aborts, upstream status, unavailable bridge')
} finally {
  server.kill()
  bridge.closeAllConnections()
  bridge.close()
}
