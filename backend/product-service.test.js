import assert from 'node:assert/strict';
import { mkdtemp } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import test from 'node:test';
import { ProductService } from './product-service.js';

test('a billing webhook durably grants an entitlement and is idempotent', async () => {
  const service = new ProductService({ file: join(await mkdtemp(join(tmpdir(), 'aegis-')), 'state.json') });
  const account = await service.account('acme');
  const checkout = await service.checkout(account, 'operator');
  assert.equal(checkout.status, 'pending_payment');
  assert.equal(account.plan, 'explorer');
  assert.deepEqual(await service.applyWebhook({ id: 'evt_1', type: 'entitlement.granted', data: { accountId: 'acme', plan: 'operator', invoiceId: 'inv_1' } }), { duplicate: false, plan: 'operator' });
  assert.equal((await service.overview(account)).plan.id, 'operator');
  assert.deepEqual(await service.applyWebhook({ id: 'evt_1', type: 'entitlement.granted', data: { accountId: 'acme', plan: 'operator' } }), { duplicate: true });
});

test('quota enforcement returns the exhausted dimension and never stores prompt properties', async () => {
  const service = new ProductService({ file: join(await mkdtemp(join(tmpdir(), 'aegis-')), 'state.json') });
  const account = await service.account('acme');
  const result = await service.recordUsage(account, { requests: 101, tokens: 0, spendCents: 0 });
  assert.equal(result.allowed, false); assert.equal(result.dimension, 'requests');
  await service.track(account, 'signup', { prompt: 'private', source: 'test' });
  assert.deepEqual(account.analytics.at(-1).properties, { source: 'test' });
});
