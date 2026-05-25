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
}

export interface HookInput {
  niche: string
  platform: Platform
  topic: string
  tone: Tone
}

const SYSTEM_PROMPT = `You are a viral short-form content strategist with deep expertise in TikTok, YouTube Shorts, and Instagram Reels.

Given a creator's niche, target platform, topic, and tone, generate exactly 10 viral hook options.

Respond ONLY as valid JSON — an array of exactly 10 objects with these keys:
  "hook" (the complete opening hook sentence, max 15 words),
  "type" (one of: Curiosity gap, Controversy, Social proof, Number/list, Pain point, Bold claim, Story opener, Question, Direct value, Pattern interrupt),
  "platform_fit" (2-5 word label, e.g. "TikTok viral format"),
  "score" (integer 1-10, higher = more likely to stop the scroll).

Sort descending by score. Vary the types — do not repeat a type more than twice. No markdown, no explanation outside the JSON array.`

export async function generateHooks(input: HookInput): Promise<HookResult[]> {
  const userMessage = `
Niche: ${input.niche}
Platform: ${input.platform}
Topic: ${input.topic}
Tone: ${input.tone}
`.trim()

  const result = await callConstitutional<unknown>({ systemPrompt: SYSTEM_PROMPT, userMessage, product: 'hook-generator' })
  const parsed = result.data
  const arr: unknown[] = Array.isArray(parsed)
    ? parsed
    : ((parsed as Record<string, unknown[]>)[Object.keys(parsed as object)[0]] ?? [])
  return arr as HookResult[]
}
