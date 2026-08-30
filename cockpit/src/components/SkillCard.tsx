interface SkillCardProps {
  skillId: string
  name: string
  confidence: number
  domains: string[]
  source: string
  tier: string
  onInstall?: (skillId: string) => void
  installStatus?: 'idle' | 'installing' | 'installed' | 'rejected'
}

export function SkillCard({
  skillId,
  name,
  confidence,
  domains,
  source,
  tier,
  onInstall,
  installStatus = 'idle',
}: SkillCardProps) {
  const pct = Math.round(confidence * 100)
  const statusColor = installStatus === 'installed'
    ? 'text-green-400'
    : installStatus === 'rejected'
    ? 'text-red-400'
    : installStatus === 'installing'
    ? 'text-yellow-400'
    : 'text-aegis-muted'

  return (
    <div className="border border-aegis-border rounded-lg p-3 bg-aegis-surface/40 hover:bg-aegis-surface/70 transition-colors">
      <div className="flex items-start justify-between gap-2 mb-2">
        <div>
          <span className="text-xs font-mono text-aegis-text">{name}</span>
          <span className={`ml-2 text-[10px] ${tier === 'T0' ? 'text-blue-400' : tier === 'T1' ? 'text-green-400' : 'text-aegis-muted'}`}>
            {tier}
          </span>
        </div>
        {onInstall && installStatus !== 'installed' && (
          <button
            onClick={() => onInstall(skillId)}
            disabled={installStatus === 'installing'}
            className="text-[10px] px-2 py-0.5 rounded border border-aegis-border text-aegis-muted hover:text-aegis-text hover:border-aegis-text transition-colors disabled:opacity-50"
          >
            {installStatus === 'installing' ? '…' : 'Install'}
          </button>
        )}
        {installStatus === 'installed' && (
          <span className="text-[10px] text-green-400">✓ Active</span>
        )}
      </div>

      {/* Confidence bar */}
      <div className="flex items-center gap-2 mb-2">
        <div className="flex-1 h-1 bg-aegis-border rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-600 to-blue-400 rounded-full transition-all"
            style={{ width: `${pct}%` }}
          />
        </div>
        <span className="text-[10px] text-aegis-muted w-7 text-right">{pct}%</span>
      </div>

      <div className="flex flex-wrap gap-1 mb-1">
        {domains.map(d => (
          <span key={d} className="text-[9px] px-1.5 py-0.5 rounded-full bg-aegis-border/50 text-aegis-muted">
            {d}
          </span>
        ))}
      </div>

      <div className={`text-[9px] truncate ${statusColor}`}>
        {installStatus !== 'idle' ? installStatus : source}
      </div>
    </div>
  )
}
