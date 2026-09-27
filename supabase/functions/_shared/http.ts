/**
 * Shared outbound HTTP transport for Supabase Edge Functions.
 *
 * Bounds request lifetime and error-body reads without adding retries. POST
 * retries remain a caller-level decision because many provider/payment calls
 * are not safely replayable without an idempotency contract.
 */

export const DEFAULT_OUTBOUND_TIMEOUT_MS = 60_000
export const DEFAULT_ERROR_BODY_LIMIT_BYTES = 2_048

function normalizePositiveInt(value: number, fallback: number): number {
  return Number.isFinite(value) && value > 0 ? Math.floor(value) : fallback
}

export async function fetchWithTimeout(
  input: Parameters<typeof fetch>[0],
  init: RequestInit = {},
  timeoutMs = DEFAULT_OUTBOUND_TIMEOUT_MS,
): Promise<Response> {
  const boundedTimeoutMs = normalizePositiveInt(timeoutMs, DEFAULT_OUTBOUND_TIMEOUT_MS)
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), boundedTimeoutMs)

  const callerSignal = init.signal
  const onCallerAbort = () => controller.abort()
  if (callerSignal) {
    if (callerSignal.aborted) controller.abort()
    else callerSignal.addEventListener('abort', onCallerAbort, { once: true })
  }

  try {
    return await fetch(input, { ...init, signal: controller.signal })
  } finally {
    clearTimeout(timer)
    callerSignal?.removeEventListener('abort', onCallerAbort)
  }
}

export async function readTextBounded(
  response: Response,
  maxBytes = DEFAULT_ERROR_BODY_LIMIT_BYTES,
): Promise<string> {
  const limit = normalizePositiveInt(maxBytes, DEFAULT_ERROR_BODY_LIMIT_BYTES)
  if (!response.body) return ''

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let remaining = limit
  let output = ''

  try {
    while (remaining > 0) {
      const { done, value } = await reader.read()
      if (done) break

      const chunk = value.byteLength > remaining ? value.subarray(0, remaining) : value
      output += decoder.decode(chunk, { stream: true })
      remaining -= chunk.byteLength

      if (chunk.byteLength < value.byteLength) {
        await reader.cancel()
        break
      }
    }
    output += decoder.decode()
    return output
  } finally {
    reader.releaseLock()
  }
}
