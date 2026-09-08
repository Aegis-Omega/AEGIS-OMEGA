/**
 * AEGIS Omega — Cloudflare Worker Bridge
 *
 * Serves constitutional telemetry endpoints for the hub and
 * routes /platform/collaborate to the Anthropic API directly.
 * All other requests fall through to the WebGPU static assets.
 *
 * Secrets (set via: npx wrangler secret put ANTHROPIC_API_KEY):
 *   ANTHROPIC_API_KEY — required for /platform/collaborate
 */

const PHI = 0.6180339887
const CONSTITUTIONAL_HASH = '2620353140d6b43cd3ea633d0c59664b8669f6475d25297968879cffed187626'
const CONTRACT_VERSION = '1.0.0'

interface Fetcher {
  fetch(request: Request | string, init?: RequestInit): Promise<Response>
}

interface Env {
  ANTHROPIC_API_KEY?: string
  SUPABASE_URL?: string
  SUPABASE_SERVICE_ROLE_KEY?: string
  ASSETS: Fetcher
}

const CORS = {
  'Access-Control-Allow-Origin': '*',
  'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
  'Access-Control-Allow-Headers': 'Content-Type, X-API-Key, Idempotency-Key',
}

async function sha256(value: string): Promise<string> {
  const bytes = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(value)))
  return Array.from(bytes).map(x => x.toString(16).padStart(2, '0')).join('')
}

/** Fail closed before inference: a key must resolve to a live entitlement and
 * the RPC atomically applies the plan's usage quota. */
async function authorizeInference(request: Request, env: Env): Promise<boolean> {
  const key = request.headers.get('x-api-key')
  if (!key || !env.SUPABASE_URL || !env.SUPABASE_SERVICE_ROLE_KEY) return false
  const response = await fetch(`${env.SUPABASE_URL.replace(/\/$/, '')}/rest/v1/rpc/authorize_api_key_usage`, {
    method: 'POST',
    headers: { 'content-type': 'application/json', apikey: env.SUPABASE_SERVICE_ROLE_KEY, authorization: `Bearer ${env.SUPABASE_SERVICE_ROLE_KEY}` },
    body: JSON.stringify({ p_key_hash: await sha256(key), p_idempotency_key: request.headers.get('idempotency-key') ?? crypto.randomUUID(), p_quantity: 1 }),
  })
  if (!response.ok) return false
  const rows = await response.json() as unknown[]
  return rows.length === 1
}

function ok(data: unknown): Response {
  return new Response(JSON.stringify(data), {
    headers: { 'Content-Type': 'application/json', ...CORS },
  })
}

function err(msg: string, code: string, status: number): Response {
  return new Response(JSON.stringify({ error: msg, code }), {
    status,
    headers: { 'Content-Type': 'application/json', ...CORS },
  })
}

function seq(): number {
  return Math.floor(Date.now() / 1000) % 1_000_000
}

function envelope(executionId: string, data: unknown) {
  return {
    contract_version: CONTRACT_VERSION,
    execution_id: executionId,
    timestamp: new Date().toISOString(),
    // The edge holds no replay log, so it cannot establish this. Reported as
    // unknown rather than asserted; the governance runtime is the only place
    // that can answer it.
    is_replay_reconstructable: null,
    replay_evidence: 'not_available_at_edge',
    data,
  }
}

/** Opaque correlation id. Random by intent — never presented as a digest. */
function execId(prefix: string): string {
  return prefix + '-' + crypto.randomUUID()
}

/** SHA-256 over the exact bytes supplied. The only hash this file may emit. */
async function sha256Hex(input: string): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(input))
  return [...new Uint8Array(digest)].map(b => b.toString(16).padStart(2, '0')).join('')
}

const DEPARTMENTS = [
  'Finance', 'Legal', 'Engineering', 'Marketing', 'Sales', 'Operations',
  'HR', 'Product', 'Design', 'Data', 'Security', 'Compliance',
  'Research', 'Strategy', 'Customer Success', 'Partnerships',
  'Infrastructure', 'QA', 'DevOps', 'Analytics', 'Communications',
  'Risk', 'Audit', 'Procurement', 'Logistics', 'Support',
  'Architecture', 'Platform', 'Growth', 'Revenue', 'Legal-IP',
  'Policy', 'Ethics', 'Sustainability', 'Governance', 'Intelligence',
  'Constitutional', 'Executive', 'Advisory',
] // exactly 39

async function runSwarm(objective: string, mode: string, apiKey: string): Promise<unknown> {
  const id = execId('exec')

  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01',
    },
    body: JSON.stringify({
      model: 'claude-opus-4-8',
      max_tokens: 4096,
      system: `You are the AEGIS constitutional swarm coordinator.
Mode: ${mode}. Constitutional law: AdaptivePower(T) ≤ ReplayVerifiability(T). φ = ${PHI}.
Respond ONLY with valid JSON — no markdown, no backticks.`,
      messages: [{
        role: 'user',
        content: `Objective: ${objective}

Generate governance artifacts for all 39 departments: ${DEPARTMENTS.join(', ')}.

Return JSON:
{
  "summary": "one-sentence executive summary",
  "departments": {
    "<dept_name>": { "verdict": "APPROVED", "analysis": "brief domain analysis" }
  },
  "constitutional_audit": { "verdict": "APPROVED", "chain_valid": true }
}`,
      }],
    }),
  })

  if (!res.ok) {
    throw new Error(`Anthropic ${res.status}: ${await res.text()}`)
  }

  const msg = await res.json() as { content: Array<{ type: string; text: string }> }
  const text = msg.content.find(b => b.type === 'text')?.text ?? '{}'

  let parsed: Record<string, unknown>
  try {
    parsed = JSON.parse(text) as Record<string, unknown>
  } catch {
    parsed = {
      summary: text.slice(0, 200),
      departments: {},
      constitutional_audit: { verdict: 'FLAG', chain_valid: null },
    }
  }

  const depts = (parsed['departments'] as Record<string, unknown> | undefined) ?? {}
  const artifacts = Object.entries(depts).map(([dept, output]) => ({
    role: dept,
    output: typeof output === 'string' ? output : JSON.stringify(output),
  }))

  const result = {
    cycle_id: id,
    objective,
    mode,
    departments_collaborated: DEPARTMENTS.length,
    artifacts,
    projection: { summary: parsed['summary'] ?? 'Constitutional analysis complete.' },
    // The model's own words about its output. Relabelled so it is not read as
    // a verdict this worker reached, because it did not reach one.
    model_reported_audit: parsed['constitutional_audit'] ?? null,
    // The edge runs no audit chain, so it cannot pronounce on validity.
    chain_valid: null,
    chain_evidence: 'not_available_at_edge',
    execution_id: id,
  }

  // A digest of exactly what is returned — recomputable by the caller from the
  // response body. Previously this field held a random string.
  return { ...result, response_digest: 'sha256:' + await sha256Hex(JSON.stringify(result)) }
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const { pathname, searchParams } = new URL(request.url)
    const method = request.method

    if (method === 'OPTIONS') {
      return new Response(null, { status: 204, headers: CORS })
    }

    // ── Health & telemetry endpoints (used by hub every 5 s) ─────────────────

    // These endpoints previously returned constants shaped like measurements:
    // `t0_verdict: true`, `corruption_count: 0`, `pgcs_passes: true` were
    // literals, not results. The worker has no filesystem and runs no gate, so
    // it cannot evaluate any of them. Each is now reported as unknown with the
    // reason, and `verified` states plainly that nothing was checked here. The
    // real gate is `sovereign-omega-v2/scripts/verify-hashes.mjs`, enforced in
    // CI; the edge must not impersonate its verdict.
    //
    // Root law: AdaptivePower(T) <= ReplayVerifiability(T). A constant that
    // reads as a verdict puts the claim above the evidence.

    if (pathname === '/health') {
      // Liveness only — this is the one thing answering the request proves.
      return ok({
        status: 'ok',
        version: '2.0.0',
        phi: PHI,
        layer: 'cloudflare-worker',
        verified: false,
        verification: 'no_gate_at_edge',
      })
    }

    if (pathname === '/node') {
      return ok({
        t0_verdict: null,
        corruption_count: null,
        phi_threshold: PHI,
        drift_risk: null,
        // Pinned into this build; the edge cannot recompute it against the
        // frozen files, so it is not evidence that the membrane is intact.
        constitutional_hash_pinned_at_build: CONSTITUTIONAL_HASH,
        verified: false,
        verification: 'no_gate_at_edge',
      })
    }

    if (pathname === '/telemetry') {
      return ok({
        sequence: seq(),
        epoch: Math.floor(Date.now() / 60_000),
        avg_vcg_error: null,
        drift_index: null,
        corruption_count: null,
        pgcs_passes: null,
        failsafe_state: 'UNKNOWN',
        gate_acceptance_rate: null,
        verified: false,
        verification: 'no_telemetry_source_at_edge',
      })
    }

    if (pathname === '/resonance') {
      return ok({
        is_resonant: null,
        is_certified: null,
        phi_convergent: null,
        resonance_depth: null,
        phi_headroom: null,
        verified: false,
        verification: 'no_resonance_source_at_edge',
      })
    }

    if (pathname === '/block') {
      // The edge keeps no chain, so it has no block to report. Reporting a
      // synthetic height with the build-time hash as `state_root` invented a
      // ledger that does not exist here.
      return err(
        'No chain state at the edge. Query the governance runtime.',
        'NO_CHAIN_AT_EDGE',
        501,
      )
    }

    // ── Platform endpoints ────────────────────────────────────────────────────

    if (pathname === '/platform/status') {
      return ok(envelope('status-' + seq(), {
        version: '2.0.0',
        chain_valid: null,
        chain_evidence: 'not_available_at_edge',
        total_agents: 39,
        available: true,
        contract_version: CONTRACT_VERSION,
        constitutional_hash_pinned_at_build: CONSTITUTIONAL_HASH,
      }))
    }

    if (pathname === '/platform/collaborate' && method === 'POST') {
      if (!env.ANTHROPIC_API_KEY) {
        return err('ANTHROPIC_API_KEY not configured', 'UNAUTHORIZED', 401)
      }
      if (!await authorizeInference(request, env)) {
        return err('Valid API key with an active entitlement and remaining quota required', 'ENTITLEMENT_REQUIRED', 403)
      }
      try {
        const body = await request.json() as { objective?: string; mode?: string }
        const result = await runSwarm(
          body.objective ?? 'Analyze governance objective',
          body.mode ?? 'analysis',
          env.ANTHROPIC_API_KEY,
        )
        return ok(envelope(execId('collab'), result))
      } catch (e) {
        return err(String(e), 'INTERNAL', 500)
      }
    }

    // ── Holon validation endpoint — external AI nodes submit constitutional verdicts ──
    //
    // Gemma-4E4B on iPhone POSTs here. We compute a SHA-256 chain entry hash
    // from the verdict + bio_state and return it in the constitutional envelope.
    // The hash is the tamper-evident record of this holon's participation.

    if (pathname === '/platform/holon/validate' && method === 'POST') {
      try {
        const body = await request.json() as {
          holon_id?: string
          verdict?: string
          confidence?: number
          reason_code?: string
          bio_state?: { stress?: number; attention?: number; rr?: number; atp?: number }
        }

        const verdict = body.verdict
        if (verdict !== 'APPROVED' && verdict !== 'FAILED') {
          return err('verdict must be APPROVED or FAILED', 'INVALID_INPUT', 400)
        }

        const holonId = body.holon_id ?? 'gemma-4e4b-iphone'
        const confidence = typeof body.confidence === 'number'
          ? Math.max(0, Math.min(1, body.confidence))
          : 0.5
        const reasonCode = body.reason_code ?? 'NOMINAL'
        const bioState = body.bio_state ?? {}

        const ts = new Date().toISOString()
        const entryData = JSON.stringify({
          holon_id: holonId, verdict, confidence, reason_code: reasonCode,
          bio_state: bioState, timestamp: ts,
        })
        const hashBuffer = await crypto.subtle.digest(
          'SHA-256', new TextEncoder().encode(entryData)
        )
        const entryHash = Array.from(new Uint8Array(hashBuffer))
          .map(b => b.toString(16).padStart(2, '0')).join('')

        const constitutionalVerdict = verdict === 'APPROVED' ? 'APPROVED' : 'FLAG'

        return ok(envelope(execId('holon'), {
          holon_id: holonId,
          verdict,
          confidence,
          reason_code: reasonCode,
          bio_state: bioState,
          timestamp: ts,
          chain_entry_hash: entryHash,
          chain_valid: null,
          chain_evidence: 'not_available_at_edge',
          constitutional_audit: {
            verdict: constitutionalVerdict,
            holon_class: 'GEMMA-4E4B',
            tier: 'T2',
            phi_threshold: PHI,
          },
        }))
      } catch (e) {
        return err(String(e), 'INTERNAL', 500)
      }
    }

    if (pathname === '/platform/holon/status' && method === 'GET') {
      return ok(envelope('holon-status-' + seq(), {
        endpoint: '/platform/holon/validate',
        method: 'POST',
        schema: {
          holon_id: 'string — e.g. gemma-4e4b-iphone',
          verdict: 'APPROVED | FAILED',
          confidence: 'float 0–1',
          reason_code: 'string',
          bio_state: { stress: 'float', attention: 'float', rr: 'float', atp: 'float' },
        },
        registered_holons: ['gemma-4e4b-iphone'],
        constitutional_law: 'AdaptivePower(T) ≤ ReplayVerifiability(T)',
      }))
    }

    // Async execution stub — returns immediately with a pending execution
    if (pathname === '/platform/executions' && method === 'POST') {
      const id = execId('exec')
      return ok(envelope(id, {
        execution_id: id,
        stream_url: `/platform/executions/live?id=${id}`,
        status: 'pending',
      }))
    }

    // ── Fall through to WebGPU static assets ─────────────────────────────────
    return env.ASSETS.fetch(request)
  },
}
