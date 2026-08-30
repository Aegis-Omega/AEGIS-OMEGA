import { AlertCircle } from 'lucide-react'

export function ErrorAlert({ message }: { message: string }) {
  return (
    <div className="flex items-start gap-2 text-red-400 bg-red-400/10 border border-red-400/20 rounded-xl px-4 py-3 text-sm">
      <AlertCircle size={16} className="mt-0.5 shrink-0" />
      <span>{message}</span>
    </div>
  )
}
