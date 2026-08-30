const GATES = [
  { n: 1, name: 'RFC 8785 JCS',      cmd: 'npm run test -- test/unit/jcs.test.ts',       tier: 'T0' },
  { n: 2, name: 'Atomic Sequences',  cmd: 'npm run test -- test/unit/sequence.test.ts',   tier: 'T0' },
  { n: 3, name: 'Immutability',      cmd: 'npm run test -- test/unit/immutable.test.ts',  tier: 'T0' },
  { n: 4, name: 'Pure Reducers',     cmd: 'npm run test -- test/unit/reducer.test.ts',    tier: 'T0' },
  { n: 5, name: 'VCG Calibration',   cmd: 'npm run test -- test/unit/vcg.test.ts',        tier: 'T1' },
  { n: 6, name: 'Bernstein Bounds',  cmd: 'npm run test -- test/unit/gate.test.ts',       tier: 'T1' },
  { n: 7, name: 'Integration',       cmd: 'npm run test -- test/integration/',             tier: 'T0' },
  { n: 8, name: 'Deployment Gate',   cmd: 'npm run test && npm run typecheck && npm run build', tier: 'T0' },
] as const

export function GateTable() {
  return (
    <section className="bg-omega-surface border border-omega-border rounded-lg p-5">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-omega-text text-sm font-bold tracking-wider uppercase">Eight-Gate Protocol</h2>
        <span className="text-xs text-omega-muted">Failure = HALT</span>
      </div>
      <div>
        {GATES.map(g => (
          <div
            key={g.n}
            className="flex items-start gap-3 py-2.5 border-b border-omega-border last:border-0"
          >
            <span className="shrink-0 w-6 h-6 flex items-center justify-center rounded bg-omega-accent/20 text-omega-glow text-xs font-bold">
              {g.n}
            </span>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-0.5">
                <span className="text-omega-text text-xs font-semibold">{g.name}</span>
                <span className="text-[10px] text-omega-muted border border-omega-border px-1 rounded">
                  {g.tier}
                </span>
              </div>
              <code className="text-[10px] text-omega-muted/70 break-all leading-relaxed">
                {g.cmd}
              </code>
            </div>
          </div>
        ))}
      </div>
    </section>
  )
}
