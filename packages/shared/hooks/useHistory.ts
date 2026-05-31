import { useState, useCallback } from 'react'

const MAX = 10

export interface HistoryEntry<I, R> {
  id: string
  ts: number
  label: string
  input: I
  result: R
}

export function useHistory<I, R>(storageKey: string, makeLabel: (input: I) => string) {
  function load(): HistoryEntry<I, R>[] {
    try { return JSON.parse(localStorage.getItem(storageKey) ?? '[]') as HistoryEntry<I, R>[] }
    catch { return [] }
  }

  const [entries, setEntries] = useState<HistoryEntry<I, R>[]>(load)

  const addEntry = useCallback((input: I, result: R) => {
    const entry: HistoryEntry<I, R> = {
      id: `${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      ts: Date.now(),
      label: makeLabel(input),
      input,
      result,
    }
    setEntries(prev => {
      const next = [entry, ...prev].slice(0, MAX)
      try { localStorage.setItem(storageKey, JSON.stringify(next)) } catch { /* quota */ }
      return next
    })
  }, [storageKey, makeLabel])

  const clearHistory = useCallback(() => {
    try { localStorage.removeItem(storageKey) } catch { /* noop */ }
    setEntries([])
  }, [storageKey])

  return { entries, addEntry, clearHistory }
}
