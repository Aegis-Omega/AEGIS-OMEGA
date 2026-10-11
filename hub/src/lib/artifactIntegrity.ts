/** AEGIS public research utility: digest and optional byte-integrity comparison.
 *  This has no network IO, signatures, admission authority or analytics calls.
 */
export const MAX_ARTIFACT_SIZE = 32 * 1024 * 1024
export type IntegrityVerdict = 'computed' | 'matched' | 'mismatch'
export interface IntegrityResult { digest: string; verdict: IntegrityVerdict; bytes: number }

export function normalizeExpectedDigest(value: string): string | null {
  const expected = value.trim().replace(/^sha256:/i, '').toLowerCase()
  if (expected === '') return null
  if (!/^[a-f0-9]{64}$/.test(expected)) {
    throw new Error('Expected SHA-256 must contain exactly 64 hexadecimal characters.')
  }
  return expected
}

/** Verify only the bytes, relative to a caller-supplied expected digest.
 * Callers must independently establish whether an expected digest is trustworthy.
 */
export async function verifyArtifactBytes(
  file: Blob,
  expectedText: string,
  subtle: SubtleCrypto | undefined = globalThis.crypto?.subtle,
): Promise<IntegrityResult> {
  if (file.size > MAX_ARTIFACT_SIZE) throw new Error('Maximum 32 MiB. Large files require a streaming verifier.')
  const expected = normalizeExpectedDigest(expectedText)
  if (!subtle) throw new Error('Secure-context SHA-256 implementation is unavailable.')
  const bytes = await file.arrayBuffer()
  const result = await subtle.digest('SHA-256', bytes)
  const digest = Array.from(new Uint8Array(result), b => b.toString(16).padStart(2, '0')).join('')
  return {
    digest,
    bytes: file.size,
    verdict: expected === null ? 'computed' : digest === expected ? 'matched' : 'mismatch',
  }
}