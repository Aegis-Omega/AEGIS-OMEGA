import { callDashScope } from '@shared/lib/dashscope'

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
}

export interface WeekPlan {
  week: number
  theme: string
  posts: DayPost[]
}

const SYSTEM_PROMPT = `You are a content planning expert who has helped 500+ creators build consistent audiences. You understand content pillars, posting rhythms, and what drives sustained growth.

Think step by step:
1. Map each content pillar to specific angles that serve the audience
2. Plan variety: mix educational, entertaining, and promotional content
3. Create hooks that make each post scroll-stopping
4. Add specific production notes that save filming time

Then output ONLY valid JSON (no markdown):
{"weeks":[{"week":1,"posts":[{"day":1,"pillar":"educational|entertaining|promotional","topic":"...","hook":"...","format":"talking_head|screen_record|broll|text_overlay|duet","production_note":"...","cta":"..."},...]},...]}
`

export async function generateCalendar(input: CalendarInput): Promise<WeekPlan[]> {
  const userMessage = `
Niche: ${input.niche}
Platforms: ${input.platforms}
Posting frequency: ${input.frequency}
Content pillar 1: ${input.pillar1}
Content pillar 2: ${input.pillar2}
Content pillar 3: ${input.pillar3}
`.trim()

  const parsed = await callDashScope<{ weeks?: WeekPlan[] } | WeekPlan[]>({
    systemPrompt: SYSTEM_PROMPT,
    userMessage,
  })
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
