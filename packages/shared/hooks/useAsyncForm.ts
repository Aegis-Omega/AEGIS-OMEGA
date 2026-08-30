import { useState, useCallback, useRef } from 'react'

export type AsyncFormState = 'idle' | 'loading' | 'results' | 'error'

export interface UseAsyncFormReturn<I, R> {
  state: AsyncFormState
  result: R | null
  errorMsg: string
  submit: (input: I) => Promise<void>
  reset: () => void
}

export function useAsyncForm<I, R>(
  fetcher: (input: I) => Promise<R>,
): UseAsyncFormReturn<I, R> {
  const [state, setState] = useState<AsyncFormState>('idle')
  const [result, setResult] = useState<R | null>(null)
  const [errorMsg, setErrorMsg] = useState('')
  const loadingRef = useRef(false)

  const submit = useCallback(
    async (input: I) => {
      if (loadingRef.current) return
      loadingRef.current = true
      setState('loading')
      try {
        setResult(await fetcher(input))
        setState('results')
      } catch (err) {
        setErrorMsg((err as Error).message)
        setState('error')
      } finally {
        loadingRef.current = false
      }
    },
    [fetcher],
  )

  const reset = useCallback(() => {
    setState('idle')
    setResult(null)
    setErrorMsg('')
  }, [])

  return { state, result, errorMsg, submit, reset }
}
