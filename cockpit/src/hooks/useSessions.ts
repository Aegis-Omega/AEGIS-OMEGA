import { useState, useCallback } from 'react'
import type { ChatMessage } from '../lib/agent.js'

export interface Session {
  id: string
  title: string
  messages: ChatMessage[]
  createdAt: number
}

const KEY = 'aegis-cockpit-sessions'

function load(): Session[] {
  try {
    return JSON.parse(localStorage.getItem(KEY) ?? '[]') as Session[]
  } catch {
    return []
  }
}

function save(sessions: Session[]): void {
  localStorage.setItem(KEY, JSON.stringify(sessions))
}

export function useSessions() {
  const [sessions, setSessions] = useState<Session[]>(load)
  const [activeId, setActiveId] = useState<string | null>(
    () => load()[0]?.id ?? null,
  )

  const activeSession = sessions.find(s => s.id === activeId) ?? null

  const createSession = useCallback(() => {
    const id = crypto.randomUUID()
    const session: Session = { id, title: 'New chat', messages: [], createdAt: Date.now() }
    setSessions(prev => {
      const next = [session, ...prev]
      save(next)
      return next
    })
    setActiveId(id)
    return id
  }, [])

  const updateSession = useCallback((id: string, messages: ChatMessage[]) => {
    setSessions(prev => {
      const next = prev.map(s => {
        if (s.id !== id) return s
        const firstUser = messages.find(m => m.role === 'user')?.content ?? 'New chat'
        const title = firstUser.length > 40 ? firstUser.slice(0, 40) + '…' : firstUser
        return { ...s, messages, title }
      })
      save(next)
      return next
    })
  }, [])

  const deleteSession = useCallback((id: string) => {
    setSessions(prev => {
      const next = prev.filter(s => s.id !== id)
      save(next)
      if (activeId === id) setActiveId(next[0]?.id ?? null)
      return next
    })
  }, [activeId])

  return { sessions, activeSession, activeId, setActiveId, createSession, updateSession, deleteSession }
}
