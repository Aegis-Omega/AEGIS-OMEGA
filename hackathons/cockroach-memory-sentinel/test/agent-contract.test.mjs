import test from 'node:test';
import assert from 'node:assert/strict';
import { MEMORY_SENTINEL_INSTRUCTIONS } from '../src/agent-contract.mjs';

test('agent instructions require memory evaluation before consequential action', () => {
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /evaluate_action_memory/);
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /before any consequential action/i);
});

test('agent instructions prohibit model or MCM authority grants', () => {
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /OBSERVATION_ONLY\/T2/);
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /never grant, expand, or infer authority/i);
});

test('agent instructions preserve DENY and uncertainty', () => {
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /DENY/);
  assert.match(MEMORY_SENTINEL_INSTRUCTIONS, /NOT_ESTABLISHED/);
});
