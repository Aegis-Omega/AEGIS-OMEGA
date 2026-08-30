import { useState, useRef, useCallback } from 'react'
import { streamChat, type ChatMessage, type Provider } from '../lib/agent.js'

export interface UseAgentReturn {
  messages: ChatMessage[]
  streaming: boolean
  error: string | null
  send: (text: string, contextOverride?: ChatMessage[]) => Promise<void>
  reset: () => void
  loadMessages: (msgs: ChatMessage[]) => void
}

export function useAgent(provider?: Provider): UseAgentReturn {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [streaming, setStreaming] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  const send = useCallback(async (text: string, contextOverride?: ChatMessage[]) => {
    if (streaming) return

    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller

    const base = contextOverride ?? messages
    const next: ChatMessage[] = [...base, { role: 'user', content: text }]
    setMessages(next)
    setStreaming(true)
    setError(null)

    let assistantContent = ''
    setMessages(prev => [...prev, { role: 'assistant', content: '' }])

    try {
      for await (const chunk of streamChat({ messages: next, signal: controller.signal, provider })) {
        assistantContent += chunk
        setMessages(prev => {
          const updated = [...prev]
          updated[updated.length - 1] = { role: 'assistant', content: assistantContent }
          return updated
        })
      }
    } catch (err) {
      if ((err as Error).name !== 'AbortError') {
        setError((err as Error).message)
        setMessages(prev => prev.slice(0, -1))
      }
    } finally {
      setStreaming(false)
    }
  }, [messages, streaming, provider])

  const reset = useCallback(() => {
    abortRef.current?.abort()
    setMessages([])
    setStreaming(false)
    setError(null)
  }, [])

  const loadMessages = useCallback((msgs: ChatMessage[]) => {
    abortRef.current?.abort()
    setMessages(msgs)
    setStreaming(false)
    setError(null)
  }, [])

  return { messages, streaming, error, send, reset, loadMessages }
}
