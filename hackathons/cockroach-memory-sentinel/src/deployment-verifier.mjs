function normalizeBaseUrl(baseUrl) {
  if (typeof baseUrl !== 'string' || baseUrl.length === 0) throw new TypeError('baseUrl required');
  return baseUrl.replace(/\/+$/, '');
}

async function parseJson(response, label) {
  if (!response.ok) throw new Error(`${label} request failed with ${response.status}`);
  const body = await response.json();
  if (!body || typeof body !== 'object') throw new Error(`${label} response invalid`);
  return body;
}

export async function verifyDeployment({
  baseUrl,
  token,
  fetchImpl = fetch,
  prompt = 'Inspect agent-7 persistent memory and preserve fail-closed authority.',
}) {
  const root = normalizeBaseUrl(baseUrl);
  if (typeof token !== 'string' || token.length < 1) throw new TypeError('token required');

  const healthResponse = await fetchImpl(`${root}/health`, { method: 'GET' });
  const health = await parseJson(healthResponse, 'health');
  if (health.status !== 'ok' || health.authority !== 'NO_AUTHORITY_GRANTED') {
    throw new Error('health contract failed');
  }

  const agentResponse = await fetchImpl(root, {
    method: 'POST',
    headers: {
      authorization: `Bearer ${token}`,
      'content-type': 'application/json',
    },
    body: JSON.stringify({ prompt }),
  });
  const agent = await parseJson(agentResponse, 'agent');

  return Object.freeze({
    status: 'PASS',
    endpoint: root,
    health: Object.freeze({ status: health.status, authority: health.authority }),
    agent: Object.freeze({ output: agent.output ?? null }),
  });
}
