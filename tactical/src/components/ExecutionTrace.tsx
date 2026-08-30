import { Terminal } from 'lucide-react'
import { useEffect, useRef } from 'react'
import type { LogEntry } from '../types.js'

interface Props { logs: LogEntry[] }

const LEVEL_COLOR: Record<LogEntry['level'], string> = {
  SYSTEM:  'text-white font-bold',
  INFO:    'text-aegis-text',
  SUCCESS: 'text-aegis-accent',
  WARN:    'text-aegis-warn',
  ERROR:   'text-aegis-err',
  STREAM:  'text-aegis-dim',
}

const LEVEL_PREFIX: Record<LogEntry['level'], string> = {
  SYSTEM:  '[SYS]',
  INFO:    '[INF]',
  SUCCESS: '[OK ]',
  WARN:    '[WRN]',
  ERROR:   '[ERR]',
  STREAM:  '[SSE]',
}

export function ExecutionTrace({ logs }: Props) {
  const bottomRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [logs])

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded p-4 flex flex-col h-full min-h-0">
      <div className="flex items-center gap-2 mb-2 border-b border-aegis-border pb-2">
        <Terminal size={14} className="text-aegis-accent" />
        <span className="text-xs font-mono text-aegis-text tracking-widest">EXECUTION_TRACE</span>
        <span className="ml-auto text-[10px] font-mono text-aegis-text/40">{logs.length} events</span>
      </div>

      <div className="flex-1 overflow-y-auto terminal-scroll space-y-0.5 font-mono text-[11px]">
        {logs.map(entry => (
          <div key={entry.id} className="flex gap-2 leading-relaxed">
            <span className="text-aegis-text/30 shrink-0">{entry.ts}</span>
            <span className={`shrink-0 ${LEVEL_COLOR[entry.level]}`}>{LEVEL_PREFIX[entry.level]}</span>
            <span className={LEVEL_COLOR[entry.level]}>{entry.message}</span>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>
    </div>
  )
}
