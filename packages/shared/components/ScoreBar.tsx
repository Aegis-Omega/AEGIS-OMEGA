interface ScoreBarProps {
  score: number
  max?: number
  colorClass?: string
}

export function ScoreBar({ score, max = 10, colorClass = 'bg-current' }: ScoreBarProps) {
  const pct = Math.min(100, (score / max) * 100)
  return (
    <div className="flex items-center gap-2">
      <div className="flex-1 bg-white/10 rounded-full h-1.5">
        <div
          className={`h-1.5 rounded-full transition-all ${colorClass}`}
          style={{ width: `${pct}%` }}
        />
      </div>
      <span className="text-xs font-medium tabular-nums">{score}</span>
    </div>
  )
}
