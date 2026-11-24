import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { readFileSync, readdirSync } from 'node:fs'

const repo = new URL('../../', import.meta.url)
const read = path => readFileSync(new URL(path, repo))
const config = path => JSON.parse(read(path))
const labDir = 'hub/public/labs/mcp/'
const release = '4bcd50774e3d1236099839bd9b69ec9086915fff'
const blobs = {
  'app.mjs': 'c71762b5c8f9d68500412004891d41125d0f1977',
  'friction-log.json': '0a8bf74e827edfe10d486ba7dd0e0b34c229c327',
  'index.html': '5355871a42b039216cc8feb40e422cf0554ba6cd',
  'receipt.json': 'b5da18fae41f2ae9229bf998ba2228ea20e3436e',
  'style.css': '2230fe1895a73856349e78f5160510477b3d2fd8',
  'trace.json': '831f62dcad8048add0db26162a12f1c63d89f55a',
  'verify.mjs': '3d463c95528066d35cde1e303fca0705230d7fa0',
}
const gitBlobId = bytes => createHash('sha1')
  .update(Buffer.from('blob ' + bytes.length + '\0')).update(bytes).digest('hex')

test('static MCP files are byte-identical to historical production source ' + release, () => {
  assert.deepEqual(readdirSync(new URL(labDir, repo)).sort(), Object.keys(blobs).sort())
  for (const [filename, id] of Object.entries(blobs)) {
    assert.equal(gitBlobId(read(labDir + filename)), id, filename)
  }
})

function checkRouting(c) {
  assert.deepEqual(c.rewrites, [
    { source: '/labs/mcp', destination: '/labs/mcp/index.html' },
    { source: '/labs/mcp/', destination: '/labs/mcp/index.html' },
    { source: '/(.*)', destination: '/index.html' },
  ])
  assert.deepEqual(c.headers.map(h => h.source), ['/labs/mcp/:path*', '/labs/mcp/'])
  assert.deepEqual(c.headers[1].headers, c.headers[0].headers)
  const h = Object.fromEntries(c.headers[0].headers.map(v => [v.key, v.value]))
  assert.match(h['Content-Security-Policy'], /(?:^|; )default-src 'none'(?:;|$)/)
  assert.match(h['Content-Security-Policy'], /(?:^|; )connect-src 'self'(?:;|$)/)
  assert.match(h['Content-Security-Policy'], /(?:^|; )frame-ancestors 'none'(?:;|$)/)
  assert.match(h['Content-Security-Policy'], /(?:^|; )form-action 'none'(?:;|$)/)
  assert.equal(h['Cache-Control'], 'no-store')
  for (const key of ['redirects', 'routes', 'functions', 'crons']) {
    assert.equal(Object.hasOwn(c, key), false, 'This static restore must not introduce ' + key)
  }
}

for (const path of ['vercel.json', 'hub/vercel.json']) {
  test(path + ' restores scoped static evidence while preserving SPA fallback', () => {
    checkRouting(config(path))
  })
}

test('release guard rejects regressions that shadow the lab or introduce redirects', () => {
  const baseline = config('hub/vercel.json')
  const shadowed = structuredClone(baseline)
  shadowed.rewrites.reverse()
  assert.throws(() => checkRouting(shadowed))
  const redirected = structuredClone(baseline)
  redirected.redirects = [{ source: '/labs/mcp', destination: '/', permanent: true }]
  assert.throws(() => checkRouting(redirected))
  const widened = structuredClone(baseline)
  widened.headers[0].source = '/(.*)'
  assert.throws(() => checkRouting(widened))
})
