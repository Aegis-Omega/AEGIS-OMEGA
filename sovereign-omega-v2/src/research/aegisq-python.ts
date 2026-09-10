// Node-only research verifier. Executable/source pins come from operator config,
// never from the request. Identity measures dependency versions, not all native
// library bytes; it is not a hermetic build or a secure-execution attestation.
import { spawn } from 'node:child_process'
import { readFile, realpath } from 'node:fs/promises'
import { isAbsolute, join } from 'node:path'
import { canonicalizeJCS } from '../core/canonicalize.js'
import { hashValue, sha256Hex } from '../core/hashing.js'
import { deepFreeze } from '../core/immutable.js'
import type { SHA256Hex } from '../core/types.js'
import type { AegisQVerifier } from './aegisq-admission.js'

const SOURCE_FILES = ['run_ifg.py', 'aegisq_ifg/__init__.py', 'aegisq_ifg/physics.py', 'aegisq_ifg/cmi.py'] as const
const MAX_INPUT = 8 * 1024 * 1024
const MAX_OUTPUT = 2 * 1024 * 1024
const TIMEOUT_MS = 30_000

export interface PythonVerifierLocation {
  readonly pythonExecutable: string
  readonly packageDirectory: string
}

export interface PinnedPythonVerifierOptions extends PythonVerifierLocation {
  readonly expectedIdentityDigest: SHA256Hex
  readonly expectedIdentity: PythonVerifierIdentity
}

export interface PythonVerifierIdentity {
  readonly schema_version: 'AEGISQ_PYTHON_VERIFIER_IDENTITY_V1'
  readonly sources_sha256: Readonly<Record<string, SHA256Hex>>
  readonly runtime: Readonly<{ python_version: string; numpy_version: string; scipy_version: string }>
  readonly dependency_scope: 'VERSIONS_ONLY_NATIVE_DEPENDENCY_BYTES_NOT_ATTESTED'
}

function runPython(location: PythonVerifierLocation, args: readonly string[], input: Uint8Array): Promise<unknown> {
  if (input.byteLength > MAX_INPUT) return Promise.reject(new Error('IFG_INPUT_TOO_LARGE'))
  return new Promise((resolve, reject) => {
    const child = spawn(location.pythonExecutable, ['-I', join(location.packageDirectory, 'run_ifg.py'), ...args], {
      cwd: location.packageDirectory,
      shell: false,
      stdio: ['pipe', 'pipe', 'pipe'],
    })
    const chunks: Buffer[] = []
    let outputBytes = 0
    let settled = false
    const finish = (error: Error | null, result?: unknown): void => {
      if (settled) return
      settled = true
      clearTimeout(timer)
      if (error !== null) reject(error)
      else resolve(result)
    }
    const timer = setTimeout(() => {
      child.kill('SIGKILL')
      finish(new Error('IFG_TOOLCHAIN_TIMEOUT'))
    }, TIMEOUT_MS)
    child.on('error', () => finish(new Error('IFG_TOOLCHAIN_UNAVAILABLE')))
    child.stdin.on('error', () => finish(new Error('IFG_STDIN_FAILURE')))
    child.stdout.on('data', (chunk: Buffer) => {
      outputBytes += chunk.byteLength
      if (outputBytes > MAX_OUTPUT) {
        child.kill('SIGKILL')
        finish(new Error('IFG_OUTPUT_TOO_LARGE'))
      } else chunks.push(chunk)
    })
    // Do not echo arbitrary child stderr or inherited environment into receipts.
    child.stderr.resume()
    child.on('close', (code, signal) => {
      if (signal !== null || code !== 0) {
        finish(new Error('IFG_TOOLCHAIN_EXECUTION_FAILED'))
        return
      }
      try {
        finish(null, JSON.parse(Buffer.concat(chunks).toString('utf8')) as unknown)
      } catch {
        finish(new Error('IFG_TOOLCHAIN_MALFORMED_OUTPUT'))
      }
    })
    child.stdin.end(input)
  })
}

async function resolveLocation(location: PythonVerifierLocation): Promise<PythonVerifierLocation> {
  if (!isAbsolute(location.pythonExecutable) || !isAbsolute(location.packageDirectory)) {
    throw new Error('IFG_ABSOLUTE_TOOLCHAIN_PATHS_REQUIRED')
  }
  return Object.freeze({
    pythonExecutable: await realpath(location.pythonExecutable),
    packageDirectory: await realpath(location.packageDirectory),
  })
}

async function sourceIdentity(location: PythonVerifierLocation): Promise<Readonly<Record<string, SHA256Hex>>> {
  const values: Record<string, SHA256Hex> = Object.create(null) as Record<string, SHA256Hex>
  for (const file of SOURCE_FILES) values[file] = await sha256Hex(await readFile(join(location.packageDirectory, file)))
  values['python_executable'] = await sha256Hex(await readFile(location.pythonExecutable))
  return deepFreeze(values)
}

/** Measure a candidate identity for review; measuring alone does not authorize it. */
export async function inspectPythonVerifier(locationInput: PythonVerifierLocation): Promise<Readonly<{
  identity: PythonVerifierIdentity
  digest: SHA256Hex
}>> {
  const location = await resolveLocation(locationInput)
  const before = await sourceIdentity(location)
  const runtime = await runPython(location, ['--identity'], new Uint8Array())
  if (runtime === null || typeof runtime !== 'object' || Array.isArray(runtime)) throw new Error('IFG_IDENTITY_INVALID')
  const r = runtime as Record<string, unknown>
  if (Object.keys(r).sort().join('|') !== 'numpy_version|python_version|scipy_version'
      || !Object.values(r).every(v => typeof v === 'string' && /^[0-9A-Za-z.+_-]+$/.test(v))) {
    throw new Error('IFG_IDENTITY_INVALID')
  }
  if (await hashValue(before) !== await hashValue(await sourceIdentity(location))) throw new Error('IFG_SOURCE_CHANGED')
  const identity = deepFreeze({
    schema_version: 'AEGISQ_PYTHON_VERIFIER_IDENTITY_V1' as const,
    sources_sha256: before,
    runtime: runtime as PythonVerifierIdentity['runtime'],
    dependency_scope: 'VERSIONS_ONLY_NATIVE_DEPENDENCY_BYTES_NOT_ATTESTED' as const,
  })
  return deepFreeze({ identity, digest: await hashValue(identity) })
}

/** Bind a fixed trusted installation, and re-check its identity around each run. */
export async function createPinnedPythonVerifier(options: PinnedPythonVerifierOptions): Promise<AegisQVerifier> {
  // Preserve operator configuration before the first asynchronous operation.
  const locationInput = Object.freeze({ pythonExecutable: options.pythonExecutable, packageDirectory: options.packageDirectory })
  const expected = options.expectedIdentityDigest
  const approved = deepFreeze({
    ...options.expectedIdentity,
    sources_sha256: { ...options.expectedIdentity.sources_sha256 },
    runtime: { ...options.expectedIdentity.runtime },
  })
  if (!/^[0-9a-f]{64}$/.test(expected)) throw new Error('IFG_IDENTITY_PIN_INVALID')
  if (approved.schema_version !== 'AEGISQ_PYTHON_VERIFIER_IDENTITY_V1'
      || approved.dependency_scope !== 'VERSIONS_ONLY_NATIVE_DEPENDENCY_BYTES_NOT_ATTESTED'
      || Object.keys(approved.sources_sha256).sort().join('|') !== [...SOURCE_FILES, 'python_executable'].sort().join('|')
      || !Object.values(approved.sources_sha256).every(value => /^[0-9a-f]{64}$/.test(value))
      || await hashValue(approved) !== expected) throw new Error('IFG_IDENTITY_PIN_MISMATCH')
  const location = await resolveLocation(locationInput)
  const approvedSourceDigest = await hashValue(approved.sources_sha256)
  const check = async (): Promise<void> => {
    // Do not execute a changed interpreter or runner even to ask for its version.
    if (await hashValue(await sourceIdentity(location)) !== approvedSourceDigest) throw new Error('IFG_IDENTITY_PIN_MISMATCH')
    if ((await inspectPythonVerifier(location)).digest !== expected) throw new Error('IFG_IDENTITY_PIN_MISMATCH')
  }
  await check()
  return Object.freeze({
    digest: expected,
    async verify(raw: unknown, model: unknown, policy: unknown): Promise<unknown> {
      // Capture exact transport bytes synchronously, before the asynchronous pin check.
      const input = canonicalizeJCS({ raw, model, policy })
      await check()
      const result = await runPython(location, [], input)
      await check()
      return result
    },
  })
}
