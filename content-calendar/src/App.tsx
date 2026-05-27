import { useState, useEffect } from 'react'
import { CalendarDays, Download } from 'lucide-react'
import { initAnalytics, trackEvent } from '@shared/lib/analytics'
import { AccessGate } from '@shared/components/AccessGate'
import { generateCalendar, calendarToText, type CalendarInput, type WeekPlan } from './lib/calendar-ai.js'
import { WeekTable } from './components/WeekTable.js'
import { useAsyncForm } from '@shared/hooks/useAsyncForm'
import { ErrorAlert } from '@shared/components/ErrorAlert'
import { LoadingSpinner } from '@shared/components/LoadingSpinner'
import { ToolkitFooter } from '@shared/components/ToolkitFooter'

const EMPTY: CalendarInput = {
  niche: '', platforms: '', frequency: '',
  pillar1: '', pillar2: '', pillar3: '',
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

function buildCsv(weeks: WeekPlan[]): string {
  const DAY_NAMES = ['', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  const header = 'Week,Theme,Day,Platform,Pillar,Hook,Format,Notes'
  const rows = weeks.flatMap(w =>
    w.posts.map(p => [
      w.week,
      `"${w.theme}"`,
      DAY_NAMES[p.day] ?? `Day${p.day}`,
      p.platform ?? '',
      p.content_pillar ?? p.pillar ?? '',
      `"${p.hook.replace(/"/g, '""')}"`,
      p.format,
      `"${(p.notes ?? p.production_note ?? '').replace(/"/g, '""')}"`,
    ].join(','))
  )
  return [header, ...rows].join('\n')
}

export default function App() {
  const [form, setForm] = useState<CalendarInput>(EMPTY)
  const { state, result, errorMsg, submit, reset: resetAsync } = useAsyncForm(generateCalendar)

  const valid = Object.values(form).every(v => v.trim().length > 0)
  const weeks: WeekPlan[] = result ?? []

  useEffect(() => {
    initAnalytics()
    trackEvent('trial_started', { product: 'content-calendar' })
  }, [])
  useEffect(() => {
    if (state === 'results') trackEvent('result_generated', { product: 'content-calendar' })
  }, [state])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!valid) return
    await submit(form)
  }

  const handleDownloadTxt = () => {
    const blob = new Blob([calendarToText(weeks, form)], { type: 'text/plain' })
    downloadBlob(blob, `content-calendar-${form.niche.replace(/\s+/g, '-').toLowerCase()}.txt`)
  }

  const handleDownloadCsv = () => {
    const blob = new Blob([buildCsv(weeks)], { type: 'text/csv' })
    downloadBlob(blob, `content-calendar-${form.niche.replace(/\s+/g, '-').toLowerCase()}.csv`)
  }

  const reset = () => { setForm(EMPTY); resetAsync() }
  const pillars: [string, string, string] = [form.pillar1, form.pillar2, form.pillar3]

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

        {(state === 'idle' || state === 'error') && (
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

            {state === 'error' && <ErrorAlert message={errorMsg} />}

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

        {state === 'loading' && (
          <LoadingSpinner message="Building your content plan…" colorClass="text-cal-glow" />
        )}

        {state === 'results' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between mb-2">
              <div className="flex items-center gap-2">
                <CalendarDays size={18} className="text-cal-glow" />
                <h2 className="font-semibold text-cal-text">4-week plan for {form.niche}</h2>
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
