import express from 'express'
import path from 'path'
import { fileURLToPath } from 'url'
import Anthropic from '@anthropic-ai/sdk'
import { AnthropicVertex } from '@anthropic-ai/vertex-sdk'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const PORT = parseInt(process.env.PORT ?? '8080')

// Vertex AI when GCP project is configured; Anthropic direct otherwise
const GCP_PROJECT = process.env.GOOGLE_CLOUD_PROJECT ?? ''
const GCP_REGION  = process.env.GOOGLE_CLOUD_REGION ?? 'us-east5'

const client = GCP_PROJECT
  ? new AnthropicVertex({ projectId: GCP_PROJECT, region: GCP_REGION })
  : new Anthropic({ apiKey: process.env.ANTHROPIC_API_KEY ?? '' })

const MODEL      = process.env.CLAUDE_MODEL      ?? 'claude-sonnet-4-6'
const MAX_TOKENS = parseInt(process.env.CLAUDE_MAX_TOKENS ?? '2048')

// Optional per-IP rate limiting (requests per minute, 0 = off)
const RATE_LIMIT = parseInt(process.env.RATE_LIMIT_RPM ?? '20')
const ipCounters  = new Map<string, { count: number; reset: number }>()

function checkRateLimit(ip: string): boolean {
  if (!RATE_LIMIT) return true
  const now = Date.now()
  const entry = ipCounters.get(ip)
  if (!entry || entry.reset < now) {
    ipCounters.set(ip, { count: 1, reset: now + 60_000 })
    return true
  }
  if (entry.count >= RATE_LIMIT) return false
  entry.count++
  return true
}

interface ChatMessage { role: 'user' | 'assistant'; content: string }
interface StreamRequest { messages: ChatMessage[]; max_tokens?: number }

const app = express()
app.use(express.json({ limit: '256kb' }))

app.get('/health', (_, res) => {
  res.json({ ok: true, model: MODEL, vertex: Boolean(GCP_PROJECT) })
})

// Bridge telemetry compat — sovereign-omega polling
app.get('/telemetry', (_, res) => {
  res.json({ status: 'cloud-run', bridge: false, model: MODEL, vertex: Boolean(GCP_PROJECT) })
})

// Bridge event compat — cockpit posts governance events here
app.post('/event', (_, res) => res.json({ ok: true }))

// Main inference endpoint — consumed by cockpit's streamClaude()
app.post('/claude/stream', async (req, res) => {
  const ip = (req.headers['x-forwarded-for'] as string)?.split(',')[0].trim() ?? req.ip ?? 'unknown'

  if (!checkRateLimit(ip)) {
    res.status(429).json({ error: 'Rate limit exceeded — try again in a minute.' })
    return
  }

  const body = req.body as StreamRequest
  const messages = (body.messages ?? []).filter(m => m.role !== 'system' as unknown)

  if (!messages.length) {
    res.status(400).json({ error: 'No messages provided.' })
    return
  }

  res.setHeader('Content-Type',  'text/event-stream')
  res.setHeader('Cache-Control', 'no-cache')
  res.setHeader('Connection',    'keep-alive')
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.flushHeaders()

  try {
    const stream = (client as Anthropic).messages.stream({
      model:      MODEL,
      max_tokens: body.max_tokens ?? MAX_TOKENS,
      messages:   messages as Anthropic.MessageParam[],
    })

    for await (const event of stream) {
      if (
        event.type === 'content_block_delta' &&
        event.delta.type === 'text_delta'
      ) {
        res.write(`data: ${JSON.stringify({ delta: event.delta.text })}\n\n`)
      }
    }
    res.write(`data: ${JSON.stringify({ done: true })}\n\n`)
  } catch (err: unknown) {
    const msg = err instanceof Error ? err.message : String(err)
    console.error('Stream error:', msg)
    res.write(`data: ${JSON.stringify({ error: msg })}\n\n`)
  }

  res.end()
})

// OPTIONS preflight
app.options('/claude/stream', (_, res) => {
  res.setHeader('Access-Control-Allow-Origin',  '*')
  res.setHeader('Access-Control-Allow-Methods', 'POST, OPTIONS')
  res.setHeader('Access-Control-Allow-Headers', 'Content-Type')
  res.sendStatus(204)
})

// Serve Cockpit SPA — must be AFTER API routes
const STATIC = path.join(__dirname, '../../dist')
app.use(express.static(STATIC))
app.get('*', (_, res) => res.sendFile(path.join(STATIC, 'index.html')))

app.listen(PORT, '0.0.0.0', () => {
  console.log(`AEGIS Cockpit  port=${PORT}  model=${MODEL}  vertex=${Boolean(GCP_PROJECT)}`)
})
