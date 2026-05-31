import { useState, useEffect } from 'react'
import { Sparkles, TrendingUp, Share2, Check, ShieldCheck, History, X } from 'lucide-react'
import { initAnalytics, trackEvent } from '@shared/lib/analytics'
import { AccessGate } from '@shared/components/AccessGate'
import { rankPlatforms, type MatcherInput, type RankedResult } from './lib/matcher.js'
import { ResultCard } from './components/ResultCard.js'
import { RadarChart } from './components/RadarChart.js'
import { useAsyncForm } from '@shared/hooks/useAsyncForm'
import { useHistory, type HistoryEntry } from '@shared/hooks/useHistory'
import { ErrorAlert } from '@shared/components/ErrorAlert'
import { LoadingSpinner } from '@shared/components/LoadingSpinner'
import { ToolkitFooter } from '@shared/components/ToolkitFooter'
import type { PlatformRanking } from './lib/matcher.js'

const HISTORY_KEY = 'aegis_platform_history'

function formatRelative(ts: number): string {
  const diff = Date.now() - ts
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

const FIELDS: { key: keyof MatcherInput; label: string; placeholder: string }[] = [
  { key: 'niche',             label: 'Your niche',         placeholder: 'e.g. fitness, cooking, comedy, finance…' },
  { key: 'content_style',     label: 'Content style',      placeholder: 'e.g. talking head, B-roll, tutorials, skits…' },
  { key: 'target_age',        label: 'Target age group',   placeholder: 'e.g. 18–24, 25–34, teens…' },
  { key: 'posting_frequency', label: 'Posting frequency',  placeholder: 'e.g. daily, 3x/week, weekends only…' },
  { key: 'monetisation_goal', label: 'Monetisation goal',  placeholder: 'e.g. brand deals, creator fund, sell products…' },
  { key: 'current_following', label: 'Current following',  placeholder: 'e.g. 0 (starting), 5k, 50k…' },
]

const EMPTY: MatcherInput = {
  niche: '', content_style: '', target_age: '',
  posting_frequency: '', monetisation_goal: '', current_following: '',
}

function buildShareText(results: PlatformRanking[], niche: string): string {
  const lines = [`🎯 Platform Picker — ${niche}`, '']
  for (const r of results) {
    lines.push(`${r.platform}: ${r.score}/10 — ${r.best_for}`)
  }
  lines.push('', 'Generated with AEGIS Platform Picker')
  return lines.join('\n')
}

function AuditBadge({ result }: { result: RankedResult }) {
  const short = result.chain_hash.slice(0, 8)
  const backendLabel: Record<string, string> = {
    'dashscope': 'Qwen', 'ollama': 'Ollama', 'claude': 'Claude',
    'cl-psi': 'CL-Ψ', 'openai-compat': 'OpenAI',
  }
  const label = backendLabel[result.backend ?? ''] ?? result.backend ?? 'AI'
  return (
    <div className="flex items-center gap-2 text-xs text-brand-muted border border-brand-border/50 rounded-lg px-3 py-2 bg-brand-surface/50 mt-4">
      <ShieldCheck size={13} className="text-green-400 shrink-0" />
      <span>
        Constitutionally certified via <span className="text-brand-glow">{label}</span>
        {result.fallback_count != null && result.fallback_count > 0 && (
          <span className="text-brand-muted/60"> (+{result.fallback_count} fallback)</span>
        )}
        {' '}· audit #{result.session_calls} ·{' '}
        <span className="font-mono text-green-400/80">{short}…</span>
        {result.martingale_anchored && (
          <span className="ml-1 text-green-400/60">· anchored</span>
        )}
      </span>
    </div>
  )
}

export default function App() {
  const [form, setForm] = useState<MatcherInput>(EMPTY)
  const [shared, setShared] = useState(false)
  const [historyEntry, setHistoryEntry] = useState<HistoryEntry<MatcherInput, RankedResult> | null>(null)
  const { state, result, errorMsg, submit, reset: resetAsync } = useAsyncForm(rankPlatforms)
  const { entries: history, addEntry } = useHistory<MatcherInput, RankedResult>(
    HISTORY_KEY, inp => `${inp.niche} · ${inp.content_style}`,
  )

  const displayState = historyEntry ? 'results' : state
  const displayResult: RankedResult | null = historyEntry ? historyEntry.result : (result ?? null)
  const rankings: PlatformRanking[] = displayResult?.rankings ?? []
  const displayForm = historyEntry ? historyEntry.input : form

  useEffect(() => {
    initAnalytics()
    trackEvent('trial_started', { product: 'platform-picker' })
  }, [])

  useEffect(() => {
    if (state === 'results' && result) {
      trackEvent('result_generated', { product: 'platform-picker' })
      addEntry(form, result)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  const valid = Object.values(form).every(v => v.trim().length > 0)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setHistoryEntry(null)
    await submit(form)
  }

  const reset = () => { setForm(EMPTY); resetAsync(); setShared(false); setHistoryEntry(null) }

  const handleShare = async () => {
    const text = buildShareText(rankings, displayForm.niche)
    await navigator.clipboard.writeText(text)
    setShared(true)
    setTimeout(() => setShared(false), 2000)
  }

  return (
    <AccessGate product="platform-picker" accentColor="#7C3AED">
    <div className="min-h-screen bg-brand-bg text-brand-text">
      <div className="max-w-2xl mx-auto px-4 py-16">
        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-brand-accent/10 border border-brand-accent/30 rounded-full px-4 py-1.5 text-brand-glow text-sm font-medium mb-6">
            <Sparkles size={14} />
            AI-powered platform matching
          </div>
          <h1 className="text-4xl font-bold text-brand-text mb-3 tracking-tight">Platform Picker</h1>
          <p className="text-brand-muted text-lg">
            Tell us about your content. Get ranked recommendations for TikTok, YouTube Shorts, Reels &amp; Spotlight.
          </p>
        </div>

        {(displayState === 'idle' || displayState === 'error') && (
          <form onSubmit={handleSubmit} className="space-y-4">
            {FIELDS.map(f => (
              <div key={f.key}>
                <label className="block text-sm font-medium text-brand-muted mb-1.5">{f.label}</label>
                <input
                  type="text"
                  value={form[f.key]}
                  onChange={e => setForm(prev => ({ ...prev, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full bg-brand-surface border border-brand-border rounded-xl px-4 py-3 text-sm text-brand-text placeholder-brand-muted focus:outline-none focus:border-brand-glow transition-colors"
                />
              </div>
            ))}

            {displayState === 'error' && <ErrorAlert message={errorMsg} />}

            <button
              type="submit"
              disabled={!valid}
              className="w-full bg-brand-accent hover:bg-brand-accent/90 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-3.5 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm"
            >
              <Sparkles size={16} />
              Find my best platform
            </button>
          </form>
        )}

        {history.length > 0 && (displayState === 'idle' || displayState === 'error') && (
          <div className="mt-8">
            <div className="flex items-center gap-2 mb-3">
              <History size={13} className="text-brand-muted" />
              <span className="text-xs font-medium text-brand-muted uppercase tracking-wide">Recent analyses</span>
            </div>
            <div className="space-y-2">
              {history.slice(0, 5).map(entry => (
                <button
                  key={entry.id}
                  onClick={() => { setHistoryEntry(entry); setForm(entry.input) }}
                  className="w-full text-left flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl border border-brand-border hover:border-brand-glow/40 bg-brand-surface transition-all group"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-brand-text truncate">{entry.label}</p>
                    <p className="text-xs text-brand-muted">{formatRelative(entry.ts)}</p>
                  </div>
                  <span className="text-xs text-brand-muted group-hover:text-brand-glow transition-colors shrink-0">Load →</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {displayState === 'loading' && (
          <LoadingSpinner message="Analysing your profile…" colorClass="text-brand-glow" />
        )}

        {displayState === 'results' && displayResult && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <TrendingUp size={18} className="text-brand-glow" />
                <h2 className="font-semibold text-brand-text">Platform ranking · {displayForm.niche}</h2>
                {historyEntry && (
                  <span className="flex items-center gap-1 text-xs text-brand-muted border border-brand-border rounded-full px-2 py-0.5">
                    <History size={10} /> {formatRelative(historyEntry.ts)}
                    <button onClick={() => setHistoryEntry(null)} className="ml-1 hover:text-brand-glow"><X size={9} /></button>
                  </span>
                )}
              </div>
              <button
                onClick={handleShare}
                aria-label="Copy results to clipboard"
                className="flex items-center gap-1.5 text-xs text-brand-muted hover:text-brand-glow border border-brand-border hover:border-brand-glow px-3 py-1.5 rounded-lg transition-colors"
              >
                {shared ? <Check size={13} className="text-green-400" /> : <Share2 size={13} />}
                {shared ? 'Copied!' : 'Share'}
              </button>
            </div>

            <div className="mb-6">
              <RadarChart rankings={rankings} />
            </div>

            <div className="space-y-4">
              {rankings.map((r, i) => (
                <div
                  key={r.platform}
                  className="animate-fade-in"
                  style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
                >
                  <ResultCard ranking={r} rank={i} />
                </div>
              ))}
            </div>

            <AuditBadge result={displayResult} />

            <button
              onClick={reset}
              className="w-full mt-4 border border-brand-border text-brand-muted hover:border-brand-glow hover:text-brand-glow py-3 rounded-xl text-sm transition-colors"
            >
              Try another profile
            </button>
          </div>
        )}
      </div>
      <ToolkitFooter
        current="Platform Picker"
        borderClass="border-brand-border"
        mutedClass="text-brand-muted"
        glowClass="text-brand-muted hover:text-brand-glow"
      />
    </div>
    </AccessGate>
  )
}
