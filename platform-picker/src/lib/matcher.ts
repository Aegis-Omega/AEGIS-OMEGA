import { callDashScope } from '@shared/lib/dashscope'

const PLATFORMS = ['TikTok', 'YouTube Shorts', 'Instagram Reels', 'Snapchat Spotlight'] as const

export type Platform = (typeof PLATFORMS)[number]

export interface PlatformRanking {
  platform: Platform
  score: number
  reasoning?: string
  reason?: string
  strengths?: string[]
  weaknesses?: string[]
  best_for?: string
}

export interface MatcherInput {
  niche: string
  content_style: string
  target_age: string
  posting_frequency: string
  monetisation_goal: string
  current_following: string
}

const SYSTEM_PROMPT = `You are an expert short-form content strategist with deep knowledge of TikTok, YouTube Shorts, Instagram Reels, and Snapchat Spotlight algorithms.

Think step by step:
1. First assess the creator's content type and audience fit for each platform
2. Consider monetisation potential for their specific goal
3. Evaluate the competitive landscape for their niche on each platform
4. Score each dimension: audience_fit (0-10), monetisation (0-10), competition (0-10, higher = less competition = better), growth_potential (0-10)

Then output ONLY valid JSON in this exact format (no markdown, no explanation):
{"rankings":[{"platform":"TikTok","score":X,"reasoning":"...","strengths":["..."],"weaknesses":["..."]},...],"recommendation":"...","key_insight":"one sentence summary"}`

export interface MatcherResponse {
  rankings: PlatformRanking[]
  recommendation: string
  key_insight: string
}

export async function rankPlatforms(input: MatcherInput): Promise<PlatformRanking[]> {
  const userMessage = `
Niche: ${input.niche}
Content style: ${input.content_style}
Target age group: ${input.target_age}
Posting frequency: ${input.posting_frequency}
Monetisation goal: ${input.monetisation_goal}
Current following size: ${input.current_following}
`.trim()

  const parsed = await callDashScope<unknown>({ systemPrompt: SYSTEM_PROMPT, userMessage })
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const obj = parsed as Record<string, unknown>
    if (Array.isArray(obj['rankings'])) return obj['rankings'] as PlatformRanking[]
  }
  const arr: unknown[] = Array.isArray(parsed)
    ? parsed
    : ((parsed as Record<string, unknown[]>)[Object.keys(parsed as object)[0]] ?? [])
  return arr as PlatformRanking[]
}
