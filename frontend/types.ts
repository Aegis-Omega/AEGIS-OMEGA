export type SystemStatus = 'IDLE' | 'INITIALIZING' | 'PROCESSING' | 'AWAITING_WEBHOOK' | 'COMPLETED' | 'ERROR';

export interface LogEntry {
  id: string;
  timestamp: string;
  level: 'INFO' | 'WARN' | 'ERROR' | 'SUCCESS' | 'SYSTEM';
  message: string;
}

export interface AgentStatus {
  id: number;
  state: 'idle' | 'active' | 'done';
  department: string;
}