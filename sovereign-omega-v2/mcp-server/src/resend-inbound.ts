import { spawnSync } from 'node:child_process'
import { join } from 'node:path'

export type ResendInboundRequest = {
  raw_body_base64: string
  headers: Array<[string, string]>
  method?: 'POST'
}

export type ResendInboundResult = {
  status: string
  codes?: string[]
  external_effect: 'NOT_EXECUTED'
  [key: string]: unknown
}

type Spawn = typeof spawnSync

function rejected(code: string): ResendInboundResult {
  return { status: 'REJECTED', codes: [code], external_effect: 'NOT_EXECUTED' }
}

export function runResendInbound(repoRoot: string, request: ResendInboundRequest, spawn: Spawn = spawnSync): ResendInboundResult {
  const python = process.env['AEGIS_PYTHON'] ?? 'python3'
  const script = join(repoRoot, 'scripts', 'resend_inbound_ingest.py')
  const result = spawn(python, [script], {
    cwd: repoRoot,
    input: JSON.stringify(request),
    encoding: 'utf8',
    env: process.env,
    timeout: 15_000,
    maxBuffer: 1_048_576,
  })
  if (result.error || result.signal || result.status !== 0 || !result.stdout) {
    return rejected('RESEND_INGEST_UNAVAILABLE')
  }
  try {
    const parsed = JSON.parse(result.stdout) as Record<string, unknown>
    if (typeof parsed['status'] !== 'string' || parsed['external_effect'] !== 'NOT_EXECUTED') {
      return rejected('RESEND_INGEST_RESPONSE_INVALID')
    }
    if (parsed['codes'] !== undefined && (!Array.isArray(parsed['codes']) || !parsed['codes'].every((item) => typeof item === 'string'))) {
      return rejected('RESEND_INGEST_RESPONSE_INVALID')
    }
    return parsed as ResendInboundResult
  } catch {
    return rejected('RESEND_INGEST_RESPONSE_INVALID')
  }
}
