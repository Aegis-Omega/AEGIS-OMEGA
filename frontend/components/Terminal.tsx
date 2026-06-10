import React, { useEffect, useRef } from 'react';
import { LogEntry } from '../types';

interface TerminalProps {
  logs: LogEntry[];
}

export const Terminal: React.FC<TerminalProps> = ({ logs }) => {
  const endOfLogsRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    endOfLogsRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  const getColorForLevel = (level: LogEntry['level']) => {
    switch (level) {
      case 'INFO': return 'text-aegis-text';
      case 'WARN': return 'text-aegis-warning';
      case 'ERROR': return 'text-aegis-danger';
      case 'SUCCESS': return 'text-aegis-accent';
      case 'SYSTEM': return 'text-blue-400';
      default: return 'text-aegis-text';
    }
  };

  return (
    <div className="bg-black border border-aegis-border rounded-md p-4 h-64 overflow-y-auto font-mono text-xs shadow-inner">
      <div className="flex items-center mb-2 pb-2 border-b border-aegis-border/50 text-aegis-text/50">
        <span className="mr-2">AEGIS-Ω // SYSTEM_LOGS</span>
        <div className="flex-grow"></div>
        <span className="animate-pulse">_</span>
      </div>
      <div className="space-y-1">
        {logs.map((log) => (
          <div key={log.id} className="flex items-start">
            <span className="text-gray-600 mr-3 shrink-0">[{log.timestamp}]</span>
            <span className={`mr-2 shrink-0 ${getColorForLevel(log.level)}`}>
              [{log.level}]
            </span>
            <span className={`${getColorForLevel(log.level)} break-all`}>
              {log.message}
            </span>
          </div>
        ))}
        <div ref={endOfLogsRef} />
      </div>
    </div>
  );
};
