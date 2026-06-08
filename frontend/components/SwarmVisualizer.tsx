import React from 'react';
import { AgentStatus } from '../types';
import { Cpu } from 'lucide-react';

interface SwarmVisualizerProps {
  agents: AgentStatus[];
  status: string;
}

export const SwarmVisualizer: React.FC<SwarmVisualizerProps> = ({ agents, status }) => {
  return (
    <div className="bg-aegis-panel border border-aegis-border rounded-md p-4">
      <div className="flex justify-between items-center mb-4">
        <h3 className="text-sm font-mono text-aegis-accent flex items-center">
          <Cpu size={16} className="mr-2" />
          SWARM_TOPOLOGY (39 NODES)
        </h3>
        <span className="text-xs font-mono text-aegis-text bg-aegis-dark px-2 py-1 rounded border border-aegis-border">
          STATUS: {status}
        </span>
      </div>
      
      <div className="grid grid-cols-13 gap-2 sm:grid-cols-8 md:grid-cols-10 lg:grid-cols-13">
        {agents.map((agent) => {
          let bgColor = 'bg-aegis-dark';
          let borderColor = 'border-aegis-border';
          let animation = '';

          if (agent.state === 'active') {
            bgColor = 'bg-aegis-accent/20';
            borderColor = 'border-aegis-accent';
            animation = 'animate-pulse';
          } else if (agent.state === 'done') {
            bgColor = 'bg-aegis-accent/10';
            borderColor = 'border-aegis-accent/50';
          }

          return (
            <div
              key={agent.id}
              title={`Node ${agent.id} - ${agent.department}`}
              className={`
                w-full aspect-square rounded-sm border flex items-center justify-center
                transition-colors duration-300 ${bgColor} ${borderColor} ${animation}
              `}
            >
              <span className="text-[8px] font-mono text-aegis-text/50">{agent.id}</span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
