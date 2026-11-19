/** TAR-21: request-bound Slack-to-agent machine credential. No public keys, service JWT or anon bypass. */
export const SLACK_TASK_MAX = 512
export const AGENT_BODY_MAX_BYTES = 16_384
const encoder = new TextEncoder()
const decoder = new TextDecoder('utf-8', { fatal: true })
const IDENTIFIER = /^[A-Z0-9]{4,32}$/
const EVENT_ID = /^[A-Za-z0-9:._-]{8,128}$/
const NONCE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i
const PATH = '/functions/v1/agent'

export type SlackMachineBody = {
  task: string
  scope: 'slack:answer'
  slack: { team_id: string; user_id: string; event_id: string }
}

function csvSet(s: string): Set<string> {
  return new Set(s.split(',').map(v => v.trim()).filter(Boolean))
}

export function allowedSlackActor(team: string, user: string, teams: string, users: string, actors: string): boolean {
  const ts = csvSet(teams)
  const us = csvSet(users)
  const as = csvSet(actors)
  return ts.size > 0 && us.size > 0 && as.size > 0
    && IDENTIFIER.test(team) && IDENTIFIER.test(user)
    && ts.has(team) && us.has(user) && as.has(`${team}:${user}`)
}

async function importHmac(secret: string): Promise<CryptoKey> {
  if (encoder.encode(secret).length < 32) throw Error('machine signing key unavailable')
  return crypto.subtle.importKey('raw', encoder.encode(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign', 'verify'])
}

function decodeHex(hex: string): Uint8Array | null {
  if (!/^[a-f0-9]{64}$/i.test(hex)) return null
  return new Uint8Array(hex.match(/../g)!.map(s => Number.parseInt(s, 16)))
}

async function sha256Hex(body: string): Promise<string> {
  const digest = new Uint8Array(await crypto.subtle.digest('SHA-256', encoder.encode(body)))
  return Array.from(digest, b => b.toString(16).padStart(2, '0')).join('')
}

export async function readBoundedBody(req: Request): Promise<string | null> {
  if (!req.body) return null
  const length = req.headers.get('content-length')
  if (length && (!/^\d+$/.test(length) || Number(length) > AGENT_BODY_MAX_BYTES)) return null
  const reader = req.body.getReader()
  const chunks: Uint8Array[] = []
  let size = 0
  try {
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      size += value.byteLength
      if (size > AGENT_BODY_MAX_BYTES) {
        await reader.cancel().catch(() => {})
        return null
      }
      chunks.push(value)
    }
    const bytes = new Uint8Array(size)
    let offset = 0
    for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength }
    return decoder.decode(bytes)
  } catch {
    return null
  } finally {
    reader.releaseLock()
  }
}

/** Verify Slack's raw-body HMAC, never accepting a missing secret or malformed timestamp. */
export async function verifySlackSignature(
  body: string, timestamp: string, signature: string, signingSecret: string, nowSeconds = Math.floor(Date.now() / 1000),
): Promise<boolean> {
  if (!signingSecret || !/^\d{10}$/.test(timestamp) || !/^v0=[a-f0-9]{64}$/i.test(signature)) return false
  if (Math.abs(nowSeconds - Number(timestamp)) > 300) return false
  try {
    const key = await crypto.subtle.importKey('raw', encoder.encode(signingSecret),
      { name: 'HMAC', hash: 'SHA-256' }, false, ['verify'])
    return crypto.subtle.verify('HMAC', key, decodeHex(signature.slice(3))!,
      encoder.encode(`v0:${timestamp}:${body}`))
  } catch { return false }
}

function assertionInput(ts: string, nonce: string, bodyHash: string): string {
  return `aegis-slack-agent-v1\nPOST\n${PATH}\n${ts}\n${nonce}\n${bodyHash}`
}

export async function signSlackAgentRequest(
  body: SlackMachineBody, key: string, keyId: string, nowSeconds = Math.floor(Date.now() / 1000),
  nonce = crypto.randomUUID(),
): Promise<{ rawBody: string; headers: Record<string, string> }> {
  if (!keyId || !/^[A-Za-z0-9_-]{1,48}$/.test(keyId) || !NONCE.test(nonce)) throw Error('invalid machine identity')
  const rawBody = JSON.stringify(body)
  if (encoder.encode(rawBody).length > AGENT_BODY_MAX_BYTES) throw Error('payload too long')
  const ts = String(nowSeconds)
  const hmac = await importHmac(key)
  const input = assertionInput(ts, nonce, await sha256Hex(rawBody))
  const signature = await crypto.subtle.sign('HMAC', hmac, encoder.encode(input))
  const hex = Array.from(new Uint8Array(signature), b => b.toString(16).padStart(2, '0')).join('')
  return { rawBody, headers: {
    'Content-Type': 'application/json',
    'x-aegis-machine-key-id': keyId,
    'x-aegis-machine-ts': ts,
    'x-aegis-machine-nonce': nonce,
    'x-aegis-machine-sig': `v1=${hex}`,
  } }
}

export async function authorizeSlackMachine(
  headers: Headers, rawBody: string, config: {
    key: string; keyId: string; allowedTeams: string; allowedUsers: string; allowedActors: string; nowSeconds?: number
  },
): Promise<SlackMachineBody | null> {
  // A request carrying both machine and user authorization is ambiguous and denied.
  if (headers.has('authorization') || !config.keyId || !/^[A-Za-z0-9_-]{1,48}$/.test(config.keyId)) return null
  const keyId = headers.get('x-aegis-machine-key-id') ?? ''
  const ts = headers.get('x-aegis-machine-ts') ?? ''
  const nonce = headers.get('x-aegis-machine-nonce') ?? ''
  const signature = headers.get('x-aegis-machine-sig') ?? ''
  if (keyId !== config.keyId || !/^\d{10}$/.test(ts) || !NONCE.test(nonce)
    || !/^v1=[a-f0-9]{64}$/i.test(signature)) return null
  const now = config.nowSeconds ?? Math.floor(Date.now() / 1000)
  if (Number(ts) < now - 60 || Number(ts) > now + 30) return null
  if (encoder.encode(rawBody).length > AGENT_BODY_MAX_BYTES) return null
  try {
    const hmac = await importHmac(config.key)
    const message = assertionInput(ts, nonce, await sha256Hex(rawBody))
    if (!(await crypto.subtle.verify('HMAC', hmac, decodeHex(signature.slice(3))!, encoder.encode(message)))) return null
    const body: unknown = JSON.parse(rawBody)
    if (!body || typeof body !== 'object' || Array.isArray(body)) return null
    const obj = body as Record<string, unknown>
    if (Object.keys(obj).sort().join(',') !== 'scope,slack,task'
      || obj.scope !== 'slack:answer' || typeof obj.task !== 'string'
      || !obj.task.trim() || obj.task.length > SLACK_TASK_MAX) return null
    const slack = obj.slack
    if (!slack || typeof slack !== 'object' || Array.isArray(slack)) return null
    const s = slack as Record<string, unknown>
    if (Object.keys(s).sort().join(',') !== 'event_id,team_id,user_id'
      || typeof s.team_id !== 'string' || typeof s.user_id !== 'string'
      || typeof s.event_id !== 'string' || !EVENT_ID.test(s.event_id)) return null
    if (!allowedSlackActor(s.team_id, s.user_id, config.allowedTeams, config.allowedUsers, config.allowedActors)) return null
    return obj as SlackMachineBody
  } catch { return null }
}

export type SlackTask = SlackMachineBody & { channel: string; threadTs?: string }
export type SlackParsed = { kind: 'challenge'; challenge: string } | { kind: 'task'; job: SlackTask } | { kind: 'ignore' }

export async function parseSlackPayload(raw: string, contentType: string, timestamp: string): Promise<SlackParsed | null> {
  let task: string, team: string, user: string, channel: string, eventId: string, threadTs: string | undefined
  if (contentType.includes('application/x-www-form-urlencoded')) {
    const p = new URLSearchParams(raw)
    if (p.get('command') !== '/aegis') return null
    task = p.get('text')?.trim() ?? ''
    team = p.get('team_id') ?? ''
    user = p.get('user_id') ?? ''
    channel = p.get('channel_id') ?? ''
    eventId = await sha256Hex(`v0:${timestamp}:${raw}`)
    threadTs = undefined
  } else if (contentType.includes('application/json')) {
    let obj: Record<string, unknown>
    try { obj = JSON.parse(raw) as Record<string, unknown> } catch { return null }
    if (!obj || typeof obj !== 'object' || Array.isArray(obj)) return null
    if (obj.type === 'url_verification') {
      return typeof obj.challenge === 'string' && obj.challenge.length <= 256
        ? { kind: 'challenge', challenge: obj.challenge } : null
    }
    if (obj.type !== 'event_callback') return { kind: 'ignore' }
    const e = obj.event as Record<string, unknown> | null
    if (!e || e.type !== 'app_mention' || e.subtype || e.bot_id) return { kind: 'ignore' }
    task = typeof e.text === 'string' ? e.text.replace(/<@[A-Z0-9]+>/g, '').trim() : ''
    team = typeof obj.team_id === 'string' ? obj.team_id : ''
    user = typeof e.user === 'string' ? e.user : ''
    channel = typeof e.channel === 'string' ? e.channel : ''
    eventId = typeof obj.event_id === 'string' ? obj.event_id : ''
    threadTs = typeof e.ts === 'string' ? e.ts : undefined
  } else return null
  if (!task || task.length > SLACK_TASK_MAX || !IDENTIFIER.test(channel) || !EVENT_ID.test(eventId)) return null
  return { kind: 'task', job: {
    task, scope: 'slack:answer', slack: { team_id: team, user_id: user, event_id: eventId },
    channel, threadTs,
  } }
}
