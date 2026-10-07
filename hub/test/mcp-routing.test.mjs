import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = path => JSON.parse(readFileSync(new URL('../../' + path, import.meta.url), 'utf8'))
const branch = 'preview/hub/mcp-evidence-v1'
for (const name of ['hub/vercel.json', 'vercel.json']) test(`${name}: exact evidence route precedes the preserved SPA fallback`, () => {
  const c = read(name)
  assert.deepEqual(c.rewrites, [{source:'/labs/mcp', destination:'/labs/mcp/index.html'},
    {source:'/labs/mcp/', destination:'/labs/mcp/index.html'}, {source:'/(.*)', destination:'/index.html'}])
  assert.equal(c.headers.length, 1)
  assert.equal(c.headers[0].source, '/labs/mcp/:path*')
  const h = Object.fromEntries(c.headers[0].headers.map(h=>[h.key,h.value]))
  assert.match(h['Content-Security-Policy'], /frame-ancestors 'none'/)
  assert.match(h['Content-Security-Policy'], /connect-src 'self'/)
  assert.equal(h['Cache-Control'], 'no-store')
  assert.ok(!c.functions && !c.crons && !c.redirects)
})
for (const name of ['hook-generator', 'platform-picker']) test(`${name}: only this hub branch is excluded before Git deployment`, () => {
  const c = read(`${name}/vercel.json`)
  assert.deepEqual(c.git, {deploymentEnabled:{[branch]:false}})
  assert.equal(c.git.deploymentEnabled.main, undefined)
  assert.deepEqual(c.rewrites,[{source:'/api/(.*)',destination:'/api/$1'},{source:'/(.*)',destination:'/index.html'}])
})
