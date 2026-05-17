import { useState } from 'react'
import { Copy, Check } from 'lucide-react'
import type { HookResult } from '../lib/hooks-ai.js'

const TYPE_COLORS: Record<string, string> = {
  'Curiosity gap':    'bg-purple-500/15 text-purple-300 border-purple-500/30',
  'Controversy':      'bg-red-500/15 text-red-300 border-red-500/30',
  'Social proof':     'bg-green-500/15 text-green-300 border-green-500/30',
  'Number/list':      'bg-blue-500/15 text-blue-300 border-blue-500/30',
  'Pain point':       'bg-orange-500/15 text-orange-300 border-orange-500/30',
  'Bold claim':       'bg-yellow-500/15 text-yellow-300 border-yellow-500/30',
  'Story opener':     'bg-pink-500/15 text-pink-300 border-pink-500/30',
  'Question':         'bg-cyan-500/15 text-cyan-300 border-cyan-500/30',
  'Direct value':     'bg-teal-500/15 text-teal-300 border-teal-500/30',
  'Pattern interrupt':'bg-indigo-500/15 text-indigo-300 border-indigo-500/30',
}

interface HookCardProps {
  hook: HookResult
  rank: number
}

export function HookCard({ hook: h, rank }: HookCardProps) {
  const [copied, setCopied] = useState(false)
  const isTop = rank === 0
  const colorClass = TYPE_COLORS[h.type] ?? 'bg-hook-border text-hook-muted border-hook-border'

  const handleCopy = async () => {
    await navigator.clipboard.writeText(h.hook)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  return (
    <div className={`bg-hook-surface border rounded-2xl p-5 group transition-all ${
      isTop ? 'border-hook-glow/50 shadow-lg shadow-hook-accent/10' : 'border-hook-border'
    }`}>
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs border rounded-full px-2.5 py-0.5 font-medium ${colorClass}`}>
            {h.type}
          </span>
          {isTop && (
            <span className="text-xs bg-hook-accent/20 text-hook-glow border border-hook-glow/30 rounded-full px-2 py-0.5 font-medium">
              Top hook
            </span>
          )}
          <span className="text-xs text-hook-muted">{h.platform_fit}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-hook-glow font-bold text-sm">{h.score}<span className="text-hook-muted font-normal">/10</span></span>
          <button
            onClick={handleCopy}
            className="text-hook-muted hover:text-hook-glow transition-colors"
            title="Copy hook"
          >
            {copied ? <Check size={15} className="text-green-400" /> : <Copy size={15} />}
          </button>
        </div>
      </div>

      <p className="text-hook-text text-sm leading-relaxed font-medium">"{h.hook}"</p>

      <div className="mt-2 w-full bg-hook-border rounded-full h-1">
        <div
          className="bg-hook-accent h-1 rounded-full"
          style={{ width: `${h.score * 10}%` }}
        />
      </div>
    </div>
  )
}
