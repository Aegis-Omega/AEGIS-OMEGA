/**
 * AEGIS Ω Public Observation Gateway
 * Only proxies the already-public GET /platform/status; no credentials,
 * execution, database, provider calls, mutation, or private telemetry.
 */
const UPSTREAM = 'https://aegis-vertex.aegisomega.com/platform/status';
const ORIGIN = 'https://aegis-vertex.aegisomega.com';
const VERSION = 'AEGIS_PUBLIC_OBSERVATION_GATE_V1';
const MAX_BYTES = 8192;
const PUBLIC_HEADERS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Max-Age': '600',
  'Cache-Control': 'no-store',
  'Content-Type': 'application/json; charset=utf-8',
  'X-Content-Type-Options': 'nosniff',
  'Cross-Origin-Resource-Policy': 'cross-origin',
  'Referrer-Policy': 'no-referrer',
};
function response(body, status = 200) { return new Response(JSON.stringify(body), { status, headers: PUBLIC_HEADERS }); }
function statusIsValid(v) {
  if (!v || typeof v !== 'object' || Array.isArray(v)) return false;
  return typeof v.version === 'string' && v.version.length > 0 && v.version.length <= 80
    && typeof v.contract_version === 'string' && v.contract_version.length > 0 && v.contract_version.length <= 80
    && Number.isSafeInteger(v.total_agents) && v.total_agents >= 0 && v.total_agents <= 100000
    && typeof v.available === 'boolean'
    && (v.chain_valid === null || typeof v.chain_valid === 'boolean')
    && (v.audit_chain_hash === null || (typeof v.audit_chain_hash === 'string' && v.audit_chain_hash.length <= 256));
}
async function handler(req) {
  const url = new URL(req.url);
  if (url.pathname === '/api/health' && req.method === 'GET') {
    return response({ service: VERSION, status: 'up', mode: 'PUBLIC_READ_ONLY', upstream: ORIGIN, attestation: 'NOT_VERIFIED' });
  }
  if (url.pathname !== '/platform/status' && url.pathname !== '/api/status') {
    return response({error:'NOT_FOUND',service:VERSION}, 404);
  }
  if (req.method === 'OPTIONS') return new Response(null, {status:204,headers: PUBLIC_HEADERS});
  if (req.method !== 'GET') return response({error:'METHOD_NOT_ALLOWED'},405);
  const c = new AbortController();
  const deadline = setTimeout(()=>c.abort(), 3800);
  try {
    const upstream = await fetch(UPSTREAM, {method:'GET', redirect:'error', signal:c.signal,
      headers:{Accept:'application/json', 'User-Agent':'AEGIS-Public-Observation-Gateway/1.0'},
    });
    if (!upstream.ok) return response({error:'UPSTREAM_UNAVAILABLE',upstream_status:upstream.status,attestation:'NOT_VERIFIED'},503);
    const declared = Number(upstream.headers.get('content-length') || '0');
    if (declared > MAX_BYTES) return response({error:'UPSTREAM_TOO_LARGE'},502);
    // Read at most MAX_BYTES of the actual UTF-8 wire payload. `response.text()`
    // without a streaming limit can allocate arbitrarily large upstream bodies.
    if (!upstream.body) return response({error:'UPSTREAM_EMPTY_BODY'},502);
    const reader = upstream.body.getReader();
    const chunks = [];
    let total = 0;
    let oversized = false;
    try {
      for (;;) {
        const { done, value } = await reader.read();
        if (done) break;
        if (!value) continue;
        total += value.byteLength;
        if (total > MAX_BYTES) { oversized = true; break; }
        chunks.push(value);
      }
    } finally {
      if (oversized) await reader.cancel().catch(() => {});
    }
    if (oversized) return response({error:'UPSTREAM_TOO_LARGE'},502);
    const bytes = new Uint8Array(total);
    let offset = 0;
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
    let env;
    try { env = JSON.parse(new TextDecoder('utf-8', { fatal:true }).decode(bytes)); }
    catch { return response({error:'UPSTREAM_INVALID_JSON'},502); }
    if (!env || typeof env !== 'object' || Array.isArray(env) || !statusIsValid(env.data)) {
      return response({error:'UPSTREAM_INVALID_CONTRACT'},502);
    }
    const d = env.data;
    // Explicit allowlist: do NOT relay customer usage, emails or future extra fields.
    const sanitized = {
      version: d.version, contract_version: d.contract_version, total_agents: d.total_agents,
      chain_valid: d.chain_valid ?? null, audit_chain_hash: d.audit_chain_hash ?? null, available: d.available,
    };
    return response({
      contract_version: env.contract_version === sanitized.contract_version ? env.contract_version : sanitized.contract_version,
      execution_id: typeof env.execution_id === 'string' ? env.execution_id.slice(0,100) : 'unavailable',
      timestamp: typeof env.timestamp === 'string' ? env.timestamp.slice(0,60) : null,
      data: sanitized,
      gateway: {schema:VERSION,observed_at:new Date().toISOString(),upstream:ORIGIN,
        authority:'UNSIGNED_REMOTE_REPORT_NOT_INDEPENDENTLY_VERIFIED'},
    });
  } catch(e) {
    return response({error:'UPSTREAM_FETCH_FAILED',detail:e?.name==='AbortError'?'TIMEOUT':'NETWORK_OR_POLICY',attestation:'NOT_VERIFIED'},503);
  } finally { clearTimeout(deadline); }
}
addEventListener('fetch', evt => evt.respondWith(handler(evt.request)));