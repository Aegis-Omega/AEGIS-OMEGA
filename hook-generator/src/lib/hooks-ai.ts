import { callConstitutional } from '@shared/lib/constitutional-ai'

export type Platform = 'TikTok' | 'YouTube Shorts' | 'Instagram Reels' | 'All platforms'
export type Tone = 'Entertaining' | 'Educational' | 'Controversial' | 'Inspirational' | 'Relatable'
export type HookType =
  | 'Curiosity gap'
  | 'Controversy'
  | 'Social proof'
  | 'Number/list'
  | 'Pain point'
  | 'Bold claim'
  | 'Story opener'
  | 'Question'
  | 'Direct value'
  | 'Pattern interrupt'

export interface HookResult {
  hook: string
  type: HookType
  platform_fit: string
  score: number
  why?: string
}

export interface HookInput {
  niche: string
  platform: Platform
  topic: string
  tone: Tone
}

const SYSTEM_PROMPT = `You are a viral content strategist who has studied 10,000+ viral short-form videos. You understand the psychology of scroll-stopping content.

Think step by step:
1. Identify what makes this topic emotionally compelling
2. Consider which hook types work best for this platform and niche
3. Apply the top psychological triggers: curiosity gap, social proof, controversy, personal transformation, fear of missing out

Then output ONLY valid JSON (no markdown):
{"hooks":[{"hook":"...","type":"curiosity|controversy|social_proof|number|pain_point|transformation|fomo","platform_fit":X,"score":X,"why":"one sentence explanation"},...]}

Generate exactly 10 hooks, ranked by viral potential (score 1-10).`

export async function generateHooks(input: HookInput): Promise<HookResult[]> {
  const userMessage = `
Niche: ${input.niche}
Platform: ${input.platform}
Topic: ${input.topic}
Tone: ${input.tone}
`.trim()

  const constitutional = await callConstitutional<unknown>({ systemPrompt: SYSTEM_PROMPT, userMessage })
  const parsed = constitutional.data
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const obj = parsed as Record<string, unknown>
    if (Array.isArray(obj['hooks'])) return obj['hooks'] as HookResult[]
  }
  const arr: unknown[] = Array.isArray(parsed)
    ? parsed
    : ((parsed as Record<string, unknown[]>)[Object.keys(parsed as object)[0]] ?? [])
  return arr as HookResult[]
}
