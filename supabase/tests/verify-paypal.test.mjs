// Offline handler regression: no real payments, emails or database writes.
// Run with Node 22.13+ or Node 24: node --test supabase/tests/verify-paypal.test.mjs
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { stripTypeScriptTypes } from 'node:module'
import { runInNewContext } from 'node:vm'
import test from 'node:test'

const source = readFileSync(new URL('../functions/verify-paypal/index.ts', import.meta.url), 'utf8')
const executable = stripTypeScriptTypes(source.replace(/^import .*$/gm, ''))

async function purchase({ currency = 'USD', value = '49.00', captureStatus = 'COMPLETED', orderStatus = 'COMPLETED' } = {}) {
  let handler
  let provisions = 0
  const env = { PAYPAL_CLIENT_ID: 'fixture', PAYPAL_CLIENT_SECRET: 'fixture', SUPABASE_URL: 'https://fixture.invalid' }
  runInNewContext(executable, {
    Deno: { env: { get: key => env[key] }, serve: fn => { handler = fn } },
    createClient: () => ({ rpc: async () => { provisions++; return { data: 'fixture-api-key', error: null } } }),
    issueGrantToken: async () => 'fixture-tool-token',
    CORS: {}, Response, btoa,
    console: { error() {} },
    fetch: async url => {
      if (url.endsWith('/v1/oauth2/token')) return Response.json({ access_token: 'fixture' })
      if (url.endsWith('/v2/checkout/orders/fixture-order/capture')) {
        return Response.json({ status: orderStatus, purchase_units: [{ payments: { captures: [{
          status: captureStatus, amount: { currency_code: currency, value },
        }] } }] })
      }
      if (url === 'https://fixture.invalid/functions/v1/notify') return Response.json({})
      throw new Error('Unexpected outbound request')
    },
  })
  const response = await handler(new Request('https://fixture.invalid', {
    method: 'POST', body: JSON.stringify({ order_id: 'fixture-order', tier: 'operator', email: 'buyer@example.test' }),
  }))
  return { status: response.status, provisions }
}

test('completed USD payment provisions one key', async () => {
  assert.deepEqual(await purchase(), { status: 200, provisions: 1 })
})

test('whole-dollar USD amount is accepted', async () => {
  assert.deepEqual(await purchase({ value: '49' }), { status: 200, provisions: 1 })
})

for (const [name, fixture] of [
  ['non-USD amount', { currency: 'EUR' }],
  ['missing currency', { currency: null }],
  ['pending capture', { captureStatus: 'PENDING' }],
  ['denied capture', { captureStatus: 'DENIED' }],
  ['malformed amount', { value: 'invalid' }],
  ['partially numeric amount', { value: '49USD' }],
  ['below-floor amount', { value: '1.00' }],
  ['incomplete order', { orderStatus: 'APPROVED' }],
]) {
  test(`${name} never provisions a key`, async () => {
    const result = await purchase(fixture)
    assert.notEqual(result.status, 200)
    assert.equal(result.provisions, 0)
  })
}
