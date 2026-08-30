// ============================================================
// SOVEREIGN OMEGA — Deterministic WASM Kernel Interface
// EPISTEMIC TIER: T0
// Ω-5: JS orchestration shell only. All determinism-critical
// computations route through WASM kernels to eliminate JS
// runtime dynamism from forensic reconstruction paths.
// ============================================================

import type { SHA256Hex } from './types.js'

export interface WasmKernelExports {
  readonly memory: WebAssembly.Memory

  /** RFC 8785 canonical serialisation → UTF-8 bytes */
  canonicalize(inputPtr: number, inputLen: number, outPtr: number): number

  /** SHA-256 over raw bytes → 32-byte digest */
  sha256(inputPtr: number, inputLen: number, outPtr: number): void

  /** Apply pure reducer over serialised event → new state hash */
  reduce_state(
    statePtr: number, stateLen: number,
    eventPtr: number, eventLen: number,
    outPtr: number
  ): number

  /** Empirical Bernstein LCB in Q32.32 */
  bernstein_lcb(
    sumQ32: bigint, sumSqQ32: bigint,
    n: number, alphaQ32: bigint
  ): bigint

  /** Merkle root from n 32-byte leaves using byte-concat-arity-2-v1 */
  merkle_root(leavesPtr: number, leafCount: number, outPtr: number): void
}

export type WasmParity = 'PASS' | 'FAIL'

/**
 * Verify that WASM kernel output matches JS fallback output.
 * Called during CI and on first startup if WASM kernel is loaded.
 * Throws DETERMINISM_VIOLATION if any parity check fails.
 */
export function assertWasmParity(
  jsOut: Uint8Array | string,
  wasmOut: Uint8Array | string,
  label: string
): void {
  const jsStr = typeof jsOut === 'string' ? jsOut : Array.from(jsOut).map(b => b.toString(16).padStart(2, '0')).join('')
  const wasmStr = typeof wasmOut === 'string' ? wasmOut : Array.from(wasmOut).map(b => b.toString(16).padStart(2, '0')).join('')
  if (jsStr !== wasmStr) {
    throw new Error(`DETERMINISM_VIOLATION: WASM parity failure in ${label}. JS=${jsStr.slice(0, 16)}, WASM=${wasmStr.slice(0, 16)}`)
  }
}

export interface WasmKernel {
  readonly loaded: boolean
  readonly hash: SHA256Hex | null
  readonly exports: WasmKernelExports | null
}

let _kernel: WasmKernel = { loaded: false, hash: null, exports: null }

export function getWasmKernel(): WasmKernel { return _kernel }

export async function loadWasmKernel(wasmPath: string): Promise<WasmKernel> {
  try {
    const { instance } = await WebAssembly.instantiateStreaming(fetch(wasmPath))
    _kernel = {
      loaded: true,
      hash: null, // set at build time from manifest
      exports: instance.exports as unknown as WasmKernelExports,
    }
  } catch {
    // WASM unavailable — JS fallbacks remain active, parity checks skipped
    _kernel = { loaded: false, hash: null, exports: null }
  }
  return _kernel
}
