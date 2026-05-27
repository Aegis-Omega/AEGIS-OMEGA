import { useState, useEffect } from 'react'
import { Sparkles, TrendingUp, Share2, Check, ShieldCheck } from 'lucide-react'
import { initAnalytics, trackEvent } from '@shared/lib/analytics'
import { AccessGate } from '@shared/components/AccessGate'
import { rankPlatforms, type MatcherInput, type RankedResult } from './lib/matcher.js'
import { ResultCard } from './components/ResultCard.js'
import { RadarChart } from './components/RadarChart.js'
import { useAsyncForm } from '@shared/hooks/useAsyncForm'
import { ErrorAlert } from '@shared/components/ErrorAlert'
import { LoadingSpinner } from '@shared/components/LoadingSpinner'
import { ToolkitFooter } from '@shared/components/ToolkitFooter'
import type { PlatformRanking } from './lib/matcher.js'

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
  const { state, result, errorMsg, submit, reset: resetAsync } = useAsyncForm(rankPlatforms)

  useEffect(() => {
    initAnalytics()
    trackEvent('trial_started', { product: 'platform-picker' })
  }, [])

  useEffect(() => {
    if (state === 'results') trackEvent('result_generated', { product: 'platform-picker' })
  }, [state])

  const valid = Object.values(form).every(v => v.trim().length > 0)
  const rankings: PlatformRanking[] = result?.rankings ?? []

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    await submit(form)
  }

  const reset = () => { setForm(EMPTY); resetAsync(); setShared(false) }

  const handleShare = async () => {
    const text = buildShareText(rankings, form.niche)
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

        {(state === 'idle' || state === 'error') && (
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

            {state === 'error' && <ErrorAlert message={errorMsg} />}

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

        {state === 'loading' && (
          <LoadingSpinner message="Analysing your profile…" colorClass="text-brand-glow" />
        )}

        {state === 'results' && result && (
          <div>
            <div className="flex items-center justify-between mb-6">
              <div className="flex items-center gap-2">
                <TrendingUp size={18} className="text-brand-glow" />
                <h2 className="font-semibold text-brand-text">Your platform ranking</h2>
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

            <AuditBadge result={result} />

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
