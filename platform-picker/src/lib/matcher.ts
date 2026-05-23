import { callConstitutional } from '@shared/lib/constitutional-ai'
export type { ConstitutionalResult } from '@shared/lib/constitutional-ai'

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

export interface RankedResult {
  rankings: PlatformRanking[]
  chain_hash: string
  call_id: string
  martingale_anchored: boolean
  session_calls: number
}

export async function rankPlatforms(input: MatcherInput): Promise<RankedResult> {
  const userMessage = `
Niche: ${input.niche}
Content style: ${input.content_style}
Target age group: ${input.target_age}
Posting frequency: ${input.posting_frequency}
Monetisation goal: ${input.monetisation_goal}
Current following size: ${input.current_following}
`.trim()

  const constitutional = await callConstitutional<unknown>({ systemPrompt: SYSTEM_PROMPT, userMessage })
  const parsed = constitutional.data

  let rankings: PlatformRanking[]
  if (parsed && typeof parsed === 'object' && !Array.isArray(parsed)) {
    const obj = parsed as Record<string, unknown>
    rankings = Array.isArray(obj['rankings']) ? obj['rankings'] as PlatformRanking[] : []
  } else {
    const arr: unknown[] = Array.isArray(parsed)
      ? parsed
      : ((parsed as Record<string, unknown[]>)[Object.keys(parsed as object)[0]] ?? [])
    rankings = arr as PlatformRanking[]
  }

  return {
    rankings,
    chain_hash: constitutional.audit.chain_hash,
    call_id: constitutional.audit.call_id,
    martingale_anchored: constitutional.martingale_anchored,
    session_calls: constitutional.session_calls,
  }
}
