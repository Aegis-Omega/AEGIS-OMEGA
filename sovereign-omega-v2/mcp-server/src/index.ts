#!/usr/bin/env node
/**
 * AEGIS Constitutional Agent Swarm — MCP Server
 * Exposes the 39-department governed swarm and constitutional health layer
 * as Model Context Protocol tools callable from any Claude instance.
 *
 * EPISTEMIC TIER: T2
 *
 * Env vars:
 *   AEGIS_BRIDGE_URL  — bridge base URL (default: http://localhost:7890)
 *   AEGIS_API_KEY     — operator API key (required for /platform/* endpoints)
 */

import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { z } from 'zod'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const BRIDGE = (process.env['AEGIS_BRIDGE_URL'] ?? 'http://localhost:7890').replace(/\/$/, '')
const API_KEY = process.env['AEGIS_API_KEY'] ?? ''

const server = new McpServer({
  name: 'aegis-constitutional-swarm',
  version: '0.1.0',
})

// ── helpers ──────────────────────────────────────────────────────────────────

async function bridgeGet(path: string, apiKey = false): Promise<unknown> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey && API_KEY) headers['X-API-Key'] = API_KEY
  const res = await fetch(`${BRIDGE}${path}`, { headers })
  if (!res.ok) throw new Error(`Bridge ${path} → HTTP ${res.status}`)
  return res.json()
}

async function bridgePost(path: string, body: unknown, apiKey = false): Promise<unknown> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey && API_KEY) headers['X-API-Key'] = API_KEY
  const res = await fetch(`${BRIDGE}${path}`, {
    method: 'POST',
    headers,
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const err = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(`Bridge ${path} → ${err}`)
  }
  return res.json()
}

function text(content: unknown): { content: Array<{ type: 'text'; text: string }> } {
  return { content: [{ type: 'text', text: JSON.stringify(content, null, 2) }] }
}

// ── tools ─────────────────────────────────────────────────────────────────────

server.tool(
  'aegis_health',
  'Check AEGIS constitutional health: t0_verdict, corruption_count, hash chain status.',
  {},
  async () => {
    const [health, node] = await Promise.all([
      bridgeGet('/health'),
      bridgeGet('/node'),
    ])
    const ok = (node as Record<string, unknown>)['t0_verdict'] === true &&
               (node as Record<string, unknown>)['corruption_count'] === 0
    return text({ constitutional_health: ok ? 'PASS' : 'FAIL', health, node })
  },
)

server.tool(
  'aegis_telemetry',
  'Get live AEGIS telemetry: PGCS passes, epoch count, VCG metrics, martingale state.',
  {},
  async () => {
    const telemetry = await bridgeGet('/telemetry')
    return text(telemetry)
  },
)

server.tool(
  'aegis_platform_status',
  'Get AEGIS platform status: version, uptime, agent availability, contract version.',
  {},
  async () => {
    const status = await bridgeGet('/platform/status', true)
    return text(status)
  },
)

server.tool(
  'aegis_collaborate',
  [
    'Run the AEGIS 39-department constitutional agent swarm on a governance objective.',
    'Each department (Finance, Legal, Engineering, Marketing, …) produces a domain-specific output.',
    'The swarm applies a constitutional audit (APPROVED / FLAG / QUARANTINE) to each output.',
    'Returns: cycle_id, artifacts from all 39 departments, constitutional verdict, audit_chain_hash.',
    'Requires AEGIS_API_KEY to be set.',
  ].join(' '),
  {
    objective: z.string().min(10).describe(
      'The governance objective for the swarm (e.g. "Enter EU fintech market Q4 2026")',
    ),
    mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis').describe(
      'Swarm operating mode',
    ),
  },
  async ({ objective, mode }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set — cannot call /platform/collaborate' })
    const result = await bridgePost('/platform/collaborate', { objective, mode, live: false }, true)
    return text(result)
  },
)

server.tool(
  'aegis_start_execution',
  [
    'Start an async AEGIS swarm execution. Returns an execution_id and stream_url immediately.',
    'Use aegis_get_execution to poll for the result. Requires AEGIS_API_KEY.',
  ].join(' '),
  {
    objective: z.string().min(10).describe('Governance objective for the swarm'),
    mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis'),
  },
  async ({ objective, mode }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set' })
    const result = await bridgePost('/platform/executions', { objective, mode, live: false }, true)
    return text(result)
  },
)

server.tool(
  'aegis_get_execution',
  'Fetch the result of an async AEGIS swarm execution by execution_id. Requires AEGIS_API_KEY.',
  {
    execution_id: z.string().describe('execution_id returned by aegis_start_execution'),
  },
  async ({ execution_id }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set' })
    const result = await bridgeGet(`/platform/executions/${execution_id}`, true)
    return text(result)
  },
)

server.tool(
  'aegis_governed_claude_call',
  [
    'Send a prompt through the AEGIS constitutional governance layer to Claude.',
    'The call is hash-chained, audit-logged, and returns a constitutional verdict alongside the response.',
    'This is the tamper-evident governed path — not a raw /v1/messages call.',
  ].join(' '),
  {
    prompt: z.string().min(1).describe('Prompt to send through the AEGIS governance layer'),
    system: z.string().optional().describe('Optional system prompt'),
  },
  async ({ prompt, system }) => {
    const body: Record<string, unknown> = { prompt }
    if (system) body['system'] = system
    const result = await bridgePost('/claude', body)
    return text(result)
  },
)

// ── resources (read-only, fuel-free — NO API key required) ─────────────────────
//
// MCP Resources expose AEGIS ground truth to any MCP client with zero fuel.
// Live resources call the key-free bridge endpoints; authority resources read
// repo files from disk. Every handler degrades gracefully if the source is
// unavailable — it returns { unavailable: true, reason } rather than throwing,
// so a resource read NEVER requires a key and NEVER hard-fails.

/** JSON resource content for a given uri. */
function jsonResource(uri: URL, value: unknown): { contents: Array<{ uri: string; mimeType: string; text: string }> } {
  return { contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify(value, null, 2) }] }
}

/** Fetch a key-free bridge endpoint, degrading to an unavailable envelope on failure. */
async function bridgeResource(uri: URL, path: string): Promise<{ contents: Array<{ uri: string; mimeType: string; text: string }> }> {
  try {
    return jsonResource(uri, await bridgeGet(path))
  } catch (err) {
    return jsonResource(uri, { unavailable: true, reason: err instanceof Error ? err.message : String(err) })
  }
}

/** Repo root — walk up from this module until a dir containing INDEX.md is found. */
function repoRoot(): string {
  let dir = dirname(fileURLToPath(import.meta.url)) // …/mcp-server/dist
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(dir, 'INDEX.md'))) return dir
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return process.cwd()
}

/** Read a repo authority file as a text resource, degrading gracefully. */
function fileResource(uri: URL, relPath: string): { contents: Array<{ uri: string; mimeType: string; text: string }> } {
  try {
    const full = join(repoRoot(), relPath)
    const md = readFileSync(full, 'utf8')
    return { contents: [{ uri: uri.href, mimeType: 'text/markdown', text: md }] }
  } catch (err) {
    return jsonResource(uri, { unavailable: true, reason: err instanceof Error ? err.message : String(err) })
  }
}

server.resource(
  'aegis-node',
  'aegis://node',
  { description: 'Live constitutional node state (bridge GET /node): t0_verdict, corruption_count, constitutional_hash, phi_threshold. Fuel-free.', mimeType: 'application/json' },
  async (uri) => bridgeResource(uri, '/node'),
)

server.resource(
  'aegis-telemetry',
  'aegis://telemetry',
  { description: 'Live AEGIS telemetry (bridge GET /telemetry): PGCS/VCG/epoch metrics. Fuel-free.', mimeType: 'application/json' },
  async (uri) => bridgeResource(uri, '/telemetry'),
)

server.resource(
  'aegis-health',
  'aegis://health',
  { description: 'AEGIS bridge liveness (bridge GET /health). Fuel-free.', mimeType: 'application/json' },
  async (uri) => bridgeResource(uri, '/health'),
)

server.resource(
  'aegis-authority-index',
  'aegis://authority/index',
  { description: 'INDEX.md — the machine-readable repository authority graph. Fuel-free.', mimeType: 'text/markdown' },
  async (uri) => fileResource(uri, 'INDEX.md'),
)

server.resource(
  'aegis-authority-repo-map',
  'aegis://authority/repo-map',
  { description: 'REPO_MAP.md — index of what is WIRED vs TESTED-ONLY/DORMANT/BROKEN/DEAD. Fuel-free.', mimeType: 'text/markdown' },
  async (uri) => fileResource(uri, 'REPO_MAP.md'),
)

// ── run ───────────────────────────────────────────────────────────────────────

const transport = new StdioServerTransport()
await server.connect(transport)
