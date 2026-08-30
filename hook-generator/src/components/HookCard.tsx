import { useState } from 'react'
import { Copy, Check, Star, ChevronDown, ChevronUp, Clapperboard, MessageSquare, Zap } from 'lucide-react'
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

const TRIGGER_COLORS: Record<string, string> = {
  curiosity_gap:    'bg-purple-500/10 text-purple-400',
  fear_of_missing_out: 'bg-orange-500/10 text-orange-400',
  social_proof:     'bg-green-500/10 text-green-400',
  controversy:      'bg-red-500/10 text-red-400',
  aspiration:       'bg-blue-500/10 text-blue-400',
  pain_relief:      'bg-yellow-500/10 text-yellow-400',
  identity_threat:  'bg-pink-500/10 text-pink-400',
}

interface HookCardProps {
  hook: HookResult
  rank: number
  isFav: boolean
  onToggleFav: () => void
}

export function HookCard({ hook: h, rank, isFav, onToggleFav }: HookCardProps) {
  const [copied, setCopied] = useState(false)
  const [captionCopied, setCaptionCopied] = useState(false)
  const [expanded, setExpanded] = useState(false)
  const isTop = rank === 0
  const colorClass = TYPE_COLORS[h.type] ?? 'bg-hook-border text-hook-muted border-hook-border'
  const triggerClass = h.psychological_trigger
    ? (TRIGGER_COLORS[h.psychological_trigger] ?? 'bg-hook-border/50 text-hook-muted')
    : null
  const hasDetails = !!(h.why_it_works || h.first_3_seconds || h.caption_starter)

  const handleCopy = async () => {
    await navigator.clipboard.writeText(h.hook)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  const handleCopyCaption = async () => {
    if (!h.caption_starter) return
    await navigator.clipboard.writeText(h.caption_starter)
    setCaptionCopied(true)
    setTimeout(() => setCaptionCopied(false), 2000)
  }

  return (
    <div
      className={`bg-hook-surface border rounded-2xl p-5 hook-card-reveal transition-all ${
        isTop ? 'border-hook-glow/50 shadow-lg shadow-hook-accent/10' : 'border-hook-border'
      }`}
      style={{ animationDelay: `${rank * 60}ms`, animationFillMode: 'both' }}
    >
      <div className="flex items-start justify-between gap-3 mb-3">
        <div className="flex items-center gap-2 flex-wrap">
          <span className={`text-xs border rounded-full px-2.5 py-0.5 font-medium ${colorClass}`}>
            {h.type}
          </span>
          {triggerClass && h.psychological_trigger && (
            <span className={`text-xs rounded-full px-2 py-0.5 font-medium ${triggerClass}`}>
              <Zap size={9} className="inline mr-0.5 -mt-px" />
              {h.psychological_trigger.replace(/_/g, ' ')}
            </span>
          )}
          {isTop && (
            <span className="text-xs bg-hook-accent/20 text-hook-glow border border-hook-glow/30 rounded-full px-2 py-0.5 font-medium">
              Top hook
            </span>
          )}
          <span className="text-xs text-hook-muted">{h.platform_fit}</span>
        </div>
        <div className="flex items-center gap-2 shrink-0">
          <span className="text-hook-glow font-bold text-sm">
            {h.score}<span className="text-hook-muted font-normal">/10</span>
          </span>
          <button
            onClick={onToggleFav}
            aria-label={isFav ? 'Remove from favourites' : 'Add to favourites'}
            className={`transition-colors ${isFav ? 'text-hook-accent' : 'text-hook-muted hover:text-hook-accent'}`}
          >
            <Star size={15} fill={isFav ? 'currentColor' : 'none'} />
          </button>
          <button
            onClick={handleCopy}
            aria-label="Copy hook"
            className="text-hook-muted hover:text-hook-glow transition-colors"
          >
            {copied ? <Check size={15} className="text-green-400" /> : <Copy size={15} />}
          </button>
        </div>
      </div>

      <p className="hook-text text-hook-text text-sm leading-relaxed font-medium">"{h.hook}"</p>

      <div className="mt-2 w-full bg-hook-border rounded-full h-1">
        <div
          className="bg-hook-accent h-1 rounded-full"
          style={{ width: `${h.score * 10}%` }}
        />
      </div>

      {(h.why_it_works ?? h.why) && (
        <p className="mt-2.5 text-xs text-hook-muted leading-relaxed italic">
          {h.why_it_works ?? h.why}
        </p>
      )}

      {hasDetails && (
        <button
          onClick={() => setExpanded(e => !e)}
          className="mt-3 flex items-center gap-1 text-xs text-hook-muted hover:text-hook-glow transition-colors"
        >
          {expanded ? <ChevronUp size={12} /> : <ChevronDown size={12} />}
          {expanded ? 'Less' : 'Production details'}
        </button>
      )}

      {expanded && hasDetails && (
        <div className="mt-3 space-y-2.5 border-t border-hook-border pt-3">
          {h.first_3_seconds && (
            <div className="flex gap-2">
              <Clapperboard size={13} className="text-hook-accent shrink-0 mt-0.5" />
              <div>
                <span className="text-xs font-semibold text-hook-muted uppercase tracking-wide">First 3 seconds</span>
                <p className="text-xs text-hook-text mt-0.5">{h.first_3_seconds}</p>
              </div>
            </div>
          )}
          {h.caption_starter && (
            <div className="flex gap-2">
              <MessageSquare size={13} className="text-hook-accent shrink-0 mt-0.5" />
              <div className="flex-1 min-w-0">
                <span className="text-xs font-semibold text-hook-muted uppercase tracking-wide">Caption starter</span>
                <div className="flex items-start justify-between gap-2 mt-0.5">
                  <p className="text-xs text-hook-text">{h.caption_starter}</p>
                  <button
                    onClick={handleCopyCaption}
                    aria-label="Copy caption starter"
                    className="text-hook-muted hover:text-hook-glow transition-colors shrink-0"
                  >
                    {captionCopied ? <Check size={12} className="text-green-400" /> : <Copy size={12} />}
                  </button>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
