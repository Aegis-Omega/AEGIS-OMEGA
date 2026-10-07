/** Real Chromium UI + static-file transport test. No MCP or model server is launched. */
import assert from 'node:assert/strict'
import { createServer } from 'node:http'
import { spawn, spawnSync } from 'node:child_process'
import { readFileSync, existsSync, writeFileSync, mkdirSync, mkdtempSync, rmSync } from 'node:fs'
import { join } from 'node:path'
import { tmpdir } from 'node:os'
import { fileURLToPath } from 'node:url'
const root = fileURLToPath(new URL('../public/labs/mcp/', import.meta.url))
const output = fileURLToPath(new URL('../evidence/mcp-public/', import.meta.url)); mkdirSync(output, { recursive: true })
const assets = { 'index.html': 'text/html; charset=utf-8', 'style.css': 'text/css', 'app.mjs': 'text/javascript',
  'verify.mjs': 'text/javascript', 'receipt.json': 'application/json', 'trace.json': 'application/json', 'friction-log.json': 'application/json' }
const observed = [], exceptions = [], tests = []
let broken = false
const server = createServer((req, res) => {
  const url = new URL(req.url, 'http://localhost')
  observed.push({ method: req.method, path: url.pathname })
  if (req.method !== 'GET') { res.writeHead(405).end(); return }
  const name = url.pathname.replace(/^\/labs\/mcp\/?/, '') || 'index.html'
  if (!url.pathname.startsWith('/labs/mcp') || !assets[name]) { res.writeHead(404).end(); return }
  res.setHeader('Cache-Control', 'no-store'); res.setHeader('Content-Type', assets[name])
  res.setHeader('Content-Security-Policy', "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
  res.end(broken && name === 'trace.json' ? '{"forged":"PASS"}' : readFileSync(join(root, name)))
})
await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
const origin = `http://127.0.0.1:${server.address().port}`
const profile = mkdtempSync(join(tmpdir(), 'aegis-static-evidence-'))
const chrome = process.env.CHROME_BIN || ['google-chrome', 'chromium', 'chromium-browser'].map(name => spawnSync('which', [name], {encoding:'utf8'}).stdout?.trim()).find(Boolean)
assert.ok(chrome, 'A real Chromium browser is required; missing browser is not a skip')
const browser = spawn(chrome, ['--headless=new', '--no-sandbox', '--disable-gpu',
  '--disable-dev-shm-usage', '--disable-background-networking', '--disable-component-update', '--no-first-run', '--no-default-browser-check',
  '--remote-debugging-address=127.0.0.1', '--remote-debugging-port=0', `--user-data-dir=${profile}`, 'about:blank'], { stdio: 'ignore' })
const pause = ms => new Promise(r => setTimeout(r, ms))
async function until(fn, reason) { for (let i = 0; i < 160; i++) { if (await fn()) return; await pause(75) } throw new Error(`Timeout: ${reason}`) }
let socket, id = 0
const pending = new Map(), network = []
function command(method, params = {}) {
  const current = ++id
  return new Promise((resolve, reject) => {
    const timer = setTimeout(() => { pending.delete(current); reject(new Error(`CDP timeout ${method}`)) }, 12000)
    pending.set(current, { resolve: r => { clearTimeout(timer); resolve(r) }, reject: e => { clearTimeout(timer); reject(e) } })
    socket.send(JSON.stringify({ id: current, method, params }))
  })
}
async function evaluate(expression) {
  const r = await command('Runtime.evaluate', { expression, returnByValue: true, awaitPromise: true })
  if (r.exceptionDetails) throw new Error(JSON.stringify(r.exceptionDetails))
  return r.result.value
}
async function click(selector) {
  const pos = await evaluate(`(() => {const e=document.querySelector(${JSON.stringify(selector)}); e.scrollIntoView({block:'center'}); const r=e.getBoundingClientRect(); return {x:r.x+r.width/2,y:r.y+r.height/2}})()`)
  await command('Input.dispatchMouseEvent', { type: 'mousePressed', button: 'left', clickCount: 1, ...pos })
  await command('Input.dispatchMouseEvent', { type: 'mouseReleased', button: 'left', clickCount: 1, ...pos })
}
try {
  await until(() => existsSync(join(profile, 'DevToolsActivePort')), 'Chromium startup')
  const port = readFileSync(join(profile, 'DevToolsActivePort'), 'utf8').split('\n')[0]
  const page = (await (await fetch(`http://127.0.0.1:${port}/json/list`)).json()).find(p => p.type === 'page')
  socket = new WebSocket(page.webSocketDebuggerUrl)
  await new Promise((resolve, reject) => { socket.addEventListener('open', resolve, { once: true }); socket.addEventListener('error', reject, { once: true }) })
  socket.addEventListener('message', event => {
    const msg = JSON.parse(event.data)
    if (msg.method === 'Runtime.exceptionThrown') exceptions.push(msg.params.exceptionDetails)
    if (msg.method === 'Network.requestWillBeSent') network.push({ method: msg.params.request.method, url: msg.params.request.url })
    const task = pending.get(msg.id)
    if (task) { pending.delete(msg.id); msg.error ? task.reject(new Error(JSON.stringify(msg.error))) : task.resolve(msg.result) }
  })
  await command('Page.enable'); await command('Runtime.enable'); await command('Network.enable')
  for (const viewport of [{ name: 'desktop', width: 1360, height: 1040 }, { name: 'mobile', width: 390, height: 844 }]) {
    broken = false
    await command('Emulation.setDeviceMetricsOverride', { width: viewport.width, height: viewport.height, deviceScaleFactor: 1, mobile: viewport.name === 'mobile' })
    const url = `${origin}/labs/mcp?viewport=${viewport.name}`
    const navigation = await command('Page.navigate', { url }); assert.equal(navigation.errorText, undefined, 'Browser navigation blocked: ' + navigation.errorText)
    await until(() => evaluate(`location.href === ${JSON.stringify(url)} && document.readyState==='complete'`), 'page load')
    assert.equal(await evaluate("document.getElementById('result').dataset.verdict"), 'NOT_VERIFIED')
    assert.equal(await evaluate("document.getElementById('tamper').disabled"), true)
    await click('#verify')
    await until(() => evaluate("['VERIFIED','FAILED'].includes(document.getElementById('result').dataset.verdict)"), 'archive verification')
    assert.equal(await evaluate("document.getElementById('result').dataset.verdict"), 'VERIFIED')
    assert.match(await evaluate("document.getElementById('exchange').textContent"), /IDENTITY_UNAVAILABLE/)
    await click('[data-step="3"]')
    assert.match(await evaluate("document.getElementById('exchange').textContent"), /policy_json/)
    await click('[data-step="4"]')
    await click('#tamper')
    await until(() => evaluate("document.getElementById('tamper-status').textContent.startsWith('REJECTED')"), 'tamper rejection')
    assert.equal(await evaluate("document.getElementById('result').dataset.verdict"), 'VERIFIED')
    assert.equal(await evaluate('document.documentElement.scrollWidth > window.innerWidth'), false)
    await evaluate('window.scrollTo(0,0)')
    const size = (await command('Page.getLayoutMetrics')).cssContentSize
    const png = await command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: true,
      clip: { x: 0, y: 0, width: viewport.width, height: Math.ceil(size.height), scale: 1 } })
    writeFileSync(join(output, `${viewport.name}.png`), Buffer.from(png.data, 'base64'))
    tests.push({ viewport, original_verified: true, inspect_policy: true, tamper_rejected: true, overflow: false })
    broken = true
    await click('#verify')
    await until(() => evaluate("document.getElementById('result').dataset.verdict==='FAILED'"), 'corrupt download denial')
    assert.equal(await evaluate("document.getElementById('source').textContent"), 'Not verified')
    assert.equal(await evaluate("document.getElementById('tamper').disabled"), true)
    assert.equal(await evaluate("[...document.querySelectorAll('[data-step]')].every(e=>e.disabled)"), true)
    tests.at(-1).corrupt_download_clears_previous_success = true
  }
  assert.deepEqual(exceptions, [])
  assert.ok(network.every(r => r.method === 'GET' && r.url.startsWith(origin + '/')), 'Only same-origin static GETs are allowed')
  assert.ok(observed.every(r => r.method === 'GET' && !['/mcp', '/bootstrap'].includes(r.path)))
  const result = { verdict: 'PASS', scope: 'Actual local Chromium over static files; not a hub build or hosted deployment test',
    browser: chrome, tests, exceptions, requests: observed, browser_network: network,
    mcp_calls: 0, external_page_requests: 0, model_calls: 0 }
  writeFileSync(join(output, 'browser-report.json'), JSON.stringify(result, null, 2) + '\n')
  console.log('PASS desktop/mobile: recorded verification, selectable exchanges, tamper rejection, corrupt replay fail-closed; static GETs only')
} catch (err) {
  console.error('PAGE', await evaluate('({url:location.href,state:document.readyState,body:document.body?.innerText})').catch(()=>null), 'REQUESTS', observed, 'NETWORK', network.map(r=>({...r,url:r.url.slice(0,180)})), 'EXCEPTIONS', exceptions); throw err
} finally {
  socket?.close(); browser.kill('SIGTERM'); server.closeAllConnections()
  await new Promise(resolve => server.close(resolve)); await pause(200)
  rmSync(profile, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 })
}
