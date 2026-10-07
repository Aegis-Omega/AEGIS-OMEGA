/** Actual Chromium + actual SDK HTTP server. No browser dependencies or network fixture. */
import assert from 'node:assert/strict'
import { spawn, spawnSync } from 'node:child_process'
import { mkdtempSync, readFileSync, existsSync, mkdirSync, writeFileSync, rmSync } from 'node:fs'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createServer } from 'node:http'
import { startHttpServer } from '../dist/http.js'
import { validateDemoTrace, sha256 } from '../web/client.mjs'

const wait = ms => new Promise(resolve => setTimeout(resolve, ms))
async function until(check, description, timeout = 20000) {
  const deadline = Date.now() + timeout
  while (Date.now() < deadline) { const value = await check(); if (value) return value; await wait(75) }
  throw new Error(`Timed out: ${description}`)
}
let bridgeRequests = 0
const bridge = createServer((_req, res) => { bridgeRequests++; res.writeHead(500).end('unexpected bridge access') })
await new Promise((resolve, reject) => { bridge.once('error', reject); bridge.listen(0, '127.0.0.1', resolve) })
process.env.AEGIS_BRIDGE_URL = `http://127.0.0.1:${bridge.address().port}`
process.env.AEGIS_EXECUTION_IDENTITY_JSON = '{"actor_identity":"must-not-be-inherited"}'
process.env.AEGIS_APPROVAL_GRANT_JSON = '{"approved":true}'
const executable = process.env.CHROME_BIN || ['google-chrome', 'chromium', 'chromium-browser'].map(name =>
  spawnSync('which', [name], { encoding: 'utf8' }).stdout?.trim()).find(Boolean)
assert.ok(executable, 'A real Chromium executable is required; browser QA cannot be skipped')
const profile = mkdtempSync(join(tmpdir(), 'aegis-mcp-chrome-'))
const app = await startHttpServer({ port: 0 })
const browser = spawn(executable, ['--headless=new', '--no-sandbox', '--disable-gpu', '--disable-dev-shm-usage',
  '--no-first-run', '--no-default-browser-check', '--disable-background-networking', '--disable-component-update',
  '--disable-sync', '--metrics-recording-only', '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0',
  `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' })
let socket
let sequence = 0
const pending = new Map()
const exceptions = []
async function command(method, params = {}) {
  const id = ++sequence
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(id); reject(new Error(`CDP timeout: ${method}`)) }, 15000)
    pending.set(id, { resolve: value => { clearTimeout(timer); resolve(value) }, reject: error => { clearTimeout(timer); reject(error) } })
    socket.send(JSON.stringify({ id, method, params }))
  })
}
async function evaluate(expression) {
  const response = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (response.exceptionDetails) throw new Error('Browser evaluation threw an exception')
  return response.result.value
}
try {
  const active = join(profile, 'DevToolsActivePort')
  await until(() => existsSync(active), 'Chromium startup')
  const debugPort = readFileSync(active, 'utf8').split('\n')[0]
  const pages = await (await fetch(`http://127.0.0.1:${debugPort}/json/list`)).json()
  const page = pages.find(item => item.type === 'page')
  assert.ok(page?.webSocketDebuggerUrl)
  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  socket.addEventListener('message', event => {
    const message = JSON.parse(event.data)
    if (message.method === 'Runtime.exceptionThrown') exceptions.push(message.params.exceptionDetails.text)
    const task = pending.get(message.id)
    if (task) { pending.delete(message.id); message.error ? task.reject(new Error(JSON.stringify(message.error))) : task.resolve(message.result) }
  })
  await command('Page.enable'); await command('Runtime.enable')
  mkdirSync('evidence', { recursive: true })
  const results = []
  for (const viewport of [{ name: 'desktop', width: 1360, height: 1040 }, { name: 'mobile', width: 390, height: 844 }]) {
    await command('Emulation.setDeviceMetricsOverride', { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.name === 'mobile' })
    const pageUrl = `${app.origin}/?viewport=${viewport.name}`
    await command('Page.navigate', { url: pageUrl })
    await until(() => evaluate(`location.href === ${JSON.stringify(pageUrl)} && document.readyState === "complete" && !!document.getElementById("run")`), 'simulator page load')
    assert.equal(await evaluate('document.getElementById("result").dataset.verdict'), 'NOT_RUN')
    assert.equal(await evaluate('document.getElementById("download").disabled'), true)
    await evaluate('document.getElementById("run").click()')
    await until(() => evaluate('["PASS", "FAIL"].includes(document.getElementById("result").dataset.verdict)'), 'browser MCP sequence')
    assert.equal(await evaluate('document.getElementById("result").dataset.verdict'), 'PASS', await evaluate('document.getElementById("result").innerText'))
    const evidence = await evaluate('window.aegisEvidence')
    assert.equal((await validateDemoTrace(evidence.trace)).verdict, 'PASS')
    assert.equal(evidence.trace_sha256, await sha256(JSON.stringify(evidence.trace)))
    assert.equal(bridgeRequests, 0, 'The actual browser must not contact the bridge')
    assert.equal(await evaluate('document.documentElement.scrollWidth > window.innerWidth'), false, 'Horizontal viewport overflow')
    assert.equal(await evaluate('document.getElementById("download").disabled'), false)
    const metrics = await command('Page.getLayoutMetrics')
    const screenshot = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: viewport.width, height: Math.ceil(metrics.cssContentSize.height), scale: 1 } })
    writeFileSync(`evidence/browser-${viewport.name}.png`, Buffer.from(screenshot.data, 'base64'))
    writeFileSync(`evidence/browser-${viewport.name}-trace.json`, JSON.stringify({ ...evidence, browser: executable, viewport,
      bridge_requests_observed: bridgeRequests }, null, 2) + '\n')
    results.push({ viewport, verdict: 'PASS', bridge_requests_observed: bridgeRequests })
  }
  assert.deepEqual(exceptions, [], 'Uncaught browser exceptions')
  writeFileSync('evidence/browser-results.json', JSON.stringify({ observation: 'ACTUAL_CHROMIUM_AND_SDK_HTTP', results, exceptions }, null, 2) + '\n')
  console.log('BROWSER_E2E_PASS actual desktop/mobile MCP exchanges; zero bridge requests; no horizontal overflow')
} finally {
  socket?.close(); browser.kill('SIGTERM')
  await app.close(); await new Promise(resolve => bridge.close(resolve))
  await wait(150); rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}
