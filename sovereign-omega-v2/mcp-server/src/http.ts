#!/usr/bin/env node
/** Local-only Streamable HTTP. No caller identity mapping and no ambient authority inheritance. */
import { createServer, type IncomingMessage, type ServerResponse } from 'node:http'
import { randomBytes, randomUUID, timingSafeEqual } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js'
import { InitializeRequestSchema, InitializedNotificationSchema, LATEST_PROTOCOL_VERSION,
  SUPPORTED_PROTOCOL_VERSIONS } from '@modelcontextprotocol/sdk/types.js'
import { createAegisServer } from './index.js'

const MAX_BODY = 65_536
const ASSETS: Record<string, [string, string]> = {
  '/': ['index.html', 'text/html; charset=utf-8'],
  '/index.html': ['index.html', 'text/html; charset=utf-8'],
  '/client.mjs': ['client.mjs', 'text/javascript; charset=utf-8'],
  '/app.mjs': ['app.mjs', 'text/javascript; charset=utf-8'],
  '/style.css': ['style.css', 'text/css; charset=utf-8'],
}
const CSP = "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; img-src 'self' data:; base-uri 'none'; frame-ancestors 'none'; form-action 'none'"
type Session = { mcp: ReturnType<typeof createAegisServer>; transport: StreamableHTTPServerTransport;
  ready: boolean; version: string; lastSeen: number }

function error(res: ServerResponse, status: number, message: string): void {
  res.writeHead(status, { 'Content-Type': 'application/json' })
  res.end(JSON.stringify({ jsonrpc: '2.0', error: { code: -32000, message }, id: null }))
}

export async function startHttpServer(options: { port?: number; maxSessions?: number; sessionTtlMs?: number } = {}) {
  const port = options.port ?? 7891
  const maxSessions = options.maxSessions ?? 16
  const sessionTtlMs = options.sessionTtlMs ?? 300_000
  if (!Number.isInteger(port) || port < 0 || port > 65_535 || !Number.isInteger(maxSessions) ||
      maxSessions < 1 || maxSessions > 64 || !Number.isFinite(sessionTtlMs) || sessionTtlMs <= 0) {
    throw new Error('INVALID_LOCAL_HTTP_CONFIGURATION')
  }
  const token = randomBytes(32).toString('hex')
  const sessions = new Map<string, Session>()
  let origin = ''
  let listeningPort = 0
  let closing = false
  async function dispose(id: string) {
    const session = sessions.get(id)
    sessions.delete(id)
    await session?.mcp.close().catch(() => {})
  }
  async function handle(req: IncomingMessage, res: ServerResponse): Promise<void> {
    res.setHeader('Cache-Control', 'no-store')
    res.setHeader('X-Content-Type-Options', 'nosniff')
    res.setHeader('Referrer-Policy', 'no-referrer')
    res.setHeader('Content-Security-Policy', CSP)
    const host = req.headers.host
    if (closing) { error(res, 503, 'SERVER_CLOSING'); return }
    if (host !== `127.0.0.1:${listeningPort}` && host !== `localhost:${listeningPort}`) {
      error(res, 403, 'HOST_NOT_ALLOWED'); return
    }
    if ((req.headers.origin !== undefined && req.headers.origin !== `http://${host}`) ||
        req.headers['sec-fetch-site'] === 'cross-site') {
      error(res, 403, 'ORIGIN_NOT_ALLOWED'); return
    }
    const path = new URL(req.url ?? '/', origin).pathname
    if (path === '/bootstrap' && req.method === 'GET') {
      res.writeHead(200, { 'Content-Type': 'application/json' })
      res.end(JSON.stringify({ localToken: token, authorityBinding: 'UNBOUND', transport: 'Streamable HTTP',
        notice: 'Local transport token only. No execution identity, approval, AWS, or Alexa runtime.' }))
      return
    }
    if (ASSETS[path] && req.method === 'GET') {
      const [file, mime] = ASSETS[path]
      res.writeHead(200, { 'Content-Type': mime })
      res.end(readFileSync(new URL(`../web/${file}`, import.meta.url)))
      return
    }
    if (path !== '/mcp') { error(res, 404, 'NOT_FOUND'); return }
    const supplied = req.headers['x-aegis-local-client']
    if (typeof supplied !== 'string' || Buffer.byteLength(supplied) !== Buffer.byteLength(token) ||
        !timingSafeEqual(Buffer.from(supplied), Buffer.from(token))) {
      error(res, 401, 'LOCAL_TRANSPORT_CREDENTIAL_REQUIRED'); return
    }
    for (const [id, session] of sessions) if (Date.now() - session.lastSeen > sessionTtlMs) await dispose(id)
    if (!['POST', 'GET', 'DELETE'].includes(req.method ?? '')) {
      res.setHeader('Allow', 'POST, GET, DELETE'); error(res, 405, 'METHOD_NOT_ALLOWED'); return
    }
    const id = req.headers['mcp-session-id']
    if (id !== undefined && (typeof id !== 'string' || !sessions.has(id))) {
      error(res, 404, 'SESSION_NOT_FOUND'); return
    }
    const existing = typeof id === 'string' ? sessions.get(id) : undefined
    if (existing) {
      if (req.headers['mcp-protocol-version'] !== existing.version) {
        error(res, 400, 'NEGOTIATED_PROTOCOL_VERSION_REQUIRED'); return
      }
      existing.lastSeen = Date.now()
    }
    if (req.method !== 'POST') {
      if (!existing || typeof id !== 'string') { error(res, 400, 'INITIALIZE_REQUIRED'); return }
      if (req.method === 'GET') {
        res.setHeader('Allow', 'POST, DELETE'); error(res, 405, 'OPTIONAL_SSE_STREAM_NOT_OFFERED'); return
      }
      await dispose(id); res.writeHead(200).end(); return
    }
    if (req.headers['content-type']?.split(';')[0].trim().toLowerCase() !== 'application/json') {
      error(res, 415, 'APPLICATION_JSON_REQUIRED'); return
    }
    const declared = req.headers['content-length']
    if (declared !== undefined && Number(declared) > MAX_BODY) { error(res, 413, 'BODY_TOO_LARGE'); return }
    const chunks: Buffer[] = []
    let size = 0
    for await (const chunk of req) {
      const bytes = Buffer.isBuffer(chunk) ? chunk : Buffer.from(chunk)
      size += bytes.length
      if (size > MAX_BODY) { error(res, 413, 'BODY_TOO_LARGE'); return }
      chunks.push(bytes)
    }
    let body: unknown
    try { body = JSON.parse(Buffer.concat(chunks).toString('utf8')) }
    catch { error(res, 400, 'MALFORMED_JSON'); return }
    if (existing) {
      if (InitializeRequestSchema.safeParse(body).success) { error(res, 400, 'ALREADY_INITIALIZED'); return }
      const initialized = InitializedNotificationSchema.safeParse(body).success
      if (!existing.ready && !initialized) { error(res, 400, 'INITIALIZED_NOTIFICATION_REQUIRED'); return }
      if (initialized) existing.ready = true
      await existing.transport.handleRequest(req, res, body)
      return
    }
    const initialize = InitializeRequestSchema.safeParse(body)
    if (!initialize.success) { error(res, 400, 'VALID_INITIALIZE_REQUIRED'); return }
    if (sessions.size >= maxSessions) { error(res, 429, 'SESSION_LIMIT_REACHED'); return }
    const newId = randomUUID()
    const transport = new StreamableHTTPServerTransport({ sessionIdGenerator: () => newId, enableJsonResponse: true })
    // Never map an HTTP caller to the launching operator's process identity or approval.
    const mcp = createAegisServer({ authorityBinding: 'unbound-http' })
    const version = initialize.data.params.protocolVersion
    const entry: Session = { mcp, transport, ready: false, lastSeen: Date.now(),
      version: SUPPORTED_PROTOCOL_VERSIONS.includes(version) ? version : LATEST_PROTOCOL_VERSION }
    sessions.set(newId, entry) // Reserve capacity before the first await.
    try {
      await mcp.connect(transport)
      const previousClose = transport.onclose
      transport.onclose = () => { previousClose?.(); sessions.delete(newId) }
      await transport.handleRequest(req, res, body)
      if (res.statusCode >= 400 || !transport.sessionId) await dispose(newId)
    } catch (err) { await dispose(newId); throw err }
  }
  const http = createServer((req, res) => {
    handle(req, res).catch(() => {
      if (!res.headersSent) error(res, 500, 'LOCAL_TRANSPORT_FAILURE')
      else if (!res.writableEnded) res.end()
    })
  })
  http.headersTimeout = 5_000
  http.requestTimeout = 10_000
  http.keepAliveTimeout = 1_000
  await new Promise<void>((resolveListen, reject) => {
    http.once('error', reject)
    http.listen(port, '127.0.0.1', () => { http.off('error', reject); resolveListen() })
  })
  const address = http.address()
  if (!address || typeof address === 'string') throw new Error('LOCAL_LISTENER_UNAVAILABLE')
  listeningPort = address.port
  origin = `http://127.0.0.1:${listeningPort}`
  return { origin, async close() {
    closing = true
    await Promise.all([...sessions.keys()].map(dispose))
    http.closeAllConnections()
    await new Promise<void>((done, reject) => http.close(err => err ? reject(err) : done()))
  } }
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  const app = await startHttpServer({ port: Number(process.env['AEGIS_MCP_HTTP_PORT'] ?? '7891') })
  console.error(`AEGIS local MCP simulator: ${app.origin} — authority UNBOUND; no AWS or Alexa runtime`)
  for (const signal of ['SIGINT', 'SIGTERM'] as const) process.once(signal, () => { void app.close().then(() => process.exit(0)) })
}
