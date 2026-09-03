import test from 'node:test';
import assert from 'node:assert/strict';
import { verifyDeployment } from '../src/deployment-verifier.mjs';

test('verifies health plus real memory-authority tool execution', async () => {
  const calls = [];
  const fetchImpl = async (url, init = {}) => {
    calls.push({ url, init });
    if (url.endsWith('/health')) {
      return new Response(JSON.stringify({ status: 'ok', authority: 'NO_AUTHORITY_GRANTED' }), { status: 200 });
    }
    return new Response(JSON.stringify({
      output: 'DENY: stale state',
      toolCalls: ['observe_collective_state', 'evaluate_action_memory'],
      toolCallCount: 2,
    }), { status: 200 });
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
  assert.ok(receipt.agent.toolCalls.includes('evaluate_action_memory'));
  assert.equal(calls[1].init.headers.authorization, 'Bearer supersecret');
});

test('fails closed on unhealthy endpoint', async () => {
  const fetchImpl = async () => new Response(JSON.stringify({ status: 'bad' }), { status: 500 });
  await assert.rejects(
    () => verifyDeployment({ baseUrl: 'https://x', token: 'secret', fetchImpl }),
    /health/i,
  );
});

test('fails closed when live agent does not execute memory authority tool', async () => {
  const fetchImpl = async (url) => url.endsWith('/health')
    ? new Response(JSON.stringify({ status: 'ok', authority: 'NO_AUTHORITY_GRANTED' }), { status: 200 })
    : new Response(JSON.stringify({ output: 'looks fine', toolCalls: [], toolCallCount: 0 }), { status: 200 });

  await assert.rejects(
    () => verifyDeployment({ baseUrl: 'https://x', token: 'secret', fetchImpl }),
    /evaluate_action_memory/,
  );
});

test('receipt never contains bearer token or raw tool arguments', async () => {
  const fetchImpl = async (url) => url.endsWith('/health')
    ? new Response(JSON.stringify({ status: 'ok', authority: 'NO_AUTHORITY_GRANTED' }), { status: 200 })
    : new Response(JSON.stringify({
        output: 'ok',
        toolCalls: ['evaluate_action_memory'],
        toolCallCount: 1,
        rawArguments: 'secret-action-arguments',
      }), { status: 200 });

  const receipt = await verifyDeployment({
    baseUrl: 'https://x',
    token: 'secret-do-not-leak',
    fetchImpl,
  });

  const serialized = JSON.stringify(receipt);
  assert.equal(serialized.includes('secret-do-not-leak'), false);
  assert.equal(serialized.includes('secret-action-arguments'), false);
});
