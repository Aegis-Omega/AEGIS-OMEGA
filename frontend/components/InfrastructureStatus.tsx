import React from 'react';
import { Globe, Database, Cloud, Lock } from 'lucide-react';
import { LOAD_BALANCER_IP } from '../constants';

export const InfrastructureStatus: React.FC = () => {
  const items = [
    { icon: Globe, label: 'CLOUDFLARE_DNS', status: 'ROUTED', detail: LOAD_BALANCER_IP, color: 'text-blue-400' },
    { icon: Lock, label: 'GCP_IAM', status: 'BOUND', detail: 'roles/aiplatform.user', color: 'text-aegis-accent' },
    { icon: Cloud, label: 'CLOUD_RUN', status: 'LIVE', detail: 'AEGIS_SWARM_MODEL=claude-opus', color: 'text-aegis-accent' },
    { icon: Database, label: 'APPS_SCRIPT', status: 'DEPLOYED', detail: '/exec Webhook Active', color: 'text-aegis-accent' },
  ];

  return (
    <div className="bg-aegis-panel border border-aegis-border rounded-md p-4">
      <h3 className="text-sm font-mono text-aegis-text mb-4 border-b border-aegis-border pb-2">
        INFRASTRUCTURE_TELEMETRY
      </h3>
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        {items.map((item, idx) => (
          <div key={idx} className="flex items-start space-x-3 bg-aegis-dark p-3 rounded border border-aegis-border/50">
            <item.icon size={20} className={`mt-1 ${item.color}`} />
            <div>
              <div className="text-xs font-mono text-aegis-text/70">{item.label}</div>
              <div className={`text-sm font-mono font-bold ${item.color}`}>{item.status}</div>
              <div className="text-[10px] font-mono text-aegis-text/50 mt-1 truncate w-32" title={item.detail}>
                {item.detail}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};
