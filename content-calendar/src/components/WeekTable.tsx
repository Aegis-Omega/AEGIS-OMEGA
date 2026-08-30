import { useState } from 'react'
import { Copy, Check, Clock, Hash } from 'lucide-react'
import type { WeekPlan } from '../lib/calendar-ai.js'

const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']

const PILLAR_COLORS = [
  'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'bg-purple-500/15 text-purple-300 border-purple-500/25',
  'bg-orange-500/15 text-orange-300 border-orange-500/25',
]

const DIFFICULTY_STYLES: Record<string, string> = {
  easy:   'bg-green-500/10 text-green-400',
  medium: 'bg-yellow-500/10 text-yellow-400',
  hard:   'bg-red-500/10 text-red-400',
}

interface WeekTableProps {
  week: WeekPlan
  pillars: [string, string, string]
}

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(text)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <button
      onClick={handleCopy}
      aria-label="Copy post to clipboard"
      className="opacity-0 group-hover:opacity-100 text-cal-muted hover:text-cal-glow transition-all shrink-0"
    >
      {copied ? <Check size={13} className="text-green-400" /> : <Copy size={13} />}
    </button>
  )
}

export function WeekTable({ week, pillars }: WeekTableProps) {
  return (
    <div className="bg-cal-surface border border-cal-border rounded-2xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-3 border-b border-cal-border">
        <span className="text-xs font-medium text-cal-muted">Week {week.week}</span>
        <span className="font-semibold text-cal-text text-sm">{week.theme}</span>
      </div>
      <div className="divide-y divide-cal-border">
        {week.posts.map((post, i) => {
          const pillarLabel = post.content_pillar ?? post.pillar ?? ''
          const pillarIdx = pillars.indexOf(pillarLabel)
          const colorClass = PILLAR_COLORS[pillarIdx] ?? PILLAR_COLORS[0]
          const note = post.notes ?? post.production_note ?? ''
          const hashtagText = post.hashtags?.join(' ') ?? ''
          const copyText = [
            `${DAY_NAMES[post.day] ?? `D${post.day}`} | ${post.platform ?? ''} | ${pillarLabel}`,
            `Hook: "${post.hook}"`,
            `Format: ${post.format}`,
            note,
            post.cta ? `CTA: ${post.cta}` : '',
            hashtagText,
          ].filter(Boolean).join('\n')

          return (
            <div key={i} className="px-5 py-3 flex flex-col gap-1.5 group">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-xs font-mono font-semibold text-cal-glow w-8">
                  {DAY_NAMES[post.day] ?? `D${post.day}`}
                </span>
                <span className="text-xs text-cal-muted">{post.platform}</span>
                <span className={`text-xs border rounded-full px-2 py-0.5 ${colorClass}`}>
                  {pillarLabel}
                </span>
                <span className="text-xs text-cal-muted">{post.format}</span>
                {post.difficulty && (
                  <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${DIFFICULTY_STYLES[post.difficulty] ?? ''}`}>
                    {post.difficulty}
                  </span>
                )}
                {post.optimal_time && (
                  <span className="flex items-center gap-1 text-xs text-cal-muted ml-auto">
                    <Clock size={10} />
                    {post.optimal_time}
                  </span>
                )}
                {!post.optimal_time && <span className="ml-auto" />}
                <CopyButton text={copyText} />
              </div>

              <p className="text-cal-text text-sm ml-10">&ldquo;{post.hook}&rdquo;</p>

              {note && <p className="text-cal-muted text-xs ml-10">{note}</p>}

              {post.cta && (
                <p className="text-cal-glow/70 text-xs ml-10 font-medium">→ {post.cta}</p>
              )}

              {post.hashtags && post.hashtags.length > 0 && (
                <div className="ml-10 flex items-center gap-1 flex-wrap mt-0.5">
                  <Hash size={10} className="text-cal-muted shrink-0" />
                  {post.hashtags.map((tag, ti) => (
                    <span key={ti} className="text-xs text-cal-muted/70 hover:text-cal-glow transition-colors cursor-default">
                      {tag.startsWith('#') ? tag : `#${tag}`}
                    </span>
                  ))}
                </div>
              )}
            </div>
          )
        })}
      </div>
    </div>
  )
}
