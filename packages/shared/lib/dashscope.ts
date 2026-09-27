export interface DashScopeCallOpts {
  systemPrompt: string
  userMessage: string
  defaultModel?: string
}

export async function callDashScope<T>(opts: DashScopeCallOpts): Promise<T> {
  const apiKey = import.meta.env.VITE_DASHSCOPE_API_KEY as string | undefined
  if (!apiKey) throw new Error('VITE_DASHSCOPE_API_KEY is not configured')

  const model =
    (import.meta.env.VITE_DASHSCOPE_MODEL as string | undefined) ??
    opts.defaultModel ??
    'qwen-plus'

  const base =
    ((import.meta.env.VITE_DASHSCOPE_BASE_URL as string | undefined) ??
      'https://dashscope-intl.aliyuncs.com/compatible-mode/v1').replace(/\/$/, '')

  const res = await fetch(
    `${base}/chat/completions`,
    {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${apiKey}` },
      body: JSON.stringify({
        model,
        response_format: { type: 'json_object' },
        messages: [
          { role: 'system', content: opts.systemPrompt },
          { role: 'user', content: opts.userMessage },
        ],
      }),
      signal: AbortSignal.timeout(60_000),
    },
  )

  if (!res.ok) {
    const detail = (await res.text()).slice(0, 2_048)
    throw new Error(`DashScope ${res.status}: ${detail}`)
  }

  const data = (await res.json()) as { choices: { message: { content: string } }[] }
  let raw = data.choices[0]?.message?.content ?? ''
  raw = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()
  return JSON.parse(raw) as T
}
