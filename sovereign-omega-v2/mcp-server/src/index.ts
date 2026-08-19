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
import {
  AuthorityResponseError,
  buildAuthorityResponseBindings,
  parseAuthorityProcessResult,
  type ActionClass,
  type VerifiedAuthorityDecision,
} from './authority-response.js'
import {
  OrganismClientError,
  prepareProviderContribution,
  readNextWork,
  readOrganismStatus,
  recordProviderContribution,
  recordProviderTextContribution,
} from './organism-client.js'
import {
  ProviderSessionError,
  bootstrapProviderAction,
  providerSessionConfigured,
} from './provider-session-client.js'

const BRIDGE = (process.env['AEGIS_BRIDGE_URL'] ?? 'http://localhost:7890').replace(/\/$/, '')
const API_KEY = process.env['AEGIS_API_KEY'] ?? ''

const server = new McpServer({ name: 'aegis-constitutional-swarm', version: '0.4.0' })

async function bridgeGet(path: string, apiKey = false): Promise<unknown> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (apiKey && API_KEY) headers['X-API-Key'] = API_KEY
  const res = await fetch(`${BRIDGE}${path}`, { headers })
  if (!res.ok) throw new Error(`Bridge ${path} → HTTP ${res.status}`)
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

type DeniedAuthorityDecision = { outcome: 'DENIED'; denial_codes: string[] }
type AuthorityDecision = VerifiedAuthorityDecision | DeniedAuthorityDecision

function localDenial(code: string): DeniedAuthorityDecision {
  return { outcome: 'DENIED', denial_codes: [code] }
}

function authorizeAction(input: {
  actionClass: ActionClass
  authorityDomain: string
  requestedCapability: string
  tool: string
  target: string
  action: Record<string, unknown>
  mutationTarget?: string
  rollbackReference?: string
  idempotencyKey?: string
  compensationReference?: string
}): AuthorityDecision {
  const root = repoRoot()
  const identityRaw = process.env['AEGIS_EXECUTION_IDENTITY_JSON']
  let identity: unknown
  let workspace: unknown
  let approval: unknown
  let trustedAuthorityKeys: Record<string, string>
  let bootstrappedProviderSession = false
  try {
    if (identityRaw) {
      identity = JSON.parse(identityRaw)
      const workspaceRaw = process.env['AEGIS_WORKSPACE_OBSERVATION_JSON']
      if (!workspaceRaw) return localDenial('WORKSPACE_OBSERVATION_UNAVAILABLE')
      workspace = JSON.parse(workspaceRaw)
    } else if (providerSessionConfigured()) {
      const bootstrap = bootstrapProviderAction(root, {
        actionClass: input.actionClass,
        authorityDomain: input.authorityDomain,
        requestedCapability: input.requestedCapability,
        tool: input.tool,
        target: input.target,
        action: input.action,
        mutationTarget: input.mutationTarget ?? '.',
      })
      identity = bootstrap.identity
      workspace = bootstrap.workspace
      bootstrappedProviderSession = true
    } else {
      return localDenial('IDENTITY_UNAVAILABLE')
    }
    if (typeof workspace !== 'object' || workspace === null || Array.isArray(workspace)) {
      return localDenial('WORKSPACE_OBSERVATION_MALFORMED')
    }
    const approvalRaw = process.env['AEGIS_APPROVAL_GRANT_JSON']
    approval = approvalRaw ? JSON.parse(approvalRaw) : undefined
    const authorityKeysRaw = process.env['AEGIS_AUTHORITY_VERIFY_KEYS_JSON']
    if (!authorityKeysRaw) return localDenial('AUTHORITY_VERIFY_KEYS_UNAVAILABLE')
    const parsedAuthorityKeys: unknown = JSON.parse(authorityKeysRaw)
    if (typeof parsedAuthorityKeys !== 'object' || parsedAuthorityKeys === null || Array.isArray(parsedAuthorityKeys)
        || Object.values(parsedAuthorityKeys).some((value) => typeof value !== 'string')) {
      return localDenial('AUTHORITY_VERIFY_KEYS_MALFORMED')
    }
    trustedAuthorityKeys = parsedAuthorityKeys as Record<string, string>
  } catch (error) {
    if (error instanceof ProviderSessionError) return localDenial(error.code)
    return localDenial('AUTHORITY_ENVIRONMENT_MALFORMED')
  }
  const sourceState = spawnSync('git', ['-C', root, 'rev-parse', 'HEAD'], {
    encoding: 'utf8', timeout: 5_000, maxBuffer: 65_536,
  })
  const remoteState = spawnSync('git', ['-C', root, 'config', '--get', 'remote.origin.url'], {
    encoding: 'utf8', timeout: 5_000, maxBuffer: 65_536,
  })
  if (sourceState.status !== 0 || sourceState.signal || sourceState.error) return localDenial('SOURCE_COMMIT_UNAVAILABLE')
  if (remoteState.status !== 0 || remoteState.signal || remoteState.error) return localDenial('REMOTE_ORIGIN_UNAVAILABLE')
  const workspaceRecord = workspace as Record<string, unknown>
  const actualRemote = remoteState.stdout.trim()
  if (!bootstrappedProviderSession && workspaceRecord['remote_origin'] !== actualRemote) return localDenial('WORKSPACE_REMOTE_CLAIM_MISMATCH')
  const boundWorkspace = { ...workspaceRecord, remote_origin: actualRemote } as {
    actual_cwd: string; remote_origin: string; mutation_target: string; path_views?: Record<string, string>
  }
  let bindings
  try {
    bindings = buildAuthorityResponseBindings(identity, input, boundWorkspace, root, trustedAuthorityKeys)
  } catch (error) {
    return localDenial(error instanceof AuthorityResponseError ? error.code : 'EXECUTION_IDENTITY_MALFORMED')
  }
  if (sourceState.stdout.trim() !== bindings.expectedSourceCommit) return localDenial('SOURCE_COMMIT_MISMATCH')
  const leaseGenerationRaw = process.env['AEGIS_LEASE_GENERATION'] ?? '0'
  if (!/^(?:0|[1-9][0-9]*)$/.test(leaseGenerationRaw)) return localDenial('LEASE_GENERATION_MALFORMED')
  const leaseGeneration = Number(leaseGenerationRaw)
  if (!Number.isSafeInteger(leaseGeneration)) return localDenial('LEASE_GENERATION_MALFORMED')
  const payload = {
    identity,
    workspace: boundWorkspace,
    approval,
    action: input.action,
    request: {
      action_class: input.actionClass,
      authority_domain: input.authorityDomain,
      requested_capability: input.requestedCapability,
      tool: input.tool,
      target: input.target,
      workspace_mode: input.actionClass === 'D0' ? 'READ_ONLY' : 'REPOSITORY',
      current_generation: leaseGeneration,
      rollback_reference: input.rollbackReference ?? 'NONE',
      idempotency_key: input.idempotencyKey ?? 'NONE',
      compensation_reference: input.compensationReference ?? 'NONE',
    },
  }
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const script = join(root, 'scripts', 'automaton3-authority.py')
  const result = spawnSync(python, [script, 'evaluate'], {
    cwd: root, input: JSON.stringify(payload), encoding: 'utf8',
    env: process.env, timeout: 15_000, maxBuffer: 1_048_576,
  })
  try {
    return parseAuthorityProcessResult({ status: result.status, signal: result.signal, stdout: result.stdout, stderr: result.stderr, error: result.error }, bindings)
  } catch (error) {
    return localDenial(error instanceof AuthorityResponseError ? error.code : 'AUTHORITY_RESPONSE_MALFORMED')
  }
}

function isDenied(decision: AuthorityDecision): decision is DeniedAuthorityDecision {
  return decision.outcome === 'DENIED'
}

function denialResponse(decision: DeniedAuthorityDecision): { content: Array<{ type: 'text'; text: string }> } {
  return text({ authority: decision, external_effect: 'NOT_EXECUTED' })
}

function terminalAdapterUnavailable(authority: VerifiedAuthorityDecision) {
  return text({ authority, outcome: 'DENIED', denial_codes: ['TERMINAL_EXECUTION_ADAPTER_UNAVAILABLE'], external_effect: 'NOT_EXECUTED' })
}

function configuredProviderIdentity(): { provider: string; model: string; session: string } | null {
  const provider = process.env['AEGIS_PROVIDER_ID']
  const model = process.env['AEGIS_MODEL_ID']
  const session = process.env['AEGIS_PROVIDER_SESSION_ID']
  return provider && model && session ? { provider, model, session } : null
}

server.tool('aegis_health', 'Check AEGIS constitutional health: t0_verdict, corruption_count, hash chain status.', {}, async () => {
  const [health, node] = await Promise.all([bridgeGet('/health'), bridgeGet('/node')])
  const ok = (node as Record<string, unknown>)['t0_verdict'] === true && (node as Record<string, unknown>)['corruption_count'] === 0
  return text({ constitutional_health: ok ? 'PASS' : 'FAIL', health, node })
})

server.tool('aegis_telemetry', 'Get live AEGIS telemetry: PGCS passes, epoch count, VCG metrics, martingale state.', {}, async () => text(await bridgeGet('/telemetry')))

server.tool('aegis_platform_status', 'Get AEGIS platform status through a D0 authority decision.', {}, async () => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'mcp:read', requestedCapability: 'mcp.platform.status', tool: 'aegis_platform_status', target: '/platform/status', action: { operation: 'read', endpoint: '/platform/status' } })
  if (isDenied(authority)) return denialResponse(authority)
  return text({ authority, result: await bridgeGet('/platform/status', true) })
})

server.tool('aegis_organism_status', 'Read the durable AEGIS organization work ledger. Read-only; provider outputs remain non-authoritative.', {}, async () => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'organism:read', requestedCapability: 'mcp.organism.status', tool: 'aegis_organism_status', target: '.aegis/runtime/organism.json', action: { operation: 'read-organism-status' } })
  if (isDenied(authority)) return denialResponse(authority)
  try { return text({ authority, organism: readOrganismStatus(repoRoot()) }) }
  catch (error) { return text({ authority, outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_STATUS_ERROR' }) }
})

server.tool('aegis_next_work', 'Return queued AEGIS work available to this provider session. This is read-only and grants no claim, lease, or authority.', { limit: z.number().int().min(1).max(100).default(10) }, async ({ limit }) => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'organism:read', requestedCapability: 'mcp.organism.next', tool: 'aegis_next_work', target: '.aegis/runtime/organism.json', action: { operation: 'read-next-work', limit } })
  if (isDenied(authority)) return denialResponse(authority)
  try { return text({ authority, work: readNextWork(repoRoot(), limit), lease: 'NONE', claim: 'NONE' }) }
  catch (error) { return text({ authority, outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_NEXT_WORK_ERROR' }) }
})

server.tool(
  'aegis_contribute',
  'Attach a provider/model artifact digest to an existing AEGIS work order. This records NON_AUTHORITATIVE_EVIDENCE only and cannot approve, verify, or admit the work.',
  {
    work_id: z.string().regex(/^[A-Za-z0-9._:/@+\-]{1,128}$/),
    provider: z.string().regex(/^[A-Za-z0-9._:/@+\-]{1,128}$/),
    model: z.string().regex(/^[A-Za-z0-9._:/@+\-]{1,128}$/),
    artifact_digest: z.string().regex(/^[0-9a-f]{64}$/),
    source_ref: z.string().regex(/^[A-Za-z0-9._:/@+\-]{1,128}$/),
  },
  async ({ work_id, provider, model, artifact_digest, source_ref }) => {
    const configured = configuredProviderIdentity()
    if (configured && (configured.provider !== provider || configured.model !== model)) return denialResponse(localDenial('PROVIDER_IDENTITY_MISMATCH'))
    const root = repoRoot()
    let prepared
    try { prepared = prepareProviderContribution(root, work_id) }
    catch (error) { return text({ outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_PREPARE_ERROR', admission_effect: 'NONE' }) }
    const action = {
      operation: 'record-provider-contribution', work_id, provider, model, artifact_digest, source_ref,
      pre_state_root: prepared.state_root, pre_order_digest: prepared.order_digest, rollback_reference: prepared.rollback_reference,
    }
    const authority = authorizeAction({
      actionClass: 'D1', authorityDomain: 'organism:contribution', requestedCapability: 'mcp.organism.contribute', tool: 'aegis_contribute', target: '.aegis/runtime/organism.json', mutationTarget: '.aegis/runtime',
      action, rollbackReference: prepared.rollback_reference,
    })
    if (isDenied(authority)) return denialResponse(authority)
    try {
      const contribution = recordProviderContribution(root, { workId: work_id, provider, model, artifactDigest: artifact_digest, sourceRef: source_ref, rollbackReference: prepared.rollback_reference })
      return text({ authority, contribution, epistemic_status: 'NON_AUTHORITATIVE_EVIDENCE', admission_effect: 'NONE' })
    } catch (error) {
      return text({ authority, outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_CONTRIBUTION_ERROR', admission_effect: 'NONE' })
    }
  },
)

server.tool(
  'aegis_contribute_text',
  'Persist this provider session output as a content-addressed AEGIS artifact and attach it to an existing work order as NON_AUTHORITATIVE_EVIDENCE.',
  {
    work_id: z.string().regex(/^[A-Za-z0-9._:/@+\-]{1,128}$/),
    text: z.string().min(1).max(262144),
    media_type: z.enum(['text/plain', 'text/markdown', 'application/json']).default('text/markdown'),
  },
  async ({ work_id, text: contributionText, media_type }) => {
    const configured = configuredProviderIdentity()
    if (!configured) return denialResponse(localDenial('PROVIDER_SESSION_IDENTITY_REQUIRED'))
    const root = repoRoot()
    let prepared
    try { prepared = prepareProviderContribution(root, work_id) }
    catch (error) { return text({ outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_PREPARE_ERROR', admission_effect: 'NONE' }) }
    const textDigest = createHash('sha256').update(contributionText, 'utf8').digest('hex')
    const sourceRef = `mcp:${configured.provider}`
    const action = {
      operation: 'record-provider-text-contribution', work_id, provider: configured.provider, model: configured.model,
      text_digest: textDigest, byte_length: Buffer.byteLength(contributionText, 'utf8'), media_type, source_ref: sourceRef,
      pre_state_root: prepared.state_root, pre_order_digest: prepared.order_digest, rollback_reference: prepared.rollback_reference,
    }
    const authority = authorizeAction({
      actionClass: 'D1', authorityDomain: 'organism:contribution', requestedCapability: 'mcp.organism.contribute', tool: 'aegis_contribute_text', target: '.aegis/runtime/organism.json', mutationTarget: '.aegis/runtime',
      action, rollbackReference: prepared.rollback_reference,
    })
    if (isDenied(authority)) return denialResponse(authority)
    try {
      const contribution = recordProviderTextContribution(root, {
        workId: work_id, provider: configured.provider, model: configured.model, text: contributionText,
        sourceRef, mediaType: media_type, rollbackReference: prepared.rollback_reference,
      })
      return text({ authority, contribution, epistemic_status: 'NON_AUTHORITATIVE_EVIDENCE', admission_effect: 'NONE' })
    } catch (error) {
      return text({ authority, outcome: 'ERROR', code: error instanceof OrganismClientError ? error.code : 'ORGANISM_CONTRIBUTION_ERROR', admission_effect: 'NONE' })
    }
  },
)

server.tool(
  'aegis_collaborate',
  'Run the governed swarm. Requires API key, execution identity, observed capability, workspace binding, and D2 approval.',
  { objective: z.string().min(10), mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis'), rollback_reference: z.string().min(1) },
  async ({ objective, mode, rollback_reference }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set', external_effect: 'NOT_EXECUTED' })
    const authority = authorizeAction({ actionClass: 'D2', authorityDomain: 'agent:shared-state', requestedCapability: 'mcp.collaborate', tool: 'aegis_collaborate', target: '/platform/collaborate', action: { operation: 'collaborate', objective, mode, live: false }, rollbackReference: rollback_reference })
    if (isDenied(authority)) return denialResponse(authority)
    return terminalAdapterUnavailable(authority)
  },
)

server.tool(
  'aegis_start_execution',
  'Start a durable governed execution. Requires API key, identity, workspace binding, capability evidence, and D2 approval.',
  { objective: z.string().min(10), mode: z.enum(['revenue', 'gtm', 'analysis', 'risk', 'compliance']).default('analysis'), rollback_reference: z.string().min(1) },
  async ({ objective, mode, rollback_reference }) => {
    if (!API_KEY) return text({ error: 'AEGIS_API_KEY not set', external_effect: 'NOT_EXECUTED' })
    const authority = authorizeAction({ actionClass: 'D2', authorityDomain: 'workflow:durable', requestedCapability: 'mcp.execution.start', tool: 'aegis_start_execution', target: '/platform/executions', action: { operation: 'start-execution', objective, mode, live: false }, rollbackReference: rollback_reference })
    if (isDenied(authority)) return denialResponse(authority)
    return terminalAdapterUnavailable(authority)
  },
)

server.tool('aegis_get_execution', 'Read a durable execution through a D0 authority decision.', { execution_id: z.string() }, async ({ execution_id }) => {
  const authority = authorizeAction({ actionClass: 'D0', authorityDomain: 'workflow:read', requestedCapability: 'mcp.execution.read', tool: 'aegis_get_execution', target: `/platform/executions/${execution_id}`, action: { operation: 'read-execution', execution_id } })
  if (isDenied(authority)) return denialResponse(authority)
  return text({ authority, result: await bridgeGet(`/platform/executions/${execution_id}`, true) })
})

server.tool(
  'aegis_governed_claude_call',
  'Send a governed model call. D3 requires explicit approval and idempotency or compensation.',
  { prompt: z.string().min(1), system: z.string().optional(), idempotency_key: z.string().min(1).optional(), compensation_reference: z.string().min(1).optional() },
  async ({ prompt, system, idempotency_key, compensation_reference }) => {
    const body: Record<string, unknown> = { prompt }; if (system) body['system'] = system
    const authority = authorizeAction({ actionClass: 'D3', authorityDomain: 'external:model-call', requestedCapability: 'mcp.claude.call', tool: 'aegis_governed_claude_call', target: '/claude', action: { operation: 'governed-model-call', prompt_digest: createHash('sha256').update(prompt, 'utf8').digest('hex'), system_digest: system === undefined ? '0'.repeat(64) : createHash('sha256').update(system, 'utf8').digest('hex'), provider_payload_digest: createHash('sha256').update(JSON.stringify(body), 'utf8').digest('hex'), has_system: system !== undefined }, idempotencyKey: idempotency_key, compensationReference: compensation_reference })
    if (isDenied(authority)) return denialResponse(authority)
    return terminalAdapterUnavailable(authority)
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
