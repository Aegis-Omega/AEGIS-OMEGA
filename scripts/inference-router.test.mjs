import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { stripTypeScriptTypes } from 'node:module';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import test from 'node:test';

const source = readFileSync(resolve(import.meta.dirname, '../packages/shared/lib/inference-router.ts'), 'utf8');
const providers = [
  ['openai-compat', 'openai', 'VITE_ENABLE_OPENAI'],
  ['azure-openai', 'azure', 'VITE_ENABLE_AZURE'],
  ['nebius-token-factory', 'nebius', 'VITE_ENABLE_NEBIUS'],
  ['dashscope', 'dashscope', 'VITE_ENABLE_DASHSCOPE'],
];
const session = 'fixture.user-session.signature';
function fixture(env = {}, responder = () => new Response(JSON.stringify({ reply: 'answer', model: 'server-model' }))) {
  const calls = [];
  const context = vm.createContext({
    env, URL, Response, AbortSignal, Date,
    fetch: async (url, init) => { calls.push({ url: String(url), init }); return responder(url, init); },
  });
  const code = stripTypeScriptTypes(source.replace(/import\.meta\.env/g, 'env').replace(/^export /gm, ''));
  new vm.Script(code + '\nthis.api = { routeInference, configuredBackends };').runInContext(context);
  return { ...context.api, calls };
}
const request = (backend, token = session) => ({ backend, userAccessToken: token, systemPrompt: 'S', userMessage: 'U' });
for (const [backend, provider, flag] of providers) {
  test(`${provider}: missing session denies before network`, async () => {
    const f = fixture({ [flag]: 'true' });
    await assert.rejects(f.routeInference(request(backend, '')), /session/i);
    assert.equal(f.calls.length, 0);
  });
  test(`${provider}: one authenticated server proxy request, server model provenance`, async () => {
    const f = fixture({ [flag]: 'true', VITE_SUPABASE_ANON_KEY: 'public-anon-key' });
    const result = await f.routeInference({ ...request(backend), model: 'client-guess' });
    assert.equal(result.model, 'server-model');
    assert.equal(result.backend, backend);
    assert.equal(result.fallback_count, 0);
    assert.equal(f.calls.length, 1);
    const { url, init } = f.calls[0];
    assert.equal(url, 'https://rwehltdwpsncnwxzkwik.supabase.co/functions/v1/chat');
    assert.equal(init.headers.Authorization, `Bearer ${session}`);
    assert.equal(init.headers.apikey, 'public-anon-key');
    assert.equal(init.redirect, 'error');
    assert.equal(JSON.parse(init.body).provider, provider);
    assert.ok(!init.body.includes('client-guess'));
  });
  test(`${provider}: disabled denies before network`, async () => {
    const f = fixture();
    await assert.rejects(f.routeInference(request(backend)), /not enabled/i);
    assert.equal(f.calls.length, 0);
  });
  test(`${provider}: server denial never retries or switches provider`, async () => {
    const f = fixture({ [flag]: 'true', VITE_DASHSCOPE_API_KEY: 'SYNTHETIC', VITE_CLAUDE_API_KEY: 'SYNTHETIC' },
      () => new Response(JSON.stringify({ error: 'AI unavailable', provider_status: 'disabled' })));
    await assert.rejects(f.routeInference(request(backend)), /unavailable/i);
    assert.equal(f.calls.length, 1);
  });
}
test('public anon key cannot substitute for user session', async () => {
  const f = fixture({ VITE_ENABLE_OPENAI: 'true', VITE_SUPABASE_ANON_KEY: session });
  await assert.rejects(f.routeInference(request('openai-compat')), /session/i);
  assert.equal(f.calls.length, 0);
});
test('default routing cannot spend through an implicitly selected paid provider', async () => {
  const f = fixture(Object.fromEntries(providers.map(([, , flag]) => [flag, 'true'])), () => { throw Error('local unavailable'); });
  await assert.rejects(f.routeInference({ systemPrompt: 'S', userMessage: 'U', userAccessToken: session }), /All inference backends failed/);
  assert.ok(f.calls.every(c => !c.url.includes('/functions/v1/chat')));
});
test('legacy browser provider keys do not activate paid routes', () => {
  const f = fixture({ VITE_DASHSCOPE_API_KEY: 'SYNTHETIC', VITE_CLAUDE_API_KEY: 'SYNTHETIC' });
  assert.ok(!f.configuredBackends().includes('dashscope'));
  assert.ok(!f.configuredBackends().includes('claude'));
});
test('Claude denies without a server proxy rather than using browser secret', async () => {
  const f = fixture({ VITE_CLAUDE_API_KEY: 'SYNTHETIC' });
  await assert.rejects(f.routeInference(request('claude')), /server proxy/i);
  assert.equal(f.calls.length, 0);
});
for (const body of [{ reply: 'answer' }, { reply: {}, model: 'server' }, { reply: 'answer', model: '' }]) {
  test(`reject incomplete success: ${JSON.stringify(body)}`, async () => {
    const f = fixture({ VITE_ENABLE_OPENAI: 'true' }, () => new Response(JSON.stringify(body)));
    await assert.rejects(f.routeInference(request('openai-compat')), /response/i);
    assert.equal(f.calls.length, 1);
  });
}
for (const url of ['http://example.test', 'https://user:pass@example.test', 'https://example.test/path', 'https://example.test/?q=1']) {
  test(`invalid proxy origin denies before credentials are sent: ${url}`, async () => {
    const f = fixture({ VITE_ENABLE_OPENAI: 'true', VITE_SUPABASE_URL: url });
    await assert.rejects(f.routeInference(request('openai-compat')), /origin/i);
    assert.equal(f.calls.length, 0);
  });
}
test('upstream error body is not exposed to the caller', async () => {
  const f = fixture({ VITE_ENABLE_OPENAI: 'true' }, () => new Response('PRIVATE_UPSTREAM_BODY', { status: 503 }));
  await assert.rejects(f.routeInference(request('openai-compat')), error => !error.message.includes('PRIVATE_UPSTREAM_BODY') && error.message.includes('503'));
  assert.equal(f.calls.length, 1);
});

// Compose the actual browser router with the actual deployed-function candidate.
// Only Auth/RPC/provider services are synthetic; no public endpoint is called.
function chatHandler(userId = 'operator') {
  const base = resolve(import.meta.dirname, '../supabase/functions');
  const paths = ['_shared/cors.ts', '_shared/http.ts', '_shared/nebius-auth.ts', '_shared/nebius-budget.ts', '_shared/nebius-endpoint.ts', '_shared/chat-provider-gate.ts', 'chat/index.ts'];
  const code = stripTypeScriptTypes(paths.map(p => readFileSync(resolve(base, p), 'utf8')).join('\n').replace(/^import .*$/gm, '').replace(/^export /gm, ''));
  let handler;
  let providerCalls = 0;
  const env = {
    SUPABASE_URL: 'https://auth.invalid', SUPABASE_SERVICE_ROLE_KEY: 'SYNTHETIC',
    CHAT_ALLOWED_USER_IDS: 'operator', CHAT_NEBIUS_ALLOWED_USER_IDS: 'operator',
    CHAT_ENABLE_OPENAI: 'true', CHAT_ENABLE_AZURE: 'true', CHAT_ENABLE_NEBIUS: 'true',
    OPENAI_API_KEY: 'SYNTHETIC', OPENAI_MODEL: 'server-model',
    NEBIUS_API_KEY: 'SYNTHETIC', NEBIUS_MODEL: 'server-nebius', DASHSCOPE_API_KEY: 'SYNTHETIC',
    AZURE_OPENAI_API_KEY: 'SYNTHETIC', AZURE_OPENAI_ENDPOINT: 'https://azure.invalid', AZURE_OPENAI_DEPLOYMENT: 'server-azure',
  };
  const sandbox = {
    Request, Response, URL, AbortController, setTimeout, clearTimeout,
    console: { error() {} },
    Deno: { env: { get: key => env[key] }, serve: fn => { handler = fn; } },
    createClient: () => ({
      auth: { getUser: async token => { assert.equal(token, session); return { data: { user: { id: userId } }, error: null }; } },
      rpc: async (name, args) => {
        if (name === 'get_provider_runtime_candidate_v1') return { data: [{ provider_id: args.p_provider_id }], error: null };
        if (name === 'reserve_nebius_inference_attempt_v1') return { data: true, error: null };
        throw Error('Unexpected RPC');
      },
    }),
    fetch: async () => { providerCalls++; return new Response(JSON.stringify({ choices: [{ message: { content: 'composed reply' } }] })); },
  };
  new vm.Script(code).runInContext(vm.createContext(sandbox));
  return { respond: (url, init) => handler(new Request(url, init)), calls: () => providerCalls };
}
for (const [backend, provider, flag] of providers) {
  test(`${provider}: real router-to-handler composition preserves authenticated route`, async () => {
    const server = chatHandler();
    const f = fixture({ [flag]: 'true', VITE_SUPABASE_ANON_KEY: 'public-anon-key' }, server.respond);
    const result = await f.routeInference(request(backend));
    assert.equal(result.content, 'composed reply');
    assert.equal(result.backend, backend);
    assert.equal(server.calls(), 1);
    assert.equal(f.calls.length, 1);
  });
  test(`${provider}: real handler denies wrong verified user before inference`, async () => {
    const server = chatHandler('unapproved-user');
    const f = fixture({ [flag]: 'true' }, server.respond);
    await assert.rejects(f.routeInference(request(backend)), /401/);
    assert.equal(server.calls(), 0);
    assert.equal(f.calls.length, 1);
  });
}
