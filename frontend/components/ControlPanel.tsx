import React, { useState } from 'react';
import { Play, Clock, ShieldAlert } from 'lucide-react';
import { SystemStatus } from '../types';
import { DEPARTMENTS } from '../constants';

interface ControlPanelProps {
  status: SystemStatus;
  onTrigger: (objective: string, mode: string) => void;
}

export const ControlPanel: React.FC<ControlPanelProps> = ({ status, onTrigger }) => {
  const [objective, setObjective] = useState("Execute automated compliance and margin assessment.");
  const [mode, setMode] = useState(DEPARTMENTS[0]);

  const isBusy = status !== 'IDLE' && status !== 'COMPLETED' && status !== 'ERROR';

  const handleFire = () => {
    if (!isBusy) {
      onTrigger(objective, mode);
    }
  };

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded-md p-4 flex flex-col h-full">
      <h3 className="text-sm font-mono text-aegis-text mb-4 flex items-center border-b border-aegis-border pb-2">
        <ShieldAlert size={16} className="mr-2 text-aegis-warning" />
        MANUAL_OVERRIDE_CONTROLS
      </h3>

      <div className="space-y-4 flex-grow">
        <div>
          <label className="block text-xs font-mono text-aegis-text/70 mb-1">OBJECTIVE_DIRECTIVE</label>
          <textarea
            value={objective}
            onChange={(e) => setObjective(e.target.value)}
            disabled={isBusy}
            className="w-full bg-aegis-dark border border-aegis-border rounded p-2 text-sm font-mono text-aegis-text focus:border-aegis-accent focus:outline-none disabled:opacity-50 resize-none h-20"
          />
        </div>

        <div>
          <label className="block text-xs font-mono text-aegis-text/70 mb-1">OPERATIONAL_MODE</label>
          <select
            value={mode}
            onChange={(e) => setMode(e.target.value)}
            disabled={isBusy}
            className="w-full bg-aegis-dark border border-aegis-border rounded p-2 text-sm font-mono text-aegis-text focus:border-aegis-accent focus:outline-none disabled:opacity-50 appearance-none"
          >
            {DEPARTMENTS.map(d => <option key={d} value={d}>{d}</option>)}
          </select>
        </div>
      </div>

      <div className="mt-6 grid grid-cols-2 gap-2">
        <button
          onClick={handleFire}
          disabled={isBusy}
          className={`
            flex items-center justify-center py-2 px-4 rounded font-mono text-sm transition-all
            ${isBusy 
              ? 'bg-aegis-border text-aegis-text/50 cursor-not-allowed' 
              : 'bg-aegis-accent/10 text-aegis-accent border border-aegis-accent hover:bg-aegis-accent hover:text-black'}
          `}
        >
          <Play size={16} className="mr-2" />
          {isBusy ? 'EXECUTING...' : 'INITIATE_SWARM'}
        </button>
        
        <button
          disabled={true}
          className="flex items-center justify-center py-2 px-4 rounded font-mono text-sm bg-aegis-dark border border-aegis-border text-aegis-text/50 cursor-not-allowed"
          title="Cron trigger managed via Apps Script"
        >
          <Clock size={16} className="mr-2" />
          CRON_ARMED (02:00)
        </button>
      </div>
    </div>
  );
};
