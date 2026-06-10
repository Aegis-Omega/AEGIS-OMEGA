import { useCallback, useRef, useState } from 'react'
import type { AgentNode, CollaborationMode, CollaborationResult, LogEntry, SystemStatus } from '../types.js'
import { DEPARTMENTS } from '../types.js'

const BRIDGE = (import.meta.env.VITE_BRIDGE_URL as string | undefined) ?? 'http://localhost:7890'

function freshAgents(): AgentNode[] {
  return DEPARTMENTS.map((d, i) => ({ ...d, state: 'idle' as const, index: i }))
}

function ts(): string {
  return new Date().toISOString().split('T')[1]?.slice(0, 12) ?? ''
}

let _logId = 0
function mkLog(level: LogEntry['level'], message: string): LogEntry {
  return { id: `l${++_logId}`, ts: ts(), level, message }
}

export function useExecution(apiKey: string) {
  const [status, setStatus]   = useState<SystemStatus>('IDLE')
  const [agents, setAgents]   = useState<AgentNode[]>(freshAgents)
  const [logs, setLogs]       = useState<LogEntry[]>([
    mkLog('SYSTEM', 'AEGIS-Ω TACTICAL OPERATIONS CENTER — ONLINE'),
    mkLog('INFO',   'Awaiting objective. All 39 nodes standing by.'),
  ])
  const [result, setResult]   = useState<CollaborationResult | null>(null)
  const sseRef = useRef<EventSource | null>(null)

  const addLog = useCallback((level: LogEntry['level'], msg: string) => {
    setLogs(prev => [...prev.slice(-199), mkLog(level, msg)])
  }, [])

  const markAgent = useCallback((deptId: string, state: AgentNode['state']) => {
    setAgents(prev => prev.map(a => a.id === deptId ? { ...a, state } : a))
  }, [])

  const reset = useCallback(() => {
    sseRef.current?.close()
    sseRef.current = null
    setStatus('IDLE')
    setAgents(freshAgents())
    setResult(null)
    setLogs([
      mkLog('SYSTEM', 'AEGIS-Ω TACTICAL OPERATIONS CENTER — RESET'),
      mkLog('INFO',   'All 39 nodes standing by.'),
    ])
  }, [])

  const execute = useCallback(async (objective: string, mode: CollaborationMode, live: boolean) => {
    if (status !== 'IDLE') return
    setStatus('INITIALIZING')
    setAgents(freshAgents())
    setResult(null)
    addLog('SYSTEM', `OBJECTIVE RECEIVED — mode: ${mode.toUpperCase()}`)
    addLog('INFO',   `Objective: ${objective}`)
    addLog('INFO',   `Live Claude: ${live ? 'YES' : 'DEMO'}`)

    // POST /platform/executions — start async execution
    let executionId: string
    let streamUrl: string
    try {
      addLog('INFO', `Initiating async execution via ${BRIDGE}/platform/executions …`)
      const res = await fetch(`${BRIDGE}/platform/executions`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'x-api-key': apiKey },
        body: JSON.stringify({ objective, mode, live }),
      })
      if (!res.ok) {
        const err = await res.json().catch(() => ({ error: res.statusText }))
        throw new Error(`${res.status}: ${(err as { error?: string }).error ?? res.statusText}`)
      }
      const data = await res.json() as { execution_id: string; stream_url: string }
      executionId = data.execution_id
      streamUrl   = data.stream_url
      addLog('SUCCESS', `Execution initiated — ID: ${executionId.slice(0, 8)}…`)
    } catch (e) {
      addLog('ERROR', `Launch failed: ${String(e)}`)
      setStatus('ERROR')
      return
    }

    // GET /platform/executions/live — SSE stream
    setStatus('STREAMING')
    addLog('STREAM', `Opening SSE stream → ${streamUrl}`)

    const es = new EventSource(`${BRIDGE}${streamUrl}`)
    sseRef.current = es

    es.onmessage = (ev) => {
      let event: { type: string; payload: Record<string, unknown> }
      try { event = JSON.parse(ev.data as string) as typeof event }
      catch { return }

      const p = event.payload

      if (event.type === 'dag_step') {
        const deptId   = p['dept_id'] as string
        const deptName = p['dept_name'] as string
        const idx      = p['step_index'] as number
        const total    = p['total_steps'] as number
        markAgent(deptId, 'active')
        addLog('STREAM', `[${idx + 1}/${total}] ${deptId} ${deptName} — activating`)
      } else if (event.type === 'agent_event') {
        const deptId  = p['dept_id'] as string
        const preview = p['output_preview'] as string
        markAgent(deptId, 'done')
        addLog('SUCCESS', `${deptId} ✓  ${preview}`)
      } else if (event.type === 'completion') {
        const r = p as unknown as CollaborationResult
        setResult(r)
        setAgents(prev => prev.map(a => ({ ...a, state: 'done' as const })))
        addLog('SYSTEM', `CYCLE COMPLETE — ${r.departments_collaborated} depts · verdict: ${r.constitutional_audit.verdict}`)
        addLog('INFO',   `Chain hash: ${r.audit_chain_hash.slice(0, 16)}…`)
        setStatus('COMPLETE')
        es.close()
        sseRef.current = null
      } else if (event.type === 'error') {
        addLog('ERROR', `Stream error: ${p['message'] as string}`)
        setStatus('ERROR')
        es.close()
        sseRef.current = null
      } else if (event.type === 'heartbeat') {
        addLog('INFO', `♥ heartbeat #${p['seq'] as number}`)
      }
    }

    es.onerror = () => {
      addLog('ERROR', 'SSE connection lost')
      setStatus(prev => prev === 'COMPLETE' ? 'COMPLETE' : 'ERROR')
      es.close()
      sseRef.current = null
    }
  }, [status, apiKey, addLog, markAgent])

  return { status, agents, logs, result, execute, reset }
}
