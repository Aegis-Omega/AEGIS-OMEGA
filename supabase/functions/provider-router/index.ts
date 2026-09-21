import { createClient } from 'jsr:@supabase/supabase-js@2'

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
  'Access-Control-Allow-Methods': 'POST, OPTIONS',
}

const ALLOWED = new Set([
  'AGENT_EXECUTION',
  'CONTAINER_RUNTIME',
  'DURABLE_RUNNER',
  'GPU_COMPUTE',
  'MODEL_INFERENCE',
  'REPOSITORY_AGENT',
  'REPOSITORY_WORKFLOW',
  'WEB_RESEARCH',
  'SERVERLESS_FUNCTION',
  'DATABASE',
  'HTTP_EGRESS',
  'SYMBOLIC_COMPUTE',
  'REPOSITORY_READ',
  'DOCUMENT_RETRIEVAL',
  'EMAIL_RETRIEVAL',
  'CALENDAR_READ',
  'COLLABORATION_READ',
  'KNOWLEDGE_BASE_READ',
  'WORK_TRACKING_READ',
  'CRM_READ',
])

Deno.serve(async (req: Request) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') {
    return new Response(JSON.stringify({ error: 'method_not_allowed' }), {
      status: 405,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  const body = await req.json().catch(() => null) as { capability?: unknown } | null
  const capability = typeof body?.capability === 'string' ? body.capability : ''
  if (!ALLOWED.has(capability)) {
    return new Response(JSON.stringify({
      schema: 'aegis.provider-router.v1',
      outcome: 'DENIED',
      provider_id: null,
      denial_code: 'INVALID_CAPABILITY',
      authority_effect: 'NONE',
    }), {
      status: 400,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  const url = Deno.env.get('SUPABASE_URL') ?? ''
  const serviceKey = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY') ?? ''
  if (!url || !serviceKey) {
    return new Response(JSON.stringify({
      schema: 'aegis.provider-router.v1',
      outcome: 'DENIED',
      provider_id: null,
      denial_code: 'RUNTIME_CREDENTIAL_UNAVAILABLE',
      authority_effect: 'NONE',
    }), {
      status: 503,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  const supabase = createClient(url, serviceKey, { auth: { persistSession: false } })
  const { data, error } = await supabase.rpc('select_provider_runtime_v1', {
    p_capability: capability,
  })

  if (error) {
    console.error('provider-router selector error', error.message)
    return new Response(JSON.stringify({
      schema: 'aegis.provider-router.v1',
      outcome: 'DENIED',
      provider_id: null,
      denial_code: 'SELECTOR_ERROR',
      authority_effect: 'NONE',
    }), {
      status: 503,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  const selected = Array.isArray(data) && data.length > 0 ? data[0] : null
  if (!selected) {
    const { data: receiptHash, error: receiptError } = await supabase.rpc(
      'record_provider_selection_v1',
      {
        p_capability: capability,
        p_outcome: 'DENIED',
        p_provider_id: null,
        p_provider_evidence_hash: null,
        p_denial_code: 'NO_OBSERVED_PROVIDER',
      },
    )
    if (receiptError || typeof receiptHash !== 'string') {
      console.error('provider-router receipt error', receiptError?.message ?? 'missing receipt hash')
      return new Response(JSON.stringify({
        schema: 'aegis.provider-router.v1',
        outcome: 'DENIED',
        provider_id: null,
        denial_code: 'RECEIPT_WRITE_FAILED',
        authority_effect: 'NONE',
      }), {
        status: 503,
        headers: { ...CORS, 'content-type': 'application/json' },
      })
    }

    return new Response(JSON.stringify({
      schema: 'aegis.provider-router.v1',
      outcome: 'DENIED',
      provider_id: null,
      denial_code: 'NO_OBSERVED_PROVIDER',
      selection_receipt_hash: receiptHash,
      authority_effect: 'NONE',
    }), {
      status: 200,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  const { data: receiptHash, error: receiptError } = await supabase.rpc(
    'record_provider_selection_v1',
    {
      p_capability: capability,
      p_outcome: 'SELECTED',
      p_provider_id: selected.provider_id,
      p_provider_evidence_hash: selected.evidence_hash,
      p_denial_code: null,
    },
  )
  if (receiptError || typeof receiptHash !== 'string') {
    console.error('provider-router receipt error', receiptError?.message ?? 'missing receipt hash')
    return new Response(JSON.stringify({
      schema: 'aegis.provider-router.v1',
      outcome: 'DENIED',
      provider_id: null,
      denial_code: 'RECEIPT_WRITE_FAILED',
      authority_effect: 'NONE',
    }), {
      status: 503,
      headers: { ...CORS, 'content-type': 'application/json' },
    })
  }

  return new Response(JSON.stringify({
    schema: 'aegis.provider-router.v1',
    outcome: 'SELECTED',
    provider_id: selected.provider_id,
    evidence_hash: selected.evidence_hash,
    observed_at: selected.observed_at,
    expires_at: selected.expires_at,
    selection_receipt_hash: receiptHash,
    authority_effect: 'NONE',
  }), {
    status: 200,
    headers: { ...CORS, 'content-type': 'application/json' },
  })
})
