import { callConstitutional } from '@shared/lib/constitutional-ai'

export interface CalendarInput {
  niche: string
  platforms: string
  frequency: string
  pillar1: string
  pillar2: string
  pillar3: string
}

export interface DayPost {
  day: number
  platform?: string
  content_pillar?: string
  pillar?: 'educational' | 'entertaining' | 'promotional' | string
  topic?: string
  hook: string
  format: string
  notes?: string
  production_note?: string
  cta?: string
  hashtags?: string[]
  optimal_time?: string
  difficulty?: 'easy' | 'medium' | 'hard'
}

export interface WeekPlan {
  week: number
  theme: string
  posts: DayPost[]
}

const SYSTEM_PROMPT = `You are a content strategist who has built editorial calendars for 500+ creators across TikTok, YouTube Shorts, and Instagram Reels. You understand content sequencing, pillar balancing, production efficiency, and how to build audience habits through consistent posting rhythms.

Think step by step:
1. Map each pillar to 3–5 specific recurring angles that compound over time (the audience starts anticipating them)
2. Sequence posts strategically: build trust (educational) → entertain → convert (promotional), never two promotional posts back-to-back
3. Write hooks that create an open loop or immediate curiosity
4. Specify optimal posting times based on platform norms and niche audience behavior
5. Rate production difficulty honestly so creators can batch easy posts and prep harder ones in advance
6. Include platform-native hashtags (7–12 relevant tags) that balance reach and niche discoverability

Then output ONLY valid JSON (no markdown, no explanation outside JSON):
{"weeks":[{"week":1,"theme":"week theme name","posts":[{"day":1,"platform":"...","pillar":"educational|entertaining|promotional","topic":"...","hook":"...","format":"talking_head|screen_record|broll|text_overlay|duet|carousel","production_note":"specific filming or editing tip to save time","cta":"exact call-to-action text","optimal_time":"e.g. 7–9 PM local or Tue 6 PM","difficulty":"easy|medium|hard","hashtags":["#tag1","#tag2","#tag3","#tag4","#tag5","#tag6","#tag7"]},...]},...]}

Generate exactly 4 weeks. Each week should have posts matching the creator's posting frequency. Vary formats — no more than 40% of posts should use the same format.`

export async function generateCalendar(input: CalendarInput): Promise<WeekPlan[]> {
  const userMessage = `
Niche: ${input.niche}
Platforms: ${input.platforms}
Posting frequency: ${input.frequency}
Content pillar 1: ${input.pillar1}
Content pillar 2: ${input.pillar2}
Content pillar 3: ${input.pillar3}
`.trim()

  const constitutional = await callConstitutional<{ weeks?: WeekPlan[] } | WeekPlan[]>({
    systemPrompt: SYSTEM_PROMPT,
    userMessage,
  })
  const parsed = constitutional.data
  const weeks: WeekPlan[] = Array.isArray(parsed) ? parsed : (parsed.weeks ?? [])
  // Normalize: theme is required by calendarToText but may be absent from model output
  return weeks.map(w => ({ ...w, theme: w.theme ?? `Week ${w.week}` }))
}

const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

export function calendarToText(weeks: WeekPlan[], input: CalendarInput): string {
  const lines: string[] = [
    `CONTENT CALENDAR — ${input.niche.toUpperCase()}`,
    `Platforms: ${input.platforms} | Frequency: ${input.frequency}`,
    `Pillars: ${input.pillar1} · ${input.pillar2} · ${input.pillar3}`,
    '',
  ]
  for (const week of weeks) {
    lines.push(`── WEEK ${week.week}: ${week.theme.toUpperCase()} ──`)
    for (const post of week.posts) {
      lines.push(`  ${DAY_NAMES[post.day] ?? `Day${post.day}`} | ${post.platform} | ${post.content_pillar}`)
      lines.push(`  Hook: "${post.hook}"`)
      lines.push(`  Format: ${post.format} | ${post.notes}`)
      lines.push('')
    }
  }
  return lines.join('\n')
}
