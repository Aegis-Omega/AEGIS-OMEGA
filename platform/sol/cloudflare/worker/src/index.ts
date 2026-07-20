import { createMcpHandler } from 'agents/mcp'
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js'
import { z } from 'zod'

import {
  AccessDeniedError,
  enforceBodyLimit,
  jsonResponse,
  parsePositiveInteger,
  requireAccessIdentity,
  type AccessIdentity,
} from './guard.js'

type Env = Cloudflare.Env

type ToolTextResult = {
  content: Array<{ type: 'text'; text: string }>
  structuredContent: Record<string, unknown>
  isError?: boolean
}

const Provider = z.enum([
  'dataverse',
  'figma',
  'github',
  'huggingface',
  'nvidia',
  'sharepoint',
  'wolfram',
])

const ConsequenceClass = z.enum(['D0', 'D1', 'D2', 'D3', 'D4'])
const Sha256 = z.string().regex(/^[0-9a-f]{64}$/)

function toolResult(payload: Record<string, unknown>, isError = false): ToolTextResult {
  return {
    content: [{ type: 'text', text: JSON.stringify(payload) }],
    structuredContent: payload,
    ...(isError ? { isError: true } : {}),
  }
}

async function coreJson(
  env: Env,
  identity: AccessIdentity,
  path: string,
  init?: RequestInit,
): Promise<Record<string, unknown>> {
  const headers = new Headers(init?.headers)
  headers.set('accept', 'application/json')
  headers.set('content-type', 'application/json')
  headers.set('x-aegis-operator-email', identity.email)
  headers.set('x-aegis-access-jwt', identity.jwt)
  headers.set('x-aegis-edge', 'cloudflare-sol-mcp')

  const response = await env.AEGIS_CORE.fetch(`https://aegis-core.internal${path}`, {
    ...init,
    headers,
  })

  const contentType = response.headers.get('content-type') ?? ''
  const payload = contentType.includes('application/json')
    ? await response.json<Record<string, unknown>>()
    : { message: await response.text() }

  if (!response.ok) {
    return {
      status: 'DENIED',
      upstream_status: response.status,
      external_effect: 'NOT_EXECUTED',
      evidence: payload,
    }
  }
  return payload
}

function createServer(env: Env, identity: AccessIdentity): McpServer {
  const server = new McpServer({ name: 'aegis-sol-edge', version: '0.1.0' })

  server.registerTool(
    'sol_platform_status',
    {
      title: 'Read SOL platform status',
      description: 'Use this when the operator needs the governed platform, provider, and authority status.',
      inputSchema: {},
      annotations: {
        readOnlyHint: true,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: false,
      },
    },
    async () => toolResult(await coreJson(env, identity, '/platform/sol/status')),
  )

  server.registerTool(
    'sol_request_execution',
    {
      title: 'Request a governed provider execution',
      description: 'Use this when an operator wants SOL to evaluate and, only if admitted, execute one provider capability.',
      inputSchema: {
        provider: Provider,
        capability: z.string().min(3).max(160),
        consequence_class: ConsequenceClass,
        target: z.string().min(1).max(500),
        arguments_digest: Sha256,
        expected_parent_state_root: Sha256,
        idempotency_key: z.string().min(8).max(200),
        compensation_reference: z.string().min(1).max(500).optional(),
      },
      annotations: {
        readOnlyHint: false,
        destructiveHint: false,
        idempotentHint: true,
        openWorldHint: true,
      },
    },
    async (input) => {
      const result = await coreJson(env, identity, '/platform/sol/executions', {
        method: 'POST',
        body: JSON.stringify({
          schema_version: '1.0.0',
          operator: { email: identity.email },
          source: 'cloudflare-remote-mcp',
          ...input,
        }),
      })
      return toolResult(result, result['status'] === 'DENIED')
    },
  )

  return server
}

export default {
  async fetch(request: Request, env: Env, ctx: ExecutionContext): Promise<Response> {
    const url = new URL(request.url)
    if (url.pathname === '/health') {
      return jsonResponse(200, {
        status: 'ok',
        service: 'aegis-sol-edge-mcp',
        environment: env.AEGIS_DEPLOYMENT_ENV,
      })
    }

    if (url.pathname !== '/mcp') {
      return jsonResponse(404, { error: 'not_found' })
    }

    try {
      enforceBodyLimit(request, parsePositiveInteger(env.AEGIS_MAX_BODY_BYTES, 1_048_576))
      const identity = requireAccessIdentity(request)
      const server = createServer(env, identity)
      return await createMcpHandler(server)(request, env, ctx)
    } catch (error) {
      if (error instanceof AccessDeniedError) {
        return jsonResponse(401, {
          error: 'access_denied',
          reason: error.message,
          external_effect: 'NOT_EXECUTED',
        })
      }
      console.error(JSON.stringify({
        event: 'sol_edge_unhandled_error',
        request_id: request.headers.get('cf-ray') ?? crypto.randomUUID(),
        error: error instanceof Error ? error.message : String(error),
      }))
      return jsonResponse(500, {
        error: 'internal_error',
        external_effect: 'UNKNOWN',
      })
    }
  },
} satisfies ExportedHandler<Env>
