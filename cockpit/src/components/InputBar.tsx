import { useRef, type KeyboardEvent } from 'react'
import { Send, StopCircle } from 'lucide-react'

interface InputBarProps {
  value: string
  streaming: boolean
  onChange: (v: string) => void
  onSend: () => void
  onStop: () => void
}

export function InputBar({ value, streaming, onChange, onSend, onStop }: InputBarProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      onSend()
    }
  }

  return (
    <div className="px-5 py-4" style={{ borderTop: '1px solid #1E1E22' }}>
      <div
        className="flex gap-3 px-4 py-3 rounded-2xl transition-all"
        style={{
          background: '#141416',
          border: '1px solid #1E1E22',
        }}
        onFocusCapture={e => {
          (e.currentTarget as HTMLElement).style.borderColor = '#2A2A30'
        }}
        onBlurCapture={e => {
          (e.currentTarget as HTMLElement).style.borderColor = '#1E1E22'
        }}
      >
        <textarea
          ref={textareaRef}
          value={value}
          onChange={e => onChange(e.target.value)}
          onKeyDown={handleKey}
          placeholder="Invoke the constitutional pipeline…"
          rows={1}
          className="flex-1 bg-transparent text-sm resize-none focus:outline-none max-h-32 overflow-y-auto"
          style={{
            color: '#ECEAE3',
            lineHeight: '1.6',
          }}
        />
        <button
          onClick={streaming ? onStop : onSend}
          disabled={!streaming && !value.trim()}
          aria-label={streaming ? 'Stop generation' : 'Send message'}
          className="self-end transition-all shrink-0 disabled:opacity-25"
          style={{
            color: streaming ? '#F87171' : value.trim() ? '#C8A96E' : '#6B6B7A',
          }}
        >
          {streaming
            ? <StopCircle size={18} />
            : <Send size={16} />
          }
        </button>
      </div>
      <p
        className="text-center font-mono text-xs mt-2 opacity-20"
        style={{ color: '#6B6B7A' }}
      >
        Constitutional pipeline · Claude Sonnet 4.6 · hash-certified
      </p>
    </div>
  )
}
