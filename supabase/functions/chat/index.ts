import { CORS } from '../_shared/cors.ts'

const DASHSCOPE_API_KEY = Deno.env.get('DASHSCOPE_API_KEY') ?? ''
const DASHSCOPE_URL = 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1/chat/completions'
const DEFAULT_SYSTEM = `You are the AEGIS Omega AI assistant helping content creators. Be concise, direct, and practical.`

Deno.serve(async (req) => {
  if (req.method === 'OPTIONS') return new Response(null, { headers: CORS })
  if (req.method !== 'POST') return new Response(JSON.stringify({ error: 'Method not allowed' }), { status: 405, headers: CORS })

  try {
    const { message, history = [], system = DEFAULT_SYSTEM } = await req.json() as {
      message: string
      history?: { role: string; content: string }[]
      system?: string
    }

    if (!message?.trim()) {
      return new Response(JSON.stringify({ error: 'message required' }), { status: 400, headers: { ...CORS, 'Content-Type': 'application/json' } })
    }

    const messages = [
      { role: 'system', content: system },
      ...history.filter(m => m.role === 'user' || m.role === 'assistant').slice(-8),
      { role: 'user', content: message },
    ]

    const resp = await fetch(DASHSCOPE_URL, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${DASHSCOPE_API_KEY}`,
      },
      body: JSON.stringify({
        model: 'qwen-plus',
        messages,
        max_tokens: 512,
        temperature: 0.7,
      }),
    })

    if (!resp.ok) {
      const err = await resp.text()
      console.error('DashScope error:', resp.status, err)
      return new Response(JSON.stringify({ error: 'AI unavailable', reply: "I'm having trouble connecting right now. Try again in a moment." }), {
        status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
      })
    }

    const data = await resp.json()
    const reply = data.choices?.[0]?.message?.content ?? "Sorry, I didn't get a response."

    return new Response(JSON.stringify({ reply }), {
      headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  } catch (e) {
    console.error('chat function error:', e)
    return new Response(JSON.stringify({ reply: "Something went wrong. Please try again." }), {
      status: 200, headers: { ...CORS, 'Content-Type': 'application/json' },
    })
  }
})
