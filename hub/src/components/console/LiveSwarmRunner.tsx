// AEGIS-Ω Console — authenticated execution client.
// This UI does not synthesize agent events or verification results.
// One live backend inference generates department artifacts; it is NOT
// evidence of 39 independent model invocations or independent chain verification.

import { useRef, useState } from 'react'
import { PlatformClient } from '@shared/lib/platform-client.js'
import { T, MONO, glass } from './consoleTokens.js'
import { Heading } from './SystemStatusBar.js'

type Mode = 'revenue' | 'analysis' | 'gtm' | 'retention'
type EvType = 'dag_step' | 'agent_event' | 'tool_call' | 'completion' | 'error'
type RunState = 'idle' | 'running' | 'received' | 'unverified'
interface StreamLine { id: number; type: EvType; text: string; color: string }

const PLATFORM_URL = ((import.meta.env.VITE_PLATFORM_URL as string | undefined)
  ?? 'https://aegis-vertex.aegisomega.com').replace(/\/$/, '')
const MODE_COLOR: Record<Mode, string> = {
  revenue: T.green, analysis: T.indigo, gtm: T.phi, retention: T.blue,
}

function publicError(e: unknown): string {
  return e instanceof Error ? e.message.slice(0, 200) : 'Unknown backend error'
}

export function LiveSwarmRunner({ memoryActive }: { memoryActive: boolean }) {
  const [mode, setMode] = useState<Mode>('gtm')
  const [objective, setObjective] = useState('Enter EU AI-governance market Q4 2026')
  const [apiKey, setApiKey] = useState('')
  const [lines, setLines] = useState<StreamLine[]>([])
  const [state, setState] = useState<RunState>('idle')
  const [executionId, setExecutionId] = useState('')
  const idRef = useRef(0)
  const accent = MODE_COLOR[mode]
  const running = state === 'running'

  function push(type: EvType, message: string, color: string) {
    setLines(prev => [...prev.slice(-79), {
      id: idRef.current++, type, text: message, color,
    }])
  }

  async function verifyResult(client: PlatformClient, id: string) {
    // Do not promote a transport-level SSE completion to success. Re-read the
    // authenticated result and ensure it has substantive backend artifacts.
    const receipt = await client.getExecution(id)
    if (receipt.status === 'error') {
      throw new Error(receipt.error || 'Backend execution failed')
    }
    if (receipt.status !== 'complete' || !receipt.result) {
      throw new Error('Execution is not complete; result unverified. Recheck by ID.')
    }
    const result = receipt.result
    if (result.execution_id !== id || !Array.isArray(result.artifacts)
        || result.artifacts.length === 0
        || result.artifacts.length !== result.departments_collaborated
        || result.artifacts.some(a => !a.role || !a.output?.trim())) {
      throw new Error('Backend result failed artifact and execution-ID checks')
    }
    push('completion', 'Backend returned ' + result.artifacts.length
      + ' department artifacts · execution=' + id, T.green)
    push('agent_event', 'Backend-reported audit: '
      + String(result.constitutional_audit?.verdict ?? 'UNKNOWN')
      + '. No independent cryptographic verification performed by this UI.', T.sub)
    setState('received')
  }

  async function run() {
    if (running || executionId || !apiKey.trim() || objective.trim().length < 10) return
    const client = new PlatformClient({ apiKey: apiKey.trim(), endpoint: PLATFORM_URL })
    setApiKey('') // Do not retain credentials in the form or persistent storage.
    setLines([])
    idRef.current = 0
    setState('running')

    try {
      // Explicit user action; live mode can consume the operator's API quota.
      // autonomous:false = one model call, not 39 independent agent calls.
      const init = await client.startExecution({
        objective: objective.trim(), mode, live: true, autonomous: false,
      })
      if (init.status !== 'pending' || !init.execution_id) {
        throw new Error('Backend did not return a valid execution receipt')
      }
      setExecutionId(init.execution_id)
      push('dag_step', 'Backend accepted live execution ' + init.execution_id, T.text)

      let terminal = false
      for await (const event of client.streamExecution(init.execution_id)) {
        if (event.execution_id !== init.execution_id) {
          throw new Error('Execution-ID mismatch in event stream')
        }
        const payload = event.payload as unknown as Record<string, unknown>
        if ((event.type === 'dag_step' || event.type === 'agent_event')
            && payload.source !== 'live') {
          throw new Error('Backend emitted non-live department events')
        }
        if (event.type === 'dag_step') {
          push('dag_step', String(payload.dept_id ?? '?') + ' · '
            + String(payload.dept_name ?? '?'), accent)
        } else if (event.type === 'agent_event') {
          push('agent_event', String(payload.role ?? '?') + ' → '
            + String(payload.output_preview ?? '').slice(0, 120), T.sub)
        } else if (event.type === 'tool_call') {
          push('tool_call', String(payload.tool_name ?? 'tool'), T.indigo)
        } else if (event.type === 'error') {
          throw new Error(String(payload.message ?? 'Backend execution error'))
        } else if (event.type === 'completion') {
          terminal = true
        }
      }
      if (!terminal) {
        throw new Error('Stream ended without a completion event; recheck by ID')
      }
      await verifyResult(client, init.execution_id)
    } catch (e) {
      push('error', publicError(e), T.red)
      setState('unverified')
    }
  }

  async function recheck() {
    if (running || !executionId || !apiKey.trim()) return
    const client = new PlatformClient({ apiKey: apiKey.trim(), endpoint: PLATFORM_URL })
    setApiKey('')
    setState('running')
    try {
      await verifyResult(client, executionId)
    } catch (e) {
      push('error', publicError(e), T.red)
      setState('unverified')
    }
  }

  function reset() {
    if (running) return
    setExecutionId('')
    setLines([])
    setState('idle')
    idRef.current = 0
  }

  return (
    <div style={{ ...glass(accent), padding: 20 }}>
      <div className="flex items-center justify-between mb-1">
        <Heading>SWARM RUNNER · authenticated execution</Heading>
        <span style={{ fontSize: 10, fontFamily: MONO, color: T.muted }}>
          {state === 'received' ? 'BACKEND RESULT RECEIVED'
            : state === 'unverified' ? 'NOT VERIFIED'
            : running ? 'BACKEND REQUEST IN PROGRESS' : 'NOT STARTED'}
        </span>
      </div>

      <p style={{ fontSize: 12, color: T.sub, lineHeight: 1.6 }}>
        Runs the existing backend with one live model call and department-specific
        outputs. An API key and a reachable runtime are required. Live calls may
        consume paid usage. This screen does not independently certify the audit chain.
      </p>

      <div className="flex flex-wrap gap-2 mt-3 mb-3">
        {(['gtm', 'revenue', 'analysis', 'retention'] as Mode[]).map(m => (
          <button key={m} onClick={() => setMode(m)} disabled={running || !!executionId}
            style={{
              padding: '5px 13px', borderRadius: 16, fontSize: 12,
              fontFamily: MONO, background: m === mode ? MODE_COLOR[m] + '18' : 'transparent',
              border: '1px solid ' + (m === mode ? MODE_COLOR[m] + '55' : T.border),
              color: m === mode ? MODE_COLOR[m] : T.muted,
            }}>{m}</button>
        ))}
      </div>

      <div className="flex flex-wrap gap-2 mb-3">
        <input aria-label="Collaboration objective" value={objective}
          onChange={e => setObjective(e.target.value)} disabled={running || !!executionId}
          style={{
            flex: '2 1 260px', background: T.inset,
            border: '1px solid ' + T.border, borderRadius: 8,
            padding: '9px 12px', color: T.text,
          }}/>
        <input aria-label="AEGIS API key" type="password" autoComplete="off"
          placeholder="AEGIS API key · not stored" value={apiKey}
          onChange={e => setApiKey(e.target.value)} disabled={running}
          style={{
            flex: '1 1 180px', background: T.inset,
            border: '1px solid ' + T.border, borderRadius: 8,
            padding: '9px 12px', color: T.text,
          }}/>
        {!executionId ? (
          <button onClick={() => void run()}
            disabled={running || !apiKey.trim() || objective.trim().length < 10}
            style={{ padding: '9px 18px', borderRadius: 8, border: 'none',
              background: accent, color: T.void }}>
            {running ? 'Running…' : 'Start live execution'}
          </button>
        ) : (
          <>
            <button onClick={() => void recheck()} disabled={running || !apiKey.trim()}
              style={{ padding: '9px 18px', borderRadius: 8,
                background: accent, color: T.void, border: 'none' }}>
              Check existing result (no new run)
            </button>
            <button onClick={reset} disabled={running}
              style={{ padding: '9px 12px', borderRadius: 8,
                background: 'transparent', color: T.sub,
                border: '1px solid ' + T.border }}>New run</button>
          </>
        )}
      </div>

      {executionId && (
        <div style={{ color: T.sub, fontFamily: MONO, fontSize: 11, marginBottom: 10,
          overflowWrap: 'anywhere' }}>Execution receipt: {executionId}</div>
      )}

      <div aria-live="polite" style={{ background: T.inset, borderRadius: 10,
        border: '1px solid ' + T.border, padding: 14, height: 250,
        overflowY: 'auto', fontFamily: MONO, fontSize: 12 }}>
        {lines.length === 0 && (
          <span style={{ color: T.muted }}>No backend events. No work is claimed.</span>
        )}
        {lines.map(line => (
          <div key={line.id} style={{ display: 'flex', gap: 12, marginBottom: 5 }}>
            <span style={{ color: line.color, minWidth: 85 }}>{line.type}</span>
            <span style={{ color: line.color, overflowWrap: 'anywhere' }}>{line.text}</span>
          </div>
        ))}
      </div>
      <p style={{ fontSize: 11, fontFamily: MONO, color: T.muted, marginTop: 12 }}>
        {memoryActive ? 'Live telemetry reports a nonzero fitness window; this is not proof of memory recall.'
          : 'No verified live memory state in this console snapshot.'}
      </p>
    </div>
  )
}
