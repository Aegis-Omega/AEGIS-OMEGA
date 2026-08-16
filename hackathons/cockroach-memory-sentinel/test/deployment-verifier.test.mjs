import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyDeployment } from '../src/deployment-verifier.mjs';

test('verifies public health and authenticated agent request', async () => {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, init });
    if (url.endsWith('/health')) {
      return new Response(JSON.stringify({ status: 'ok', authority: 'NO_AUTHORITY_GRANTED' }), { status: 200 });
    }
    return new Response(JSON.stringify({ output: 'DENY: stale state' }), { status: 200 });
  };

  const receipt = await verifyDeployment({
    baseUrl: 'https://example.lambda-url.aws',
    token: 'supersecret',
    fetchImpl,
    prompt: 'check agent-7',
  });

  assert.equal(receipt.status, 'PASS');
  assert.equal(receipt.health.authority, 'NO_AUTHORITY_GRANTED');
  assert.equal(receipt.agent.output, 'DENY: stale state');
  assert.equal(calls[1].init.headers.authorization, 'Bearer supersecret');
});

test('fails closed on unhealthy endpoint', async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ status: 'bad' }), { status: 500 });
  await assert.rejects(
    () => verifyDeployment({ baseUrl: 'https://x', token: 'secret', fetchImpl }),
    /health/i,
  );
});

test('receipt never contains bearer token', async () => {
  const fetchImpl = async (url) => url.endsWith('/health')
    ? new Response(JSON.stringify({ status: 'ok', authority: 'NO_AUTHORITY_GRANTED' }), { status: 200 })
    : new Response(JSON.stringify({ output: 'ok' }), { status: 200 });

  const receipt = await verifyDeployment({
    baseUrl: 'https://x',
    token: 'secret-do-not-leak',
    fetchImpl,
  });

  assert.equal(JSON.stringify(receipt).includes('secret-do-not-leak'), false);
});
