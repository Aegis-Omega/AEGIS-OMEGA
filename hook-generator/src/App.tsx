import { useState, useEffect } from 'react'
import { Zap, Download, Star, History, X } from 'lucide-react'
import { initAnalytics, trackEvent } from '@shared/lib/analytics'
import { AccessGate } from '@shared/components/AccessGate'
import { generateHooks, type HookInput, type HookResult, type Platform, type Tone } from './lib/hooks-ai.js'
import { HookCard } from './components/HookCard.js'
import { useAsyncForm } from '@shared/hooks/useAsyncForm'
import { useHistory, type HistoryEntry } from '@shared/hooks/useHistory'
import { ErrorAlert } from '@shared/components/ErrorAlert'
import { LoadingSpinner } from '@shared/components/LoadingSpinner'
import { ToolkitFooter } from '@shared/components/ToolkitFooter'

const PLATFORMS: Platform[] = ['TikTok', 'YouTube Shorts', 'Instagram Reels', 'All platforms']
const TONES: Tone[] = ['Entertaining', 'Educational', 'Controversial', 'Inspirational', 'Relatable']

const EMPTY: HookInput = { niche: '', platform: 'TikTok', topic: '', tone: 'Entertaining' }
const FAV_KEY = 'aegis_hook_favorites'
const HISTORY_KEY = 'aegis_hooks_history'

function formatRelative(ts: number): string {
  const diff = Date.now() - ts
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

function loadFavs(): Set<string> {
  try {
    const raw = localStorage.getItem(FAV_KEY)
    return new Set(raw ? (JSON.parse(raw) as string[]) : [])
  } catch {
    return new Set()
  }
}

function saveFavs(favs: Set<string>) {
  localStorage.setItem(FAV_KEY, JSON.stringify([...favs]))
}

export default function App() {
  const [form, setForm] = useState<HookInput>(EMPTY)
  const [favs, setFavs] = useState<Set<string>>(loadFavs)
  const [showFavsOnly, setShowFavsOnly] = useState(false)
  const [historyEntry, setHistoryEntry] = useState<HistoryEntry<HookInput, HookResult[]> | null>(null)
  const { state, result, errorMsg, submit, reset: resetAsync } = useAsyncForm(generateHooks)
  const { entries: history, addEntry } = useHistory<HookInput, HookResult[]>(
    HISTORY_KEY, inp => `${inp.platform} · ${inp.topic}`,
  )

  const valid = form.niche.trim().length > 0 && form.topic.trim().length > 0
  const displayState = historyEntry ? 'results' : state
  const allResults: HookResult[] = (historyEntry ? historyEntry.result : result) ?? []
  const results = showFavsOnly ? allResults.filter(h => favs.has(h.hook)) : allResults
  const displayForm = historyEntry ? historyEntry.input : form

  useEffect(() => { saveFavs(favs) }, [favs])
  useEffect(() => {
    initAnalytics()
    trackEvent('trial_started', { product: 'hook-generator' })
  }, [])
  useEffect(() => {
    if (state === 'results' && result) {
      trackEvent('result_generated', { product: 'hook-generator' })
      addEntry(form, result)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setHistoryEntry(null)
    setShowFavsOnly(false)
    await submit(form)
  }

  const reset = () => { setForm(EMPTY); resetAsync(); setShowFavsOnly(false); setHistoryEntry(null) }

  const toggleFav = (hook: string) => {
    setFavs(prev => {
      const next = new Set(prev)
      if (next.has(hook)) next.delete(hook); else next.add(hook)
      return next
    })
  }

  const exportAll = () => {
    const text = allResults.map((h, i) => {
      const lines = [`${i + 1}. [${h.type}] ${h.score}/10 — ${h.platform_fit}`]
      lines.push(`   "${h.hook}"`)
      if (h.why_it_works ?? h.why) lines.push(`   Why: ${h.why_it_works ?? h.why}`)
      if (h.caption_starter) lines.push(`   Caption: ${h.caption_starter}`)
      return lines.join('\n')
    }).join('\n\n')
    navigator.clipboard.writeText(text)
  }

  const favCount = allResults.filter(h => favs.has(h.hook)).length

  return (
    <AccessGate product="hook-generator" accentColor="#D97706">
    <div className="min-h-screen bg-hook-bg text-hook-text">
      <div className="max-w-2xl mx-auto px-4 py-16">

        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-hook-accent/10 border border-hook-accent/30 rounded-full px-4 py-1.5 text-hook-glow text-sm font-medium mb-6">
            <Zap size={14} />
            AI-powered hook writing
          </div>
          <h1 className="text-4xl font-bold text-hook-text mb-3 tracking-tight">Hook Generator</h1>
          <p className="text-hook-muted text-lg">
            Turn any topic into 10 scroll-stopping hooks — ranked by viral potential.
          </p>
        </div>

        {(displayState === 'idle' || displayState === 'error') && (
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-hook-muted mb-1.5">Platform</label>
                <select
                  value={form.platform}
                  onChange={e => setForm(p => ({ ...p, platform: e.target.value as Platform }))}
                  className="w-full bg-hook-surface border border-hook-border rounded-xl px-4 py-3 text-sm text-hook-text focus:outline-none focus:border-hook-glow transition-colors"
                >
                  {PLATFORMS.map(p => <option key={p} value={p}>{p}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-hook-muted mb-1.5">Tone</label>
                <select
                  value={form.tone}
                  onChange={e => setForm(p => ({ ...p, tone: e.target.value as Tone }))}
                  className="w-full bg-hook-surface border border-hook-border rounded-xl px-4 py-3 text-sm text-hook-text focus:outline-none focus:border-hook-glow transition-colors"
                >
                  {TONES.map(t => <option key={t} value={t}>{t}</option>)}
                </select>
              </div>
            </div>

            <div>
              <label className="block text-sm font-medium text-hook-muted mb-1.5">Your niche</label>
              <input
                type="text"
                value={form.niche}
                onChange={e => setForm(p => ({ ...p, niche: e.target.value }))}
                placeholder="e.g. personal finance, fitness, cooking, productivity…"
                className="w-full bg-hook-surface border border-hook-border rounded-xl px-4 py-3 text-sm text-hook-text placeholder-hook-muted focus:outline-none focus:border-hook-glow transition-colors"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-hook-muted mb-1.5">Video topic</label>
              <input
                type="text"
                value={form.topic}
                onChange={e => setForm(p => ({ ...p, topic: e.target.value }))}
                placeholder="e.g. why most people never pay off debt, 5-minute ab workout…"
                className="w-full bg-hook-surface border border-hook-border rounded-xl px-4 py-3 text-sm text-hook-text placeholder-hook-muted focus:outline-none focus:border-hook-glow transition-colors"
              />
            </div>

            {displayState === 'error' && <ErrorAlert message={errorMsg} />}

            <button
              type="submit"
              disabled={!valid}
              className="w-full bg-hook-accent hover:bg-hook-accent/90 disabled:opacity-40 disabled:cursor-not-allowed text-black font-semibold py-3.5 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm"
            >
              <Zap size={16} />
              Generate 15 hooks
            </button>
          </form>
        )}

        {history.length > 0 && (displayState === 'idle' || displayState === 'error') && (
          <div className="mt-8">
            <div className="flex items-center gap-2 mb-3">
              <History size={13} className="text-hook-muted" />
              <span className="text-xs font-medium text-hook-muted uppercase tracking-wide">Recent generations</span>
            </div>
            <div className="space-y-2">
              {history.slice(0, 5).map(entry => (
                <button
                  key={entry.id}
                  onClick={() => { setHistoryEntry(entry); setForm(entry.input) }}
                  className="w-full text-left flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl border border-hook-border hover:border-hook-glow/40 bg-hook-surface hover:bg-hook-surface/80 transition-all group"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-hook-text truncate">{entry.label}</p>
                    <p className="text-xs text-hook-muted">{entry.result.length} hooks · {formatRelative(entry.ts)}</p>
                  </div>
                  <span className="text-xs text-hook-muted group-hover:text-hook-glow transition-colors shrink-0">Load →</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {displayState === 'loading' && (
          <LoadingSpinner message="Generating viral hooks…" colorClass="text-hook-glow" />
        )}

        {displayState === 'results' && (
          <div className="space-y-3">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <Zap size={18} className="text-hook-glow" />
                <h2 className="font-semibold text-hook-text">{allResults.length} hooks for &ldquo;{displayForm.topic}&rdquo;</h2>
                {historyEntry && (
                  <span className="flex items-center gap-1 text-xs text-hook-muted border border-hook-border rounded-full px-2 py-0.5">
                    <History size={10} /> {formatRelative(historyEntry.ts)}
                    <button onClick={() => setHistoryEntry(null)} className="ml-1 hover:text-hook-glow"><X size={9} /></button>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                {favCount > 0 && (
                  <button
                    onClick={() => setShowFavsOnly(v => !v)}
                    aria-label="Toggle favourites filter"
                    className={`flex items-center gap-1 text-xs px-2.5 py-1.5 rounded-lg border transition-colors ${
                      showFavsOnly
                        ? 'text-hook-accent border-hook-accent bg-hook-accent/10'
                        : 'text-hook-muted border-hook-border hover:text-hook-glow hover:border-hook-glow'
                    }`}
                  >
                    <Star size={12} fill={showFavsOnly ? 'currentColor' : 'none'} />
                    {favCount}
                  </button>
                )}
                <button
                  onClick={exportAll}
                  aria-label="Copy all hooks to clipboard"
                  className="flex items-center gap-1.5 text-xs text-hook-muted hover:text-hook-glow border border-hook-border hover:border-hook-glow px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Download size={13} />
                  Export all
                </button>
              </div>
            </div>

            <div className="flex items-center justify-end">
              <span className="text-hook-muted text-xs">{displayForm.platform} · {displayForm.tone}</span>
            </div>

            {results.map((h, i) => (
              <HookCard
                key={h.hook}
                hook={h}
                rank={i}
                isFav={favs.has(h.hook)}
                onToggleFav={() => toggleFav(h.hook)}
              />
            ))}

            <button
              onClick={reset}
              className="w-full mt-4 border border-hook-border text-hook-muted hover:border-hook-glow hover:text-hook-glow py-3 rounded-xl text-sm transition-colors"
            >
              Generate more hooks
            </button>
          </div>
        )}
      </div>
      <ToolkitFooter
        current="Hook Generator"
        borderClass="border-hook-border"
        mutedClass="text-hook-muted"
        glowClass="text-hook-muted hover:text-hook-glow"
      />
    </div>
    </AccessGate>
  )
}
