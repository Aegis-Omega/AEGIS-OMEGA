import { callConstitutional } from '@shared/lib/constitutional-ai'

const PLATFORMS = ['TikTok', 'YouTube Shorts', 'Instagram Reels', 'Snapchat Spotlight'] as const

export type Platform = (typeof PLATFORMS)[number]

export interface PlatformRanking {
  platform: Platform
  score: number
  reason: string
  best_for: string
}

export interface MatcherInput {
  niche: string
  content_style: string
  target_age: string
  posting_frequency: string
  monetisation_goal: string
  current_following: string
}

const SYSTEM_PROMPT = `You are a short-form video platform expert.
Given a creator's profile, rank these platforms: ${PLATFORMS.join(', ')}.
Respond ONLY as valid JSON — an array of objects with keys:
  "platform" (one of the platforms above),
  "score" (integer 1-10, higher = better fit),
  "reason" (one sentence why),
  "best_for" (2-4 word label e.g. "viral dance content").
Sort descending by score. No markdown, no explanation outside the JSON array.`

export async function rankPlatforms(input: MatcherInput): Promise<PlatformRanking[]> {
  const userMessage = `
Niche: ${input.niche}
Content style: ${input.content_style}
Target age group: ${input.target_age}
Posting frequency: ${input.posting_frequency}
Monetisation goal: ${input.monetisation_goal}
Current following size: ${input.current_following}
`.trim()

  const result = await callConstitutional<unknown>({ systemPrompt: SYSTEM_PROMPT, userMessage, product: 'platform-picker' })
  const parsed = result.data
  const arr: unknown[] = Array.isArray(parsed)
    ? parsed
    : ((parsed as Record<string, unknown[]>)[Object.keys(parsed as object)[0]] ?? [])
  return arr as PlatformRanking[]
}
