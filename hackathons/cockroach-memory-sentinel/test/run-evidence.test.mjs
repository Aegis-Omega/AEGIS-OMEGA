import test from 'node:test';
import assert from 'node:assert/strict';
import { summarizeRunEvidence } from '../src/run-evidence.mjs';

test('extracts only tool names and final output from SDK run result', () => {
  const summary = summarizeRunEvidence({
    finalOutput: 'DENY',
    newItems: [
      {
        type: 'tool_call_item',
        rawItem: {
          type: 'function_call',
          name: 'observe_collective_state',
          arguments: '{"nodeId":"agent-7"}',
        },
      },
      {
        type: 'tool_call_output_item',
        rawItem: { type: 'function_call_output', output: 'secret-ish raw data' },
      },
      {
        type: 'tool_call_item',
        rawItem: {
          type: 'function_call',
          name: 'evaluate_action_memory',
          arguments: '{"action":"secret"}',
        },
      },
    ],
  });

  assert.deepEqual(summary, {
    finalOutput: 'DENY',
    toolCalls: ['observe_collective_state', 'evaluate_action_memory'],
    toolCallCount: 2,
  });
  assert.equal(JSON.stringify(summary).includes('secret-ish'), false);
  assert.equal(JSON.stringify(summary).includes('"action"'), false);
});

test('handles missing items without inventing tool use', () => {
  assert.deepEqual(summarizeRunEvidence({ finalOutput: 'NOT_ESTABLISHED' }), {
    finalOutput: 'NOT_ESTABLISHED',
    toolCalls: [],
    toolCallCount: 0,
  });
});
