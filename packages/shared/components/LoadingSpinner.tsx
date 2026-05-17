import { Loader2 } from 'lucide-react'

interface LoadingSpinnerProps {
  message?: string
  colorClass?: string
}

export function LoadingSpinner({
  message = 'Loading…',
  colorClass = 'text-current',
}: LoadingSpinnerProps) {
  return (
    <div className="text-center py-20">
      <Loader2 size={36} className={`animate-spin ${colorClass} mx-auto mb-4`} />
      {message && <p className="text-sm opacity-60">{message}</p>}
    </div>
  )
}
