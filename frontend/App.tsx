import React, { useState, useCallback, useRef } from 'react';
import { Terminal } from './components/Terminal';
import { SwarmVisualizer } from './components/SwarmVisualizer';
import { ControlPanel } from './components/ControlPanel';
import { InfrastructureStatus } from './components/InfrastructureStatus';
import { SystemStatus, LogEntry, AgentStatus } from './types';
import { DEPARTMENTS, MOCK_WEBHOOK_URL } from './constants';
import { Activity, ShieldCheck } from 'lucide-react';
import { GoogleGenAI } from '@google/genai';
import { runtimeConfig } from './resources/react-calligraphy-studio-application-99081472/config';

declare var process: any;

const generateInitialAgents = (): AgentStatus[] => {
  return Array.from({ length: 39 }, (_, i) => ({
    id: i + 1,
    state: 'idle',
    department: DEPARTMENTS[i % DEPARTMENTS.length]
  }));
};

const App: React.FC = () => {
  const [status, setStatus] = useState<SystemStatus>('IDLE');
  const [logs, setLogs] = useState<LogEntry[]>([
    { id: 'init', timestamp: new Date().toISOString().split('T')[1].slice(0, -1), level: 'SYSTEM', message: 'AEGIS-Ω AUTOMATION ARCHITECTURE INITIATED.' },
    { id: 'init2', timestamp: new Date().toISOString().split('T')[1].slice(0, -1), level: 'INFO', message: 'Awaiting external trigger or manual override.' }
  ]);
  const [agents, setAgents] = useState<AgentStatus[]>(generateInitialAgents());
  const [consensusReport, setConsensusReport] = useState<string | null>(null);
  
  const logIdCounter = useRef(0);

  const addLog = useCallback((level: LogEntry['level'], message: string) => {
    const now = new Date();
    const timestamp = now.toISOString().split('T')[1].slice(0, -1); // HH:MM:SS.mmm
    logIdCounter.current += 1;
    setLogs(prev => [...prev, { id: `log-${logIdCounter.current}`, timestamp, level, message }]);
  }, []);

  const delay = (ms: number) => new Promise(resolve => setTimeout(resolve, ms));

  const executeSwarmSimulation = async (objective: string, mode: string) => {
    setStatus('INITIALIZING');
    setAgents(generateInitialAgents()); // Reset agents
    setConsensusReport(null);
    
    addLog('SYSTEM', `MANUAL OVERRIDE ACCEPTED. Waking AEGIS-Ω Swarm...`);
    addLog('INFO', `Objective: ${objective}`);
    addLog('INFO', `Mode: ${mode}`);
    
    await delay(1000);
    setStatus('PROCESSING');
    addLog('INFO', `Routing request via Cloudflare Load Balancer...`);
    
    await delay(800);
    addLog('SUCCESS', `GCP Vertex AI IAM verified. Allocating compute resources.`);
    
    // Simulate agent processing
    const totalAgents = 39;
    const batchSize = 13;
    
    for (let i = 0; i < totalAgents; i += batchSize) {
      setAgents(prev => {
        const next = [...prev];
        for (let j = i; j < Math.min(i + batchSize, totalAgents); j++) {
          next[j].state = 'active';
        }
        return next;
      });
      
      addLog('INFO', `Nodes [${i+1}-${Math.min(i + batchSize, totalAgents)}] analyzing data streams...`);
      await delay(600 + Math.random() * 400);
      
      setAgents(prev => {
        const next = [...prev];
        for (let j = i; j < Math.min(i + batchSize, totalAgents); j++) {
          next[j].state = 'done';
        }
        return next;
      });
    }

    addLog('SYSTEM', `Querying Gemini AI for BFT Consensus...`);
    
    try {
      const ai = new GoogleGenAI({ apiKey: process.env.API_KEY, vertexai: true });
      const response = await ai.models.generateContent({
        model: 'gemini-2.5-flash',
        contents: `Execute a tactical analysis for the following objective.\nObjective: ${objective}\nOperational Mode: ${mode}\nProvide a brief, highly technical, 2-sentence consensus report from the perspective of a 39-node AI swarm.`,
        config: {
          temperature: runtimeConfig.parameters?.temperature ?? 0.7,
          topP: runtimeConfig.parameters?.topP ?? 0.95,
        }
      });
      
      const report = response.text || "Consensus reached. No anomalies detected.";
      setConsensusReport(report);
      addLog('SUCCESS', `Swarm consensus reached. Payload generated.`);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Unknown error';
      setConsensusReport(`ERROR: Consensus failed. ${errorMessage}`);
      addLog('ERROR', `AI Consensus failure: ${errorMessage}`);
    }

    await delay(1000);
    
    setStatus('AWAITING_WEBHOOK');
    addLog('SYSTEM', `Initiating POST request to Google Apps Script Webhook...`);
    addLog('INFO', `Target: ${MOCK_WEBHOOK_URL}`);
    
    await delay(1500);
    
    addLog('SUCCESS', `Webhook acknowledged. Status: 200 OK.`);
    addLog('INFO', `Google Sheets tactical layout updated silently.`);
    
    setStatus('COMPLETED');
    addLog('SYSTEM', `CYCLE COMPLETE. Returning to standby.`);
  };

  return (
    <div className="min-h-screen p-4 md:p-8 flex flex-col space-y-6 max-w-7xl mx-auto">
      {/* Header */}
      <header className="flex items-center justify-between border-b border-aegis-border pb-4">
        <div className="flex items-center space-x-3">
          <div className="bg-aegis-accent/20 p-2 rounded border border-aegis-accent">
            <Activity className="text-aegis-accent animate-pulse" size={24} />
          </div>
          <div>
            <h1 className="text-xl font-mono font-bold text-white tracking-wider">AEGIS-Ω</h1>
            <h2 className="text-xs font-mono text-aegis-text tracking-widest">AUTOMATION ARCHITECTURE</h2>
          </div>
        </div>
        <div className="text-right font-mono text-xs">
          <div className="text-aegis-text">SYSTEM_STATE</div>
          <div className={`font-bold ${status === 'PROCESSING' ? 'text-aegis-warning animate-pulse' : status === 'COMPLETED' ? 'text-aegis-accent' : 'text-aegis-text'}`}>
            [{status}]
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        
        {/* Left Column: Controls & Visualizer */}
        <div className="lg:col-span-1 space-y-6 flex flex-col">
          <ControlPanel status={status} onTrigger={executeSwarmSimulation} />
          <SwarmVisualizer agents={agents} status={status} />
          
          {consensusReport && (
            <div className="bg-aegis-panel border border-aegis-accent rounded-md p-4 animate-fade-in shadow-[0_0_15px_rgba(0,255,157,0.1)]">
              <h3 className="text-sm font-mono text-aegis-accent mb-3 flex items-center border-b border-aegis-accent/30 pb-2">
                <ShieldCheck size={16} className="mr-2" />
                BFT_CONSENSUS_REPORT
              </h3>
              <p className="text-sm font-mono text-white leading-relaxed">
                {consensusReport}
              </p>
            </div>
          )}
        </div>

        {/* Right Column: Infrastructure & Terminal */}
        <div className="lg:col-span-2 space-y-6 flex flex-col">
          <InfrastructureStatus />
          <div className="flex-grow flex flex-col">
            <h3 className="text-sm font-mono text-aegis-text mb-2">EXECUTION_TRACE</h3>
            <Terminal logs={logs} />
          </div>
        </div>

      </main>
    </div>
  );
};

export default App;
