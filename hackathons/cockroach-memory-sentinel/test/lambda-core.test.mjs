import test from 'node:test';
import assert from 'node:assert/strict';
import { createLambdaHandler } from '../src/lambda-core.mjs';

test('health check does not allocate model or database resources', async () => {
  let allocations = 0;
  const handler = createLambdaHandler({
    createStore: async () => { allocations++; return {}; },
    runAgent: async () => { allocations++; return {}; },
  });
  const response = await handler({ rawPath: '/health', requestContext: { http: { method: 'GET' } } });
  assert.equal(response.statusCode, 200);
  assert.equal(allocations, 0);
});

test('missing prompt fails before model/database execution', async () => {
  let allocations = 0;
  const handler = createLambdaHandler({
    createStore: async () => { allocations++; return {}; },
    runAgent: async () => { allocations++; return {}; },
  });
  const response = await handler({ rawPath: '/', requestContext: { http: { method: 'POST' } }, body: '{}' });
  assert.equal(response.statusCode, 400);
  assert.equal(allocations, 0);
});

test('valid request runs agent against injected store and returns structured output', async () => {
  const store = { id: 'cockroach' };
  let received;
  const handler = createLambdaHandler({
    createStore: async () => store,
    runAgent: async (args) => { received = args; return { finalOutput: 'DENY: stale state' }; },
  });
  const response = await handler({
    rawPath: '/',
    requestContext: { http: { method: 'POST' } },
    body: JSON.stringify({ prompt: 'check agent-7' }),
  });
  assert.equal(response.statusCode, 200);
  assert.equal(received.store, store);
  assert.equal(received.prompt, 'check agent-7');
  assert.deepEqual(JSON.parse(response.body), { output: 'DENY: stale state' });
});
