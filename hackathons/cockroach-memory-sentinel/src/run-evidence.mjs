export function summarizeRunEvidence(result = {}) {
  const toolCalls = [];

  for (const item of Array.isArray(result.newItems) ? result.newItems : []) {
    if (item?.type !== 'tool_call_item') continue;
    const raw = item.rawItem;
    if (raw?.type === 'function_call' && typeof raw.name === 'string' && raw.name.length > 0) {
      toolCalls.push(raw.name);
    }
  }

  return Object.freeze({
    finalOutput: result.finalOutput ?? null,
    toolCalls: Object.freeze(toolCalls),
    toolCallCount: toolCalls.length,
  });
}
