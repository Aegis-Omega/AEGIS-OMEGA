import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import { BridgePanel } from './components/BridgePanel.js'
import { GateTable } from './components/GateTable.js'

const VERSION = '0.5.3'
const SCHEMA = 'v2024-01'

const FROZEN = [
  { file: 'gate.py',   sha: '72196f38…f5fdb1e9' },
  { file: 'dna.py',    sha: '9c4d38d8…03971a9' },
  { file: 'router.py', sha: 'c96e566c…07ac769' },
] as const

const TIER_LIST = [
  ['T0', 'Mechanically proven',    'Core runtime, epoch failsafe'],
  ['T1', 'Empirically validated',  'TGCS, AFSE, VCG benchmarks'],
  ['T2', 'Engineering hypothesis', 'E1 heuristics, Paperclip'],
  ['T3', 'Research conjecture',    'Quasicrystal-CDT spectral'],
  ['T4', 'Speculative vision',     'Swarm, planetary'],
  ['T5', 'Creative',               'Cycle series'],
] as const

const TIER_COLORS = [
  'text-omega-glow', 'text-omega-accent', 'text-yellow-400',
  'text-orange-400', 'text-red-400', 'text-omega-muted',
] as const

function tierColor(i: number): string {
  return TIER_COLORS[i] ?? 'text-omega-muted'
}

function ConstitutionalFiles() {
  return (
    <section className="bg-omega-surface border border-omega-border rounded-lg p-5">
      <h2 className="text-omega-text text-sm font-bold tracking-wider uppercase mb-2">Constitutional Files</h2>
      <p className="text-omega-muted/60 text-xs mb-3">Modification requires /guardian APPROVED verdict.</p>
      {FROZEN.map(f => (
        <div key={f.file} className="flex justify-between py-1.5 border-b border-omega-border last:border-0">
          <code className="text-omega-glow text-xs">{f.file}</code>
          <code className="text-omega-muted text-[10px]">{f.sha}</code>
        </div>
      ))}
      <p className="text-omega-muted/50 text-[10px] mt-3">
        Verify: <code className="text-omega-muted/80">node scripts/verify-hashes.mjs</code>
      </p>
    </section>
  )
}

function EpistemicTiers() {
  return (
    <section className="bg-omega-surface border border-omega-border rounded-lg p-5">
      <h2 className="text-omega-text text-sm font-bold tracking-wider uppercase mb-3">Epistemic Tier Taxonomy</h2>
      {TIER_LIST.map(([tier, label, desc], i) => (
        <div key={tier} className="flex gap-3 py-1.5 border-b border-omega-border last:border-0">
          <span className={`shrink-0 w-6 text-xs font-bold ${tierColor(i)}`}>{tier}</span>
          <div>
            <span className="text-omega-text text-xs">{label}</span>
            <span className="text-omega-muted/60 text-xs ml-2">— {desc}</span>
          </div>
        </div>
      ))}
      <p className="text-omega-muted/50 text-[10px] mt-3">T4/T5 may not ground T0–T2 claims without evidence review.</p>
    </section>
  )
}

function App() {
  return (
    <div className="min-h-screen bg-omega-bg text-omega-text font-mono">
      <header className="border-b border-omega-border px-6 py-4 flex items-center justify-between">
        <div>
          <h1 className="text-omega-glow text-base font-bold tracking-widest uppercase">Sovereign Omega</h1>
          <p className="text-omega-muted text-xs mt-0.5">Governance Runtime v{VERSION} · Schema {SCHEMA}</p>
        </div>
        <span className="text-xs border border-omega-glow/30 text-omega-glow px-2 py-1 rounded">
          T0 · Mechanically Proven
        </span>
      </header>
      <main className="p-6 grid grid-cols-1 lg:grid-cols-2 gap-6">
        <BridgePanel />
        <GateTable />
        <ConstitutionalFiles />
        <EpistemicTiers />
      </main>
    </div>
  )
}

const root = document.getElementById('root')
if (!root) throw new Error('Root element not found')
createRoot(root).render(<StrictMode><App /></StrictMode>)
