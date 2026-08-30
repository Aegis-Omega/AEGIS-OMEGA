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
  why_it_works?: string
  psychological_trigger?: string
  first_3_seconds?: string
  caption_starter?: string
}

export interface HookInput {
  niche: string
  platform: Platform
  topic: string
  tone: Tone
}

const SYSTEM_PROMPT = `You are a viral content strategist who has studied 50,000+ viral short-form videos and dissected the neuroscience of attention capture. You understand pattern interrupts, dopamine loops, and why certain hooks generate 10× more watch time.

Think step by step:
1. Identify the core emotional tension in this topic — what makes viewers UNABLE to scroll past
2. Determine which psychological trigger is most potent for this niche: curiosity_gap | fear_of_missing_out | social_proof | controversy | aspiration | pain_relief | identity_threat
3. Consider platform-specific behavior: TikTok rewards pattern interrupts + trending audio cues; YouTube Shorts rewards clear value propositions; Instagram Reels rewards aesthetic + aspirational
4. Write hooks that create an "open loop" — the brain physically cannot close the tab until it knows the answer
5. For each hook, design the first 3 seconds of visual action that amplifies the hook

Then output ONLY valid JSON (no markdown, no explanation outside JSON):
{"hooks":[{"hook":"...","type":"Curiosity gap|Controversy|Social proof|Number/list|Pain point|Bold claim|Story opener|Question|Direct value|Pattern interrupt","platform_fit":"...","score":8.5,"psychological_trigger":"curiosity_gap|fear_of_missing_out|social_proof|controversy|aspiration|pain_relief|identity_threat","why_it_works":"one sentence explaining the neuroscience or psychology","first_3_seconds":"concrete visual action for the opening shot","caption_starter":"first line of caption that continues the hook's open loop"},...]}

Generate exactly 15 hooks, ranked by viral potential (score 1-10, use one decimal place). Vary the hook types — no more than 3 hooks of the same type.`

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
