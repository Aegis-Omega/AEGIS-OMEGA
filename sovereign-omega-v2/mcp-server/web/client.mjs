/** Real JSON-RPC MCP client. Browser-native fetch; no model, SDK impersonation, or fabricated replies. */
const MAX_RESPONSE = 2 * 1024 * 1024
const SUPPORTED = ['2025-11-25', '2025-06-18', '2025-03-26']

function correlated(message, id) {
  if (!message || message.jsonrpc !== '2.0' || message.id !== id ||
      (Object.hasOwn(message, 'result') === Object.hasOwn(message, 'error'))) {
    throw new Error('Invalid or uncorrelated JSON-RPC response id')
  }
  return message
}

export async function readRpcResponse(response, id) {
  const mime = (response.headers.get('content-type') ?? '').split(';')[0].trim()
  if (!['application/json', 'text/event-stream'].includes(mime)) throw new Error('Unsupported MCP response media type')
  const reader = response.body?.getReader()
  if (!reader) throw new Error('Missing MCP response body')
  const decoder = new TextDecoder('utf-8', { fatal: true })
  let buffer = '', bytes = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      bytes += value.byteLength
      if (bytes > MAX_RESPONSE) throw new Error('MCP response exceeds bounded client buffer')
      buffer += decoder.decode(value, { stream: true })
      if (mime === 'text/event-stream') {
        let boundary
        while ((boundary = /\r?\n\r?\n/.exec(buffer))) {
          const frame = buffer.slice(0, boundary.index)
          buffer = buffer.slice(boundary.index + boundary[0].length)
          const data = frame.split(/\r?\n/).filter(line => line.startsWith('data:'))
            .map(line => line.slice(5).replace(/^ /, '')).join('\n')
          if (!data) continue
          const message = JSON.parse(data)
          if (Object.hasOwn(message, 'id')) return correlated(message, id)
          if (message.jsonrpc !== '2.0' || typeof message.method !== 'string') throw new Error('Invalid SSE notification')
        }
      }
    }
    buffer += decoder.decode()
    if (mime === 'application/json') return correlated(JSON.parse(buffer), id)
    throw new Error('SSE ended without a correlated JSON-RPC response')
  } finally { await reader.cancel().catch(() => {}); reader.releaseLock() }
}

export class BrowserMcpClient {
  #endpoint; #token; #fetch; #session; #version; #ready = false; #id = 0; #timeout
  trace = []
  constructor({ endpoint, localToken, fetchImpl = globalThis.fetch.bind(globalThis), timeoutMs = 10_000 }) {
    const url = new URL(endpoint)
    if (url.protocol !== 'http:' || !['127.0.0.1', 'localhost'].includes(url.hostname) ||
        url.pathname !== '/mcp' || url.username || url.password || url.search || url.hash) {
      throw new Error('This simulator only connects to its local MCP endpoint')
    }
    if (typeof localToken !== 'string' || !localToken) throw new Error('Local transport credential is required')
    this.#endpoint = url.href; this.#token = localToken; this.#fetch = fetchImpl; this.#timeout = timeoutMs
  }
  async #send(method, params, notification = false) {
    const request = { jsonrpc: '2.0', ...(notification ? {} : { id: ++this.#id }), method, ...(params === undefined ? {} : { params }) }
    const headers = { 'Content-Type': 'application/json', Accept: 'application/json, text/event-stream',
      'X-Aegis-Local-Client': this.#token }
    if (this.#session) headers['Mcp-Session-Id'] = this.#session
    if (this.#version) headers['MCP-Protocol-Version'] = this.#version
    const entry = { sequence: this.trace.length + 1, observed_at: new Date().toISOString(), method,
      request, request_headers: { accept: headers.Accept, session_present: Boolean(this.#session),
        protocol_version: this.#version ?? null }, status: null, response: null }
    this.trace.push(entry)
    try {
      const response = await this.#fetch(this.#endpoint, { method: 'POST', headers,
        body: JSON.stringify(request), signal: AbortSignal.timeout(this.#timeout), cache: 'no-store', redirect: 'error' })
      entry.status = response.status
      if (!response.ok) {
        if (response.status === 404) { this.#session = undefined; this.#ready = false }
        throw new Error(`MCP HTTP ${response.status}`)
      }
      if (notification) {
        if (response.status !== 202 || (await response.text()) !== '') throw new Error('Invalid MCP notification acknowledgment')
        return undefined
      }
      const message = await readRpcResponse(response, request.id)
      entry.response = message
      if (message.error) throw new Error(`MCP error ${message.error.code}: ${message.error.message}`)
      if (method === 'initialize') {
        this.#session = response.headers.get('mcp-session-id') ?? undefined
        if (!this.#session || !SUPPORTED.includes(message.result?.protocolVersion)) throw new Error('Invalid MCP initialization result')
        this.#version = message.result.protocolVersion
      }
      return message.result
    } catch (error) {
      entry.client_error = error instanceof Error ? error.message : String(error)
      throw error
    }
  }
  async initialize() {
    if (this.#session || this.#ready) throw new Error('Client already initialized')
    const result = await this.#send('initialize', { protocolVersion: '2025-11-25', capabilities: {},
      clientInfo: { name: 'aegis-alexa-lane-web-simulator', version: '1.0.0' } })
    await this.#send('notifications/initialized', undefined, true)
    this.#ready = true
    return result
  }
  async listTools() {
    if (!this.#ready) throw new Error('Client must be initialized')
    return this.#send('tools/list', {})
  }
  async callTool(name, args = {}) {
    if (!this.#ready) throw new Error('Client must be initialized')
    return this.#send('tools/call', { name, arguments: args })
  }
  async close() {
    const session = this.#session
    this.#session = undefined; this.#ready = false
    if (!session) return
    const response = await this.#fetch(this.#endpoint, { method: 'DELETE', headers: {
      'X-Aegis-Local-Client': this.#token, 'Mcp-Session-Id': session, 'MCP-Protocol-Version': this.#version,
    }, signal: AbortSignal.timeout(this.#timeout), redirect: 'error' })
    if (!response.ok && response.status !== 404) throw new Error(`MCP session cleanup HTTP ${response.status}`)
  }
}

export async function sha256(text) {
  const digest = await globalThis.crypto.subtle.digest('SHA-256', new TextEncoder().encode(text))
  return [...new Uint8Array(digest)].map(byte => byte.toString(16).padStart(2, '0')).join('')
}

export async function validateDemoTrace(trace) {
  const fail = reason => { throw new Error(`Unverified demo: ${reason}`) }
  const methods = ['initialize', 'notifications/initialized', 'tools/list', 'tools/call', 'tools/call']
  if (!Array.isArray(trace) || trace.length !== methods.length) fail('incomplete or unexpected trace')
  for (let i = 0; i < methods.length; i++) {
    const event = trace[i]
    if (event.method !== methods[i] || event.request?.method !== methods[i] || event.client_error) fail('invalid method order')
    if (i === 1) {
      if (event.status !== 202 || event.response !== null) fail('initialized notification was not acknowledged')
    } else {
      if (event.status !== 200) fail('unsuccessful HTTP exchange')
      correlated(event.response, event.request.id)
      if (event.response.error) fail('JSON-RPC error is not successful tool evidence')
    }
  }
  const version = trace[0].response.result?.protocolVersion
  if (!SUPPORTED.includes(version)) fail('unsupported protocol version')
  for (const event of trace.slice(1)) {
    if (!event.request_headers?.session_present || event.request_headers.protocol_version !== version) fail('missing negotiated session or protocol header')
  }
  const tools = trace[2].response.result?.tools
  if (!Array.isArray(tools) || !['aegis_authority_policy', 'aegis_governed_claude_call'].every(name => tools.some(tool => tool.name === name))) fail('required tools missing')
  const unpack = event => {
    const text = event.response.result?.content?.find(item => item.type === 'text')?.text
    if (typeof text !== 'string') fail('tool content missing')
    return JSON.parse(text)
  }
  if (trace[3].request.params.name !== 'aegis_authority_policy' || trace[3].response.result.isError === true) fail('read-only policy call failed')
  const policy = unpack(trace[3])
  if (policy.source?.path !== 'harness/policies/consequence-policy.v1.json' || typeof policy.policy_json !== 'string' ||
      policy.source.sha256 !== await sha256(policy.policy_json) ||
      JSON.stringify(policy.policy) !== JSON.stringify(JSON.parse(policy.policy_json)) ||
      policy.policy?.classes?.D3?.approval !== 'EXPLICIT' || policy.authority_effect !== 'NONE' || policy.external_effect !== 'NONE') fail('policy bytes, sha256 or authority metadata mismatch')
  const denied = unpack(trace[4])
  if (trace[4].request.params.name !== 'aegis_governed_claude_call' || trace[4].response.result.isError !== true ||
      denied.authority?.outcome !== 'DENIED' || denied.external_effect !== 'NOT_EXECUTED' ||
      !denied.authority.denial_codes?.includes('IDENTITY_UNAVAILABLE')) fail('consequential call was not denied at the unbound-identity gate')
  return { verdict: 'PASS', profile: 'LOCAL_MCP_PROTOCOL_AND_AUTHORITY_BOUNDARY', protocol_version: version,
    policy_sha256: policy.source.sha256, authority_outcome: 'DENIED', external_effect: 'NOT_EXECUTED',
    authority_effect: 'NONE', scope: 'Five actual local HTTP exchanges; not Alexa runtime, model execution, or repository admission.' }
}
