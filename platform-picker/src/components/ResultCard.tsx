import { useState } from 'react'
import { Copy, Check, ChevronDown, ChevronUp, TrendingUp, Clock } from 'lucide-react'
import type { PlatformRanking } from '../lib/matcher.js'

const EMOJI: Record<string, string> = {
  'TikTok': '🎵',
  'YouTube Shorts': '▶️',
  'Instagram Reels': '📸',
  'Snapchat Spotlight': '👻',
}

interface ResultCardProps {
  ranking: PlatformRanking
  rank: number
}

export function ResultCard({ ranking: r, rank }: ResultCardProps) {
  const [copied, setCopied] = useState(false)
  const [expanded, setExpanded] = useState(rank === 0)
  const isTop = rank === 0
  const hasDetails = !!(r.strengths?.length || r.weaknesses?.length || r.action_steps?.length || r.growth_timeline)

  const handleCopy = async () => {
    const lines = [
      `${r.platform} — Score: ${r.score}/10`,
      r.reason ?? '',
      r.best_for ? `Best for: ${r.best_for}` : '',
      r.strengths?.length ? `Strengths: ${r.strengths.join(', ')}` : '',
      r.growth_timeline ? `Timeline: ${r.growth_timeline}` : '',
    ].filter(Boolean)
    await navigator.clipboard.writeText(lines.join('\n'))
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`bg-brand-surface border rounded-2xl p-5 transition-all ${
      isTop ? 'border-brand-glow/50 shadow-lg shadow-brand-accent/10' : 'border-brand-border'
    }`}>
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center gap-2">
          <span className="text-xl">{EMOJI[r.platform] ?? '📱'}</span>
          <span className="font-semibold text-brand-text">{r.platform}</span>
          {isTop && (
            <span className="text-xs bg-brand-accent/20 text-brand-glow border border-brand-glow/30 rounded-full px-2 py-0.5 font-medium">
              Best match
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <div className="text-2xl font-bold text-brand-glow">
            {r.score}<span className="text-sm text-brand-muted font-normal">/10</span>
          </div>
          <button
            onClick={handleCopy}
            className="text-brand-muted hover:text-brand-glow transition-colors"
            title="Copy result"
          >
            {copied ? <Check size={15} className="text-green-400" /> : <Copy size={15} />}
          </button>
        </div>
      </div>

      <div className="w-full bg-brand-border rounded-full h-1.5 mb-3">
        <div
          className="bg-brand-glow h-1.5 rounded-full transition-all"
          style={{ width: `${r.score * 10}%` }}
        />
      </div>

      <p className="text-brand-muted text-sm mb-1">{r.reason}</p>
      {r.best_for && <p className="text-brand-glow/80 text-xs font-medium">{r.best_for}</p>}

      {(r.strengths?.length || r.weaknesses?.length) && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {r.strengths?.map((s, i) => (
            <span key={i} className="text-xs bg-green-500/10 text-green-400 border border-green-500/20 rounded-full px-2 py-0.5">
              + {s}
            </span>
          ))}
          {r.weaknesses?.map((w, i) => (
            <span key={i} className="text-xs bg-red-500/10 text-red-400 border border-red-500/20 rounded-full px-2 py-0.5">
              − {w}
            </span>
          ))}
        </div>
      )}

      {hasDetails && (r.action_steps?.length || r.growth_timeline) && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-3 flex items-center gap-1 text-xs text-brand-muted hover:text-brand-glow transition-colors"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? 'Hide action plan' : 'Show action plan'}
        </button>
      )}

      {expanded && (r.action_steps?.length || r.growth_timeline) && (
        <div className="mt-3 space-y-3 border-t border-brand-border pt-3">
          {r.action_steps?.length ? (
            <div>
              <div className="flex items-center gap-1.5 mb-2">
                <TrendingUp size={12} className="text-brand-accent" />
                <span className="text-xs font-semibold text-brand-muted uppercase tracking-wide">Action plan</span>
              </div>
              <ol className="space-y-1.5">
                {r.action_steps.map((step, i) => (
                  <li key={i} className="flex gap-2 text-xs text-brand-text">
                    <span className="text-brand-glow font-bold shrink-0">{i + 1}.</span>
                    <span>{step}</span>
                  </li>
                ))}
              </ol>
            </div>
          ) : null}
          {r.growth_timeline && (
            <div className="flex gap-2">
              <Clock size={12} className="text-brand-accent shrink-0 mt-0.5" />
              <p className="text-xs text-brand-muted">{r.growth_timeline}</p>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
