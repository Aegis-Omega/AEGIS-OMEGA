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
  action_steps?: string[]
  growth_timeline?: string
}

export interface MatcherInput {
  niche: string
  content_style: string
  target_age: string
  posting_frequency: string
  monetisation_goal: string
  current_following: string
}

const SYSTEM_PROMPT = `You are a senior short-form content strategist who has scaled 200+ creator accounts to 100K+ followers. You have deep operational knowledge of TikTok, YouTube Shorts, Instagram Reels, and Snapchat Spotlight — their algorithms, monetisation thresholds, content discovery mechanics, and niche-specific competitive dynamics.

Think step by step:
1. Assess the creator's content type, energy, and format against each platform's dominant content styles
2. Model the monetisation pathway: what specific feature unlocks at what follower milestone on each platform for this goal
3. Evaluate true competitive density — not just "fitness is popular on TikTok" but whether THIS specific angle has whitespace
4. Score holistically (0-10): blend of audience_fit, monetisation_speed, competition_advantage, algorithm_tailwind

Then output ONLY valid JSON (no markdown, no explanation outside JSON):
{"rankings":[{"platform":"TikTok","score":8.5,"reasoning":"2-3 sentence analytical justification","strengths":["specific strength 1","specific strength 2","specific strength 3"],"weaknesses":["specific weakness 1","specific weakness 2"],"best_for":"one sentence on the ideal creator profile for this platform","action_steps":["First concrete action to take this week","Second action in month 1","Third action to hit first monetisation milestone"],"growth_timeline":"realistic milestone timeline: e.g. 1K followers in 3 weeks, 10K in 3 months if posting 5x/week"}],"recommendation":"platform name","key_insight":"one contrarian or non-obvious insight about this creator's specific situation"}`

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
  backend?: string
  fallback_count?: number
  latency_ms?: number
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

  // Normalize: prompt outputs `reasoning`/`strengths`; UI reads `reason`/`best_for`
  rankings = rankings.map(r => ({
    ...r,
    reason: r.reason ?? r.reasoning,
    best_for: r.best_for ?? r.strengths?.[0] ?? r.reasoning ?? '',
  }))

  return {
    rankings,
    chain_hash: constitutional.audit.chain_hash,
    call_id: constitutional.audit.call_id,
    martingale_anchored: constitutional.martingale_anchored,
    session_calls: constitutional.session_calls,
    backend: constitutional.audit.backend,
    fallback_count: constitutional.audit.fallback_count,
    latency_ms: constitutional.audit.latency_ms,
  }
}
