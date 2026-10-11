/*
 * AEGIS Ω — evidence-first edge bridge.
 *
 * HTTP availability is NOT proof of constitutional certification. This Edge
 * Function has no access to a verified runtime replay/certificate, so it must
 * return explicit UNKNOWN/UNAVAILABLE rather than fabricated T0 success.
 */
const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, OPTIONS',
  'Access-Control-Allow-Headers': 'authorization, apikey, content-type',
  'Cache-Control': 'no-store',
  'Content-Type': 'application/json',
}

const SCHEMA = 'aegis.bridge.telemetry.v2'
const REASON = 'NO_VERIFIED_GOVERNANCE_RUNTIME_SOURCE'

function reply(status, data) {
  return new Response(JSON.stringify({ schema: SCHEMA, ...data }), {
    status,
    headers: CORS,
  })
}

function unavailable(path) {
  const common = {
    verified: false,
    verification: REASON,
    authority_effect: 'NONE',
    status: 'UNAVAILABLE',
    source: 'edge_without_governance_runtime_attestation',
  }
  if (path === '/node') {
    return reply(503, {
      ...common,
      t0_verdict: null,
      constitutional_hash: null,
      catalog_hash: null,
      corruption_count: null,
      drift_risk: null,
      is_replay_reconstructable: null,
    })
  }
  if (path === '/telemetry') {
    return reply(503, {
      ...common,
      pgcs_passes: null,
      vcg_error: null,
      avg_vcg_error: null,
      drift_index: null,
      gate_acceptance_rate: null,
      corruption_count: null,
      failsafe_state: 'UNKNOWN',
    })
  }
  return reply(503, {
    ...common,
    is_resonant: null,
    is_certified: null,
    phi_convergent: null,
    resonance_coefficient: null,
    ring_valid: null,
  })
}

Deno.serve((req) => {
  if (req.method === 'OPTIONS') {
    return new Response(null, { status: 204, headers: CORS })
  }
  if (req.method !== 'GET') {
    return reply(405, { error: 'METHOD_NOT_ALLOWED', verified: false, authority_effect: 'NONE' })
  }
  const url = new URL(req.url)
  const path = '/' + (url.pathname.split('/').filter(Boolean).pop() || '')
  if (path === '/health') {
    return reply(200, {
      status: 'alive',
      verified: false,
      verification: 'EDGE_LIVENESS_ONLY',
      authority_effect: 'NONE',
    })
  }
  if (path === '/node' || path === '/telemetry' || path === '/resonance') {
    return unavailable(path)
  }
  return reply(404, { error: 'NOT_FOUND', verified: false, authority_effect: 'NONE' })
})
