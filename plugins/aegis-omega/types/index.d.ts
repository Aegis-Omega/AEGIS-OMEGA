export type LedgerEntry = { at: number; kind: 'push' | 'shield'; text: string }
export type Stats = { prompts: number; calls: number; pushes: number; blocked: number }

declare module 'claude-code' {
  interface PluginState {
    'aegis-omega': { ledger: Shaped<LedgerEntry[]>; stats: Shaped<Stats> }
  }
}
