import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EXPECTED_PROJECT_ID,
  DEFAULT_MODEL,
  CANARY_TEXT,
  validateConfig,
  buildRequest,
  runCanary,
} from '../../scripts/openai-complimentary-canary.mjs';

const baseEnv = { OPENAI_API_KEY: 'sk-test-secret-never-emit', OPENAI_PROJECT_ID: EXPECTED_PROJECT_ID };

function response(payload, ok = true, status = 200) {
  return { ok, status, json: async () => payload };
}

test('requires existing key and exact governed AegisOmega project', () => {
  assert.throws(() => validateConfig({ OPENAI_PROJECT_ID: EXPECTED_PROJECT_ID }), /OPENAI_API_KEY/);
  assert.throws(() => validateConfig({ ...baseEnv, OPENAI_PROJECT_ID: 'proj_other' }), /governed AegisOmega project/);
});

test('defaults to lowest-cost complimentary-eligible GPT-5.6 Luna model', () => {
  assert.equal(validateConfig(baseEnv).model, DEFAULT_MODEL);
  assert.equal(DEFAULT_MODEL, 'gpt-5.6-luna');
});

test('rejects models outside the bounded complimentary canary set', () => {
  assert.throws(() => validateConfig({ ...baseEnv, OPENAI_MODEL: 'gpt-6-astra' }), /OPENAI_MODEL/);
});

test('request is read-only, store=false, tool-free, and tightly output-bounded', () => {
  assert.deepEqual(buildRequest('gpt-5.6-luna'), {
    model: 'gpt-5.6-luna', input: CANARY_TEXT, max_output_tokens: 32, store: false, reasoning: { effort: 'none' },
  });
});

test('successful canary binds project/model/usage and never emits the API key', async () => {
  let call;
  const receipt = await runCanary({
    env: baseEnv,
    now: () => new Date('2026-09-22T17:00:00.000Z'),
    fetchImpl: async (url, init) => {
      call = { url, init };
      return response({
        id: 'resp_fixture', model: 'gpt-5.6-luna', status: 'completed', service_tier: 'default', output_text: CANARY_TEXT,
        usage: { input_tokens: 9, output_tokens: 4, total_tokens: 13 },
      });
    },
  });
  assert.equal(call.url, 'https://api.openai.com/v1/responses');
  assert.equal(call.init.headers['OpenAI-Project'], EXPECTED_PROJECT_ID);
  assert.match(call.init.headers.authorization, /^Bearer /);
  assert.equal(receipt.response.canary_text_match, true);
  assert.equal(receipt.usage.total_tokens, 13);
  assert.equal(receipt.complimentary_billing_status, 'NOT_ESTABLISHED_FROM_API_RESPONSE');
  assert.equal(receipt.authority_effect, 'NONE');
  assert.equal(JSON.stringify(receipt).includes(baseEnv.OPENAI_API_KEY), false);
  assert.match(receipt.receipt_sha256, /^[0-9a-f]{64}$/);
});

test('missing service tier remains unknown rather than inferred complimentary', async () => {
  const receipt = await runCanary({
    env: baseEnv,
    fetchImpl: async () => response({ id:'resp_fixture', model:'gpt-5.6-luna', status:'completed', output_text:CANARY_TEXT, usage:{} }),
  });
  assert.equal(receipt.response.service_tier, null);
  assert.equal(receipt.complimentary_billing_status, 'NOT_ESTABLISHED_FROM_API_RESPONSE');
});

test('API failure returns bounded error fields and does not leak authorization secret', async () => {
  await assert.rejects(
    runCanary({
      env: baseEnv,
      fetchImpl: async () => response({ error: { type:'invalid_request_error', code:'x', message:'bad request' } }, false, 400),
    }),
    error => {
      assert.equal(error.message, 'OPENAI_CANARY_FAILED');
      assert.deepEqual(error.details, { status:400, type:'invalid_request_error', code:'x', message:'bad request' });
      assert.equal(JSON.stringify(error.details).includes(baseEnv.OPENAI_API_KEY), false);
      return true;
    },
  );
});
