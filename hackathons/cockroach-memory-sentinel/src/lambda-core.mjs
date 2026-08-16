function json(statusCode, payload) {
  return {
    statusCode,
    headers: { 'content-type': 'application/json' },
    body: JSON.stringify(payload),
  };
}

export function createLambdaHandler({ createStore, runAgent, demoToken = null }) {
  if (typeof createStore !== 'function' || typeof runAgent !== 'function') {
    throw new TypeError('dependencies required');
  }

  return async function handler(event = {}) {
    const method = event.requestContext?.http?.method ?? event.httpMethod ?? 'GET';
    const path = event.rawPath ?? event.path ?? '/';

    if (method === 'GET' && path === '/health') {
      return json(200, { status: 'ok', authority: 'NO_AUTHORITY_GRANTED' });
    }

    if (method !== 'POST') return json(405, { error: 'METHOD_NOT_ALLOWED' });

    if (demoToken) {
      const auth = event.headers?.authorization ?? event.headers?.Authorization ?? '';
      if (auth !== `Bearer ${demoToken}`) return json(401, { error: 'UNAUTHORIZED' });
    }

    let body;
    try {
      body = typeof event.body === 'string' ? JSON.parse(event.body) : (event.body ?? {});
    } catch {
      return json(400, { error: 'INVALID_JSON' });
    }

    if (typeof body.prompt !== 'string' || body.prompt.trim().length === 0) {
      return json(400, { error: 'PROMPT_REQUIRED' });
    }

    const store = await createStore();
    const result = await runAgent({ prompt: body.prompt, store });
    return json(200, {
      output: result.finalOutput ?? null,
      toolCalls: Array.isArray(result.toolCalls) ? result.toolCalls : [],
      toolCallCount: Number.isSafeInteger(result.toolCallCount) ? result.toolCallCount : 0,
    });
  };
}
