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

  const res = await fetch(
    'https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions',
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

  if (!res.ok) throw new Error(`DashScope ${res.status}: ${await res.text()}`)

  const data = (await res.json()) as { choices: { message: { content: string } }[] }
  let raw = data.choices[0]?.message?.content ?? ''
  raw = raw.replace(/^```(?:json)?\s*/i, '').replace(/\s*```$/, '').trim()
  return JSON.parse(raw) as T
}
