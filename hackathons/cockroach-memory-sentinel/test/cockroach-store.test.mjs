import test from 'node:test';
import assert from 'node:assert/strict';
import { CockroachMemoryStore, toVectorLiteral } from '../src/cockroach-store.mjs';

test('vector literal requires exactly 1536 finite dimensions', () => {
  const embedding = Array(1536).fill(0);
  embedding[0] = 0.25;
  embedding[1535] = -0.5;
  const literal = toVectorLiteral(embedding);
  assert.ok(literal.startsWith('[0.25,'));
  assert.ok(literal.endsWith(',-0.5]'));
  assert.throws(() => toVectorLiteral([1, 2, 3]), /1536/);
  const bad = Array(1536).fill(0);
  bad[3] = Number.NaN;
  assert.throws(() => toVectorLiteral(bad), /finite/);
});

test('getNodeState uses a parameterized primary-key lookup', async () => {
  const calls = [];
  const client = {
    query: async (sql, params) => {
      calls.push({ sql, params });
      return { rows: [{ node_id: 'agent-7', state_digest: 's', policy_digest: 'p', authority_epoch: '7' }] };
    },
  };
  const store = new CockroachMemoryStore(client);
  const row = await store.getNodeState('agent-7');
  assert.equal(row.node_id, 'agent-7');
  assert.deepEqual(calls[0].params, ['agent-7']);
  assert.match(calls[0].sql, /WHERE node_id = \$1/);
});

test('findEvidence uses Cockroach VECTOR distance and a bounded limit', async () => {
  const calls = [];
  const client = {
    query: async (sql, params) => {
      calls.push({ sql, params });
      return { rows: [{ memory_id: 'm1', distance: 0.1 }] };
    },
  };
  const store = new CockroachMemoryStore(client);
  const rows = await store.findEvidence({
    epistemicTier: 'T2',
    embedding: Array(1536).fill(0.01),
    limit: 3,
  });
  assert.equal(rows.length, 1);
  assert.equal(calls[0].params[0], 'T2');
  assert.equal(calls[0].params[2], 3);
  assert.match(calls[0].sql, /embedding <-> \$2::VECTOR/);
  await assert.rejects(
    () => store.findEvidence({ epistemicTier: 'T2', embedding: Array(1536).fill(0), limit: 51 }),
    /limit/,
  );
});
