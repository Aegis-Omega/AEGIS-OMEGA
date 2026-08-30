import { useState, useEffect } from 'react'
import { CalendarDays, Download, History, X } from 'lucide-react'
import { initAnalytics, trackEvent } from '@shared/lib/analytics'
import { AccessGate } from '@shared/components/AccessGate'
import { generateCalendar, calendarToText, type CalendarInput, type WeekPlan } from './lib/calendar-ai.js'
import { WeekTable } from './components/WeekTable.js'
import { useAsyncForm } from '@shared/hooks/useAsyncForm'
import { useHistory, type HistoryEntry } from '@shared/hooks/useHistory'
import { ErrorAlert } from '@shared/components/ErrorAlert'
import { LoadingSpinner } from '@shared/components/LoadingSpinner'
import { ToolkitFooter } from '@shared/components/ToolkitFooter'

const EMPTY: CalendarInput = {
  niche: '', platforms: '', frequency: '',
  pillar1: '', pillar2: '', pillar3: '',
}

const HISTORY_KEY = 'aegis_calendar_history'

function formatRelative(ts: number): string {
  const diff = Date.now() - ts
  if (diff < 60_000) return 'just now'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)}m ago`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)}h ago`
  return `${Math.floor(diff / 86_400_000)}d ago`
}

const FIELDS: { key: keyof CalendarInput; label: string; placeholder: string }[] = [
  { key: 'niche',     label: 'Your niche',         placeholder: 'e.g. personal finance, fitness, travel…' },
  { key: 'platforms', label: 'Platforms',           placeholder: 'e.g. TikTok + Instagram Reels' },
  { key: 'frequency', label: 'Posting frequency',   placeholder: 'e.g. daily, 3x/week, Mon/Wed/Fri' },
  { key: 'pillar1',   label: 'Content pillar 1',    placeholder: 'e.g. Education / Tips' },
  { key: 'pillar2',   label: 'Content pillar 2',    placeholder: 'e.g. Entertainment / Skits' },
  { key: 'pillar3',   label: 'Content pillar 3',    placeholder: 'e.g. Personal story / Motivation' },
]

const PILLAR_LEGEND_COLORS = [
  'bg-blue-500/15 text-blue-300 border-blue-500/25',
  'bg-purple-500/15 text-purple-300 border-purple-500/25',
  'bg-orange-500/15 text-orange-300 border-orange-500/25',
]

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const a = document.createElement('a')
  a.href = url
  a.download = filename
  a.click()
  URL.revokeObjectURL(url)
}

function q(s: string) { return `"${s.replace(/"/g, '""')}"` }

function buildCsv(weeks: WeekPlan[]): string {
  const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const header = 'Week,Theme,Day,Platform,Pillar,Topic,Hook,Format,Difficulty,OptimalTime,CTA,Notes,Hashtags'
  const rows = weeks.flatMap(w =>
    w.posts.map(p => [
      w.week,
      q(w.theme),
      DAY_NAMES[p.day] ?? `Day${p.day}`,
      p.platform ?? '',
      p.content_pillar ?? p.pillar ?? '',
      q(p.topic ?? ''),
      q(p.hook),
      p.format,
      p.difficulty ?? '',
      q(p.optimal_time ?? ''),
      q(p.cta ?? ''),
      q(p.notes ?? p.production_note ?? ''),
      q(p.hashtags?.join(' ') ?? ''),
    ].join(','))
  )
  return [header, ...rows].join('\n')
}

export default function App() {
  const [form, setForm] = useState<CalendarInput>(EMPTY)
  const [historyEntry, setHistoryEntry] = useState<HistoryEntry<CalendarInput, WeekPlan[]> | null>(null)
  const { state, result, errorMsg, submit, reset: resetAsync } = useAsyncForm(generateCalendar)
  const { entries: history, addEntry } = useHistory<CalendarInput, WeekPlan[]>(
    HISTORY_KEY, inp => `${inp.niche} · ${inp.frequency}`,
  )

  const displayState = historyEntry ? 'results' : state
  const weeks: WeekPlan[] = (historyEntry ? historyEntry.result : result) ?? []
  const displayForm = historyEntry ? historyEntry.input : form
  const valid = Object.values(form).every(v => v.trim().length > 0)

  useEffect(() => {
    initAnalytics()
    trackEvent('trial_started', { product: 'content-calendar' })
  }, [])
  useEffect(() => {
    if (state === 'results' && result) {
      trackEvent('result_generated', { product: 'content-calendar' })
      addEntry(form, result)
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [state])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setHistoryEntry(null)
    await submit(form)
  }

  const handleDownloadTxt = () => {
    const blob = new Blob([calendarToText(weeks, displayForm)], { type: 'text/plain' })
    downloadBlob(blob, `content-calendar-${displayForm.niche.replace(/\s+/g, '-').toLowerCase()}.txt`)
  }

  const handleDownloadCsv = () => {
    const blob = new Blob([buildCsv(weeks)], { type: 'text/csv' })
    downloadBlob(blob, `content-calendar-${displayForm.niche.replace(/\s+/g, '-').toLowerCase()}.csv`)
  }

  const reset = () => { setForm(EMPTY); resetAsync(); setHistoryEntry(null) }
  const pillars: [string, string, string] = [displayForm.pillar1, displayForm.pillar2, displayForm.pillar3]

  return (
    <AccessGate product="content-calendar" accentColor="#16A34A">
    <div className="min-h-screen bg-cal-bg text-cal-text">
      <div className="max-w-2xl mx-auto px-4 py-16">

        <div className="text-center mb-12">
          <div className="inline-flex items-center gap-2 bg-cal-accent/10 border border-cal-accent/30 rounded-full px-4 py-1.5 text-cal-glow text-sm font-medium mb-6">
            <CalendarDays size={14} />
            AI-powered content planning
          </div>
          <h1 className="text-4xl font-bold text-cal-text mb-3 tracking-tight">Content Calendar</h1>
          <p className="text-cal-muted text-lg">
            4-week content plan — hooks, formats, and pillars — ready to execute.
          </p>
        </div>

        {(displayState === 'idle' || displayState === 'error') && (
          <form onSubmit={handleSubmit} className="space-y-4">
            {FIELDS.map(f => (
              <div key={f.key}>
                <label className="block text-sm font-medium text-cal-muted mb-1.5">{f.label}</label>
                <input
                  type="text"
                  value={form[f.key]}
                  onChange={e => setForm(p => ({ ...p, [f.key]: e.target.value }))}
                  placeholder={f.placeholder}
                  className="w-full bg-cal-surface border border-cal-border rounded-xl px-4 py-3 text-sm text-cal-text placeholder-cal-muted focus:outline-none focus:border-cal-glow transition-colors"
                />
              </div>
            ))}

            {displayState === 'error' && <ErrorAlert message={errorMsg} />}

            <button
              type="submit"
              disabled={!valid}
              className="w-full bg-cal-accent hover:bg-cal-accent/90 disabled:opacity-40 disabled:cursor-not-allowed text-black font-semibold py-3.5 rounded-xl transition-colors flex items-center justify-center gap-2 text-sm"
            >
              <CalendarDays size={16} />
              Generate 4-week calendar
            </button>
          </form>
        )}

        {history.length > 0 && (displayState === 'idle' || displayState === 'error') && (
          <div className="mt-8">
            <div className="flex items-center gap-2 mb-3">
              <History size={13} className="text-cal-muted" />
              <span className="text-xs font-medium text-cal-muted uppercase tracking-wide">Recent calendars</span>
            </div>
            <div className="space-y-2">
              {history.slice(0, 5).map(entry => (
                <button
                  key={entry.id}
                  onClick={() => { setHistoryEntry(entry); setForm(entry.input) }}
                  className="w-full text-left flex items-center justify-between gap-3 px-4 py-2.5 rounded-xl border border-cal-border hover:border-cal-glow/40 bg-cal-surface transition-all group"
                >
                  <div className="min-w-0">
                    <p className="text-xs font-medium text-cal-text truncate">{entry.label}</p>
                    <p className="text-xs text-cal-muted">{entry.result.length} weeks · {formatRelative(entry.ts)}</p>
                  </div>
                  <span className="text-xs text-cal-muted group-hover:text-cal-glow transition-colors shrink-0">Load →</span>
                </button>
              ))}
            </div>
          </div>
        )}

        {displayState === 'loading' && (
          <LoadingSpinner message="Building your content plan…" colorClass="text-cal-glow" />
        )}

        {displayState === 'results' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <CalendarDays size={18} className="text-cal-glow" />
                <h2 className="font-semibold text-cal-text">4-week plan for {displayForm.niche}</h2>
                {historyEntry && (
                  <span className="flex items-center gap-1 text-xs text-cal-muted border border-cal-border rounded-full px-2 py-0.5">
                    <History size={10} /> {formatRelative(historyEntry.ts)}
                    <button onClick={() => setHistoryEntry(null)} className="ml-1 hover:text-cal-glow"><X size={9} /></button>
                  </span>
                )}
              </div>
              <div className="flex items-center gap-2">
                <button
                  onClick={handleDownloadCsv}
                  aria-label="Download as CSV"
                  className="flex items-center gap-1.5 text-xs text-cal-muted hover:text-cal-glow border border-cal-border hover:border-cal-glow px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Download size={13} />
                  CSV
                </button>
                <button
                  onClick={handleDownloadTxt}
                  aria-label="Download as text"
                  className="flex items-center gap-1.5 text-xs text-cal-muted hover:text-cal-glow border border-cal-border hover:border-cal-glow px-3 py-1.5 rounded-lg transition-colors"
                >
                  <Download size={13} />
                  TXT
                </button>
              </div>
            </div>

            {/* Pillar legend */}
            <div className="flex items-center gap-2 flex-wrap mb-4">
              {pillars.map((p, i) => p && (
                <span key={i} className={`text-xs border rounded-full px-2.5 py-0.5 ${PILLAR_LEGEND_COLORS[i]}`}>
                  {p}
                </span>
              ))}
            </div>

            {weeks.map(w => <WeekTable key={w.week} week={w} pillars={pillars} />)}

            <button
              onClick={reset}
              className="w-full mt-4 border border-cal-border text-cal-muted hover:border-cal-glow hover:text-cal-glow py-3 rounded-xl text-sm transition-colors"
            >
              Generate another calendar
            </button>
          </div>
        )}
      </div>
      <ToolkitFooter
        current="Content Calendar"
        borderClass="border-cal-border"
        mutedClass="text-cal-muted"
        glowClass="text-cal-muted hover:text-cal-glow"
      />
    </div>
    </AccessGate>
  )
}
