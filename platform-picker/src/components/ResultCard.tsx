import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
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
  const isTop = rank === 0

  const handleCopy = async () => {
    const text = `${r.platform} — Score: ${r.score}/10\n${r.reason}\nBest for: ${r.best_for}`
    await navigator.clipboard.writeText(text)
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
      <p className="text-brand-glow/80 text-xs font-medium">{r.best_for}</p>
    </div>
  )
}
