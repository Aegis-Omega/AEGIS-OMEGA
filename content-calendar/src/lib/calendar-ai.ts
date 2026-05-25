import { callConstitutional } from '@shared/lib/constitutional-ai'
import { mintToken } from '@shared/lib/proof-ledger'

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
  platform: string
  content_pillar: string
  hook: string
  format: string
  notes: string
}

export interface WeekPlan {
  week: number
  theme: string
  posts: DayPost[]
}

const SYSTEM_PROMPT = `You are an expert short-form content strategist.

Given a creator's niche, platforms, posting frequency, and 3 content pillars, generate a 4-week content calendar.

Respond ONLY as valid JSON — an object with key "weeks" containing an array of 4 week objects, each with:
  "week" (integer 1-4),
  "theme" (2-5 word week theme),
  "posts" (array of post objects based on the posting frequency).

Each post object:
  "day" (day of week 1=Mon to 7=Sun),
  "platform" (one of the specified platforms),
  "content_pillar" (which of the 3 pillars),
  "hook" (opening hook sentence, max 12 words),
  "format" (e.g. Talking head, B-roll, Tutorial, Duet, POV),
  "notes" (1 brief production tip).

Space posts evenly across the week. Rotate content pillars. No markdown outside JSON.`

export async function generateCalendar(input: CalendarInput): Promise<WeekPlan[]> {
  const userMessage = `
Niche: ${input.niche}
Platforms: ${input.platforms}
Posting frequency: ${input.frequency}
Content pillar 1: ${input.pillar1}
Content pillar 2: ${input.pillar2}
Content pillar 3: ${input.pillar3}
`.trim()

  const result = await callConstitutional<{ weeks?: WeekPlan[] } | WeekPlan[]>({
    systemPrompt: SYSTEM_PROMPT,
    userMessage,
  })
  await mintToken(result.audit, 'content-calendar')
  const parsed = result.data
  return Array.isArray(parsed) ? parsed : (parsed.weeks ?? [])
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
