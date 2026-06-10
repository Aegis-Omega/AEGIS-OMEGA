// Local types for the tactical dashboard — aligned with packages/shared/lib/platform-contract.ts

export type CollaborationMode =
  | 'revenue' | 'analysis' | 'gtm' | 'retention'
  | 'competitive' | 'technical' | 'regulatory' | 'fundraising'

export type SseEventType = 'dag_step' | 'agent_event' | 'tool_call' | 'error' | 'completion' | 'heartbeat'

export interface SseEvent {
  type: SseEventType
  execution_id: string
  timestamp: string
  payload: Record<string, unknown>
}

export interface CollaborationResult {
  cycle_id: string
  objective: string
  mode: CollaborationMode
  departments_collaborated: number
  artifacts: readonly { role: string; output: string }[]
  projection: {
    first_year_arr_usd?: number
    tier?: string
    governed_note?: string
  }
  constitutional_audit: {
    verdict: 'APPROVED' | 'FLAG' | 'QUARANTINE'
    concerns?: string[]
  }
  chain_valid: boolean
  audit_chain_hash: string
  execution_id: string
}

export type AgentState = 'idle' | 'active' | 'done' | 'error'

export interface AgentNode {
  id: string       // dept_id e.g. 'REV-01'
  role: string
  category: string
  state: AgentState
  index: number    // 0–38
}

export type SystemStatus = 'IDLE' | 'INITIALIZING' | 'STREAMING' | 'COMPLETE' | 'ERROR'

export interface LogEntry {
  id: string
  ts: string
  level: 'SYSTEM' | 'INFO' | 'SUCCESS' | 'WARN' | 'ERROR' | 'STREAM'
  message: string
}

export const DEPARTMENTS: readonly { id: string; role: string; category: string }[] = [
  { id: 'REV-01', role: 'Strategy',    category: 'revenue'        },
  { id: 'REV-02', role: 'Finance',     category: 'revenue'        },
  { id: 'REV-03', role: 'Pricing',     category: 'revenue'        },
  { id: 'MKT-01', role: 'Brand',       category: 'marketing'      },
  { id: 'MKT-02', role: 'Content',     category: 'marketing'      },
  { id: 'MKT-03', role: 'SEO',         category: 'marketing'      },
  { id: 'MKT-04', role: 'Paid',        category: 'marketing'      },
  { id: 'MKT-05', role: 'Social',      category: 'marketing'      },
  { id: 'SLS-01', role: 'Outbound',    category: 'sales'          },
  { id: 'SLS-02', role: 'Inbound',     category: 'sales'          },
  { id: 'SLS-03', role: 'Partner',     category: 'sales'          },
  { id: 'SLS-04', role: 'Enterprise',  category: 'sales'          },
  { id: 'PRD-01', role: 'Product',     category: 'product'        },
  { id: 'PRD-02', role: 'UX',          category: 'product'        },
  { id: 'PRD-03', role: 'Data',        category: 'product'        },
  { id: 'PRD-04', role: 'API',         category: 'product'        },
  { id: 'ENG-01', role: 'Backend',     category: 'engineering'    },
  { id: 'ENG-02', role: 'Frontend',    category: 'engineering'    },
  { id: 'ENG-03', role: 'Infra',       category: 'engineering'    },
  { id: 'ENG-04', role: 'Security',    category: 'engineering'    },
  { id: 'ENG-05', role: 'AI/ML',       category: 'engineering'    },
  { id: 'OPS-01', role: 'RevOps',      category: 'operations'     },
  { id: 'OPS-02', role: 'Support',     category: 'operations'     },
  { id: 'OPS-03', role: 'Legal',       category: 'operations'     },
  { id: 'OPS-04', role: 'Compliance',  category: 'operations'     },
  { id: 'RES-01', role: 'Research',    category: 'research'       },
  { id: 'RES-02', role: 'Competitive', category: 'research'       },
  { id: 'RES-03', role: 'Customer',    category: 'research'       },
  { id: 'FIN-01', role: 'Accounting',  category: 'finance'        },
  { id: 'FIN-02', role: 'Treasury',    category: 'finance'        },
  { id: 'FIN-03', role: 'Tax',         category: 'finance'        },
  { id: 'EXE-01', role: 'CEO',         category: 'executive'      },
  { id: 'EXE-02', role: 'COO',         category: 'executive'      },
  { id: 'EXE-03', role: 'CTO',         category: 'executive'      },
  { id: 'EXE-04', role: 'CFO',         category: 'executive'      },
  { id: 'GOV-01', role: 'Ethics',      category: 'governance'     },
  { id: 'GOV-02', role: 'Risk',        category: 'governance'     },
  { id: 'CON-01', role: 'Audit',       category: 'constitutional' },
  { id: 'CON-09', role: 'Guardian',    category: 'constitutional' },
]

export const CATEGORY_COLOR: Record<string, string> = {
  revenue:        'border-emerald-500 bg-emerald-500/20 text-emerald-400',
  marketing:      'border-blue-500 bg-blue-500/20 text-blue-400',
  sales:          'border-cyan-500 bg-cyan-500/20 text-cyan-400',
  product:        'border-purple-500 bg-purple-500/20 text-purple-400',
  engineering:    'border-orange-500 bg-orange-500/20 text-orange-400',
  operations:     'border-yellow-500 bg-yellow-500/20 text-yellow-400',
  research:       'border-pink-500 bg-pink-500/20 text-pink-400',
  finance:        'border-teal-500 bg-teal-500/20 text-teal-400',
  executive:      'border-red-500 bg-red-500/20 text-red-400',
  governance:     'border-amber-500 bg-amber-500/20 text-amber-400',
  constitutional: 'border-white bg-white/20 text-white',
}
