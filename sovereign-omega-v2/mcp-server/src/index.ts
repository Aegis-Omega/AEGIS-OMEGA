#!/usr/bin/env node
/**
 * AEGIS Constitutional Agent Swarm — MCP Server
 * Consequential tools are gated through the single Automaton-3 evaluator.
 * Read-only resources remain fuel-free and key-free.
 */
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js'
import { z } from 'zod'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'

const BRIDGE = (process.env['AEGIS_BRIDGE_URL'] ?? 'http://localhost:7890').replace(/\/$/, '')
const API_KEY = process.env['AEGIS_API_KEY'] ?? ''

const server = new McpServer({ name: 'aegis-constitutional-swarm', version: '0.2.0' })

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
  const res = await fetch(`${BRIDGE}${path}`, { method: 'POST', headers, body: JSON.stringify(body) })
  if (!res.ok) {
    const err = await res.text().catch(() => `HTTP ${res.status}`)
    throw new Error(`Bridge ${path} → ${err}`)
  }
  return res.json()
}

function text(content: unknown): { content: Array<{ type: 'text'; text: string }> } {
  return { content: [{ type: 'text', text: JSON.stringify(content, null, 2) }] }
}

function repoRoot(): string {
  let dir = dirname(fileURLToPath(import.meta.url))
  for (let i = 0; i < 8; i++) {
    if (existsSync(join(dir, 'INDEX.md'))) return dir
    const parent = dirname(dir)
    if (parent === dir) break
    dir = parent
  }
  return process.cwd()
}

type AuthorityDecision = {
  outcome: 'ADMITTED' | 'DENIED'
  denial_codes?: string[]
  mutation_receipt_root?: string
  policy_decision?: { decision_root?: string }
  [key: string]: unknown
}

function localDenial(code: string): AuthorityDecision {
  return { outcome: 'DENIED', denial_codes: [code] }
}

function authorizeAction(input: {
  actionClass: 'D0' | 'D1' | 'D2' | 'D3' | 'D4'
  authorityDomain: string
  requestedCapability: string
  tool: string
  target: string
  action: Record<string, unknown>
  idempotencyKey?: string
  compensationReference?: string
}): AuthorityDecision {
  const identityRaw = process.env['AEGIS_EXECUTION_IDENTITY_JSON']
  if (!identityRaw) return localDenial('IDENTITY_UNAVAILABLE')
  let identity: unknown
  let workspace: unknown = {}
  let approval: unknown
  try {
    identity = JSON.parse(identityRaw)
    workspace = JSON.parse(process.env['AEGIS_WORKSPACE_OBSERVATION_JSON'] ?? '{}')
    const approvalRaw = process.env['AEGIS_APPROVAL_GRANT_JSON']
    approval = approvalRaw ? JSON.parse(approvalRaw) : undefined
  } catch {
    return localDenial('AUTHORITY_ENVIRONMENT_MALFORMED')
  }
  const payload = {
    identity,
    workspace,
    approval,
    action: input.action,
    request: {
      action_class: input.actionClass,
      authority_domain: input.authorityDomain,
      requested_capability: input.requestedCapability,
      tool: input.tool,
      target: input.target,
      current_generation: Number(process.env['AEGIS_LEASE_GENERATION'] ?? '0'),
      idempotency_key: input.idempotencyKey ?? 'NONE',
      compensation_reference: input.compensationReference ?? 'NONE',
    },
  }
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const script = join(repoRoot(), 'scripts', 'automaton3-authority.py')
  const result = spawnSync(python, [script, 'evaluate'], {
    cwd: repoRoot(), input: JSON.stringify(payload), encoding: 'utf8',
    env: process.env, timeout: 15_000, maxBuffer: 1_048_576,
  })
  if (!result.stdout) return localDenial('AUTHORITY_SERVICE_UNAVAILABLE')
  try {
    return JSON.parse(result.stdout) as AuthorityDecision
  } catch {
    return localDenial('AUTHORITY_RESPONSE_MALFORMED')
  }
}

function denied(decision: AuthorityDecision): { content: Array<{ type: 'text'; text: string }> } | null {
  return decision.outcome === 'ADMITTED' ? null : text({ authority: decision, external_effect: 'NOT_EXECUTED' })
}

server.tool('aegis_health', 'Check AEGIS constitutional health: t0_verdict, corruption_count, hash chain status.', {}, async () => {
  const [health, node] = await Promise.all([bridgeGet('/health'), bridgeGet('/node')])
  const ok = (node as Record<string, unknown>)['t0_verdict'] === true && (node as Record<string, unknown>)['corruption_count'] === 0
  return text({ constitutional_health: ok ? 'PASS' : 'FAIL', health, node })
})

server.tool('aegis_telemetry', 'Get live AEGIS telemetry: PGCS passes, epoch count, VCG metrics, martingale state.', {}, async () => text(await bridgeGet('/telemetry')))

server.tool('aegis_platform_status', 'Get AEGIS platform status through a D0 authority decision.', {}, async () => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'mcp:read', requestedCapability: 'mcp.platform.status', tool: 'aegis_platform_status', target: '/platform/status', action: { operation: 'read', endpoint: '/platform/status' } })
  const denial = denied(authority); if (denial) return denial
  return text({ authority, result: await bridgeGet('/platform/status', true) })
})

server.tool(
  'aegis_collaborate',
  'Run the governed swarm. Requires API key, execution identity, observed capability, workspace binding, and D2 approval.',
  { objective: z.string().min(10), mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis') },
  async ({ objective, mode }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set', external_effect: 'NOT_EXECUTED' })
    const authority = authorizeAction({ actionClass: 'D2', authorityDomain: 'agent:shared-state', requestedCapability: 'mcp.collaborate', tool: 'aegis_collaborate', target: '/platform/collaborate', action: { operation: 'collaborate', objective, mode, live: false } })
    const denial = denied(authority); if (denial) return denial
    return text({ authority, result: await bridgePost('/platform/collaborate', { objective, mode, live: false }, true) })
  },
)

server.tool(
  'aegis_start_execution',
  'Start a durable governed execution. Requires API key, identity, workspace binding, capability evidence, and D2 approval.',
  { objective: z.string().min(10), mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis') },
  async ({ objective, mode }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set', external_effect: 'NOT_EXECUTED' })
    const authority = authorizeAction({ actionClass: 'D2', authorityDomain: 'workflow:durable', requestedCapability: 'mcp.execution.start', tool: 'aegis_start_execution', target: '/platform/executions', action: { operation: 'start-execution', objective, mode, live: false } })
    const denial = denied(authority); if (denial) return denial
    return text({ authority, result: await bridgePost('/platform/executions', { objective, mode, live: false }, true) })
  },
)

server.tool('aegis_get_execution', 'Read a durable execution through a D0 authority decision.', { execution_id: z.string() }, async ({ execution_id }) => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'workflow:read', requestedCapability: 'mcp.execution.read', tool: 'aegis_get_execution', target: `/platform/executions/${execution_id}`, action: { operation: 'read-execution', execution_id } })
  const denial = denied(authority); if (denial) return denial
  return text({ authority, result: await bridgeGet(`/platform/executions/${execution_id}`, true) })
})

server.tool(
  'aegis_governed_claude_call',
  'Send a governed model call. D3 requires explicit approval and idempotency or compensation.',
  { prompt: z.string().min(1), system: z.string().optional(), idempotency_key: z.string().min(1).optional(), compensation_reference: z.string().min(1).optional() },
  async ({ prompt, system, idempotency_key, compensation_reference }) => {
    const body: Record<string, unknown> = { prompt }; if (system) body['system'] = system
    const authority = authorizeAction({ actionClass: 'D3', authorityDomain: 'external:model-call', requestedCapability: 'mcp.claude.call', tool: 'aegis_governed_claude_call', target: '/claude', action: { operation: 'governed-model-call', prompt_digest: createHash('sha256').update(prompt, 'utf8').digest('hex'), has_system: Boolean(system) }, idempotencyKey: idempotency_key, compensationReference: compensation_reference })
    const denial = denied(authority); if (denial) return denial
    return text({ authority, result: await bridgePost('/claude', body) })
  },
)

function jsonResource(uri: URL, value: unknown): { contents: Array<{ uri: string; mimeType: string; text: string }> } {
  return { contents: [{ uri: uri.href, mimeType: 'application/json', text: JSON.stringify(value, null, 2) }] }
}

async function bridgeResource(uri: URL, path: string): Promise<{ contents: Array<{ uri: string; mimeType: string; text: string }> }> {
  try { return jsonResource(uri, await bridgeGet(path)) }
  catch (err) { return jsonResource(uri, { unavailable: true, reason: err instanceof Error ? err.message : String(err) }) }
}

function fileResource(uri: URL, relPath: string): { contents: Array<{ uri: string; mimeType: string; text: string }> } {
  try {
    const md = readFileSync(join(repoRoot(), relPath), 'utf8')
    return { contents: [{ uri: uri.href, mimeType: 'text/markdown', text: md }] }
  } catch (err) { return jsonResource(uri, { unavailable: true, reason: err instanceof Error ? err.message : String(err) }) }
}

server.resource('aegis-node', 'aegis://node', { description: 'Live constitutional node state. Fuel-free.', mimeType: 'application/json' }, async (uri) => bridgeResource(uri, '/node'))
server.resource('aegis-telemetry', 'aegis://telemetry', { description: 'Live AEGIS telemetry. Fuel-free.', mimeType: 'application/json' }, async (uri) => bridgeResource(uri, '/telemetry'))
server.resource('aegis-health', 'aegis://health', { description: 'Bridge liveness. Fuel-free.', mimeType: 'application/json' }, async (uri) => bridgeResource(uri, '/health'))
server.resource('aegis-authority-index', 'aegis://authority/index', { description: 'Repository authority graph. Fuel-free.', mimeType: 'text/markdown' }, async (uri) => fileResource(uri, 'INDEX.md'))
server.resource('aegis-authority-repo-map', 'aegis://authority/repo-map', { description: 'Repository wiring map. Fuel-free.', mimeType: 'text/markdown' }, async (uri) => fileResource(uri, 'REPO_MAP.md'))

const transport = new StdioServerTransport()
await server.connect(transport)
