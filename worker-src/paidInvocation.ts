/**
 * AEGIS Ω paid collaboration transport, dependency-injected for safe replay.
 * No fallback to a model, mocked agent output, or 'successful' empty result.
 * Authorization and atomic quota reservation MUST precede `provider`.
 */

export interface PaidInvocationEnv {
  ANTHROPIC_API_KEY?: string
  SUPABASE_URL?: string
  SUPABASE_SERVICE_ROLE_KEY?: string
}
export interface PaidInvocationAdmission {
  admitted: boolean
  status?: number
  code?: string
}
export interface PaidInvocationDeps {
  originAllowed(origin: string | null): boolean
  cors(origin: string | null): Record<string, string>
  reserve(request: Request, env: PaidInvocationEnv): Promise<PaidInvocationAdmission>
  provider(objective: string, mode: string, key: string): Promise<unknown>
  envelope(id: string, data: unknown): unknown
  id(prefix: string): string
}

export async function handlePaidInvocation(request: Request, env: PaidInvocationEnv, deps: PaidInvocationDeps): Promise<Response> {
  const origin = request.headers.get('origin')
  const reply = (message: string, code: string, status: number) =>
    new Response(JSON.stringify({ error: message, code }), {
      status,
      headers: { 'Content-Type': 'application/json', ...deps.cors(origin) },
    })
  if (!deps.originAllowed(origin)) {
    return reply('Browser origin is not authorized for paid calls', 'ORIGIN_FORBIDDEN', 403)
  }
  if (!env.ANTHROPIC_API_KEY) {
    return reply('Provider execution is not configured', 'PROVIDER_UNAVAILABLE', 503)
  }
  if (!(request.headers.get('content-type') ?? '').toLowerCase().includes('application/json')) {
    return reply('JSON body required', 'INVALID_CONTENT_TYPE', 415)
  }
  const declared = Number(request.headers.get('content-length') ?? 0)
  if (!Number.isFinite(declared) || declared < 0 || declared > 4096) {
    return reply('Request body exceeds limit', 'BODY_TOO_LARGE', 413)
  }
  const reader = request.body?.getReader()
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    if (reader) {
      for (;;) {
        const chunk = await reader.read()
        if (chunk.done) break
        size += chunk.value.byteLength
        if (size > 4096) {
          await reader.cancel()
          return reply('Request body exceeds limit', 'BODY_TOO_LARGE', 413)
        }
        chunks.push(chunk.value)
      }
    }
  } catch {
    return reply('Unable to read request body', 'INVALID_REQUEST_BODY', 400)
  }
  const bytes = new Uint8Array(size)
  let offset = 0
  for (const part of chunks) { bytes.set(part, offset); offset += part.byteLength }
  let body: unknown
  try {
    body = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
  } catch {
    return reply('Malformed JSON payload', 'INVALID_JSON', 400)
  }
  if (!body || typeof body !== 'object' || Array.isArray(body)) {
    return reply('JSON object required', 'INVALID_REQUEST', 400)
  }
  const input = body as Record<string, unknown>
  const objective = typeof input.objective === 'string' ? input.objective.trim() : ''
  const modes = ['analysis', 'revenue', 'gtm', 'retention']
  if (!objective || objective.length > 700 || (typeof input.mode !== 'string' || !modes.includes(input.mode))) {
    return reply('Objective and supported mode required', 'INVALID_REQUEST', 400)
  }
  if (input.live !== true) {
    // No demo implementation exists in this Worker. Never make a paid model
    // call for a request that explicitly asks for a demo or omits live=true.
    return reply('Worker demo execution is not implemented; no provider call was made', 'DEMO_NOT_IMPLEMENTED', 501)
  }
  const admission = await deps.reserve(request, env)
  if (!admission.admitted) {
    return reply('Invocation denied by authorization or quota gate', admission.code || 'AUTH_DENIED', admission.status || 503)
  }
  // Paid reservation has already happened. A provider failure must remain visible.
  try {
    const result = await deps.provider(objective, input.mode as string, env.ANTHROPIC_API_KEY)
    return new Response(JSON.stringify(deps.envelope(deps.id('collab'), result)), {
      headers: { 'Content-Type': 'application/json', ...deps.cors(origin) },
    })
  } catch {
    return reply('Provider call failed after quota reservation; investigate receipt', 'PROVIDER_FAILED', 502)
  }
}