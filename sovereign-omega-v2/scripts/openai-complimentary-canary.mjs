import { createHash } from 'node:crypto';
import { pathToFileURL } from 'node:url';

export const EXPECTED_PROJECT_ID = 'proj_1eYFqYDJeAZr5Xh3oPRwzKRp';
export const DEFAULT_MODEL = 'gpt-5.6-luna';
export const CANARY_TEXT = 'AEGIS_OPENAI_CANARY_OK';

const ALLOWED_MODELS = new Set(['gpt-5.6-luna', 'gpt-5.6-terra', 'gpt-5.6-sol']);

function canonical(value) {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    return `{${Object.keys(value).sort().map(k => `${JSON.stringify(k)}:${canonical(value[k])}`).join(',')}}`;
  }
  return JSON.stringify(value);
}

export function validateConfig(env = process.env) {
  const apiKey = (env.OPENAI_API_KEY ?? '').trim();
  const projectId = (env.OPENAI_PROJECT_ID ?? '').trim();
  const model = (env.OPENAI_MODEL ?? DEFAULT_MODEL).trim();
  if (!apiKey) throw new Error('OPENAI_API_KEY is required');
  if (projectId !== EXPECTED_PROJECT_ID) {
    throw new Error(`OPENAI_PROJECT_ID must equal the governed AegisOmega project ${EXPECTED_PROJECT_ID}`);
  }
  if (!ALLOWED_MODELS.has(model)) {
    throw new Error('OPENAI_MODEL must be one of gpt-5.6-luna, gpt-5.6-terra, gpt-5.6-sol');
  }
  return { apiKey, projectId, model };
}

export function buildRequest(model) {
  return {
    model,
    input: CANARY_TEXT,
    max_output_tokens: 32,
    store: false,
    reasoning: { effort: 'none' },
  };
}

function extractOutputText(payload) {
  if (typeof payload?.output_text === 'string') return payload.output_text;
  const parts = [];
  for (const item of payload?.output ?? []) {
    for (const content of item?.content ?? []) {
      if (typeof content?.text === 'string') parts.push(content.text);
    }
  }
  return parts.join('');
}

function safeApiError(status, payload) {
  const error = payload?.error ?? {};
  return {
    status,
    type: typeof error.type === 'string' ? error.type : null,
    code: typeof error.code === 'string' ? error.code : null,
    message: typeof error.message === 'string' ? error.message.slice(0, 500) : 'OpenAI request failed',
  };
}

export async function runCanary({ env = process.env, fetchImpl = fetch, now = () => new Date() } = {}) {
  const { apiKey, projectId, model } = validateConfig(env);
  const request = buildRequest(model);
  const response = await fetchImpl('https://api.openai.com/v1/responses', {
    method: 'POST',
    headers: {
      authorization: `Bearer ${apiKey}`,
      'content-type': 'application/json',
      'OpenAI-Project': projectId,
    },
    body: JSON.stringify(request),
  });

  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error('OPENAI_CANARY_FAILED');
    err.details = safeApiError(response.status, payload);
    throw err;
  }

  const outputText = extractOutputText(payload).trim();
  const usage = payload?.usage ?? {};
  const receipt = {
    schema: 'AEGIS_OPENAI_COMPLIMENTARY_CANARY_V1',
    observed_at: now().toISOString(),
    project_id: projectId,
    endpoint: '/v1/responses',
    request: {
      model,
      store: false,
      tools_requested: false,
      max_output_tokens: 32,
    },
    response: {
      id: typeof payload?.id === 'string' ? payload.id : null,
      model: typeof payload?.model === 'string' ? payload.model : null,
      status: typeof payload?.status === 'string' ? payload.status : null,
      service_tier: typeof payload?.service_tier === 'string' ? payload.service_tier : null,
      canary_text_match: outputText === CANARY_TEXT,
    },
    usage: {
      input_tokens: Number.isFinite(usage?.input_tokens) ? usage.input_tokens : null,
      output_tokens: Number.isFinite(usage?.output_tokens) ? usage.output_tokens : null,
      total_tokens: Number.isFinite(usage?.total_tokens) ? usage.total_tokens : null,
    },
    complimentary_billing_status: 'NOT_ESTABLISHED_FROM_API_RESPONSE',
    verification_next: 'Confirm Usage dashboard service-tier grouping shows data sharing incentive tier for this request.',
    write_authority: 'NOT_GRANTED',
    merge_authority: 'NOT_GRANTED',
    deploy_authority: 'NOT_GRANTED',
    financial_authority: 'NOT_GRANTED',
    authority_effect: 'NONE',
  };
  receipt.receipt_sha256 = createHash('sha256').update(canonical(receipt)).digest('hex');
  return receipt;
}

async function main() {
  try {
    const receipt = await runCanary();
    process.stdout.write(`${JSON.stringify(receipt, null, 2)}\n`);
    if (!receipt.response.canary_text_match) process.exitCode = 2;
  } catch (error) {
    const safe = error?.details ?? { message: error instanceof Error ? error.message : 'UNKNOWN_ERROR' };
    process.stderr.write(`${JSON.stringify({ schema: 'AEGIS_OPENAI_COMPLIMENTARY_CANARY_ERROR_V1', ...safe }, null, 2)}\n`);
    process.exitCode = 1;
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) await main();
