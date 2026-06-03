// Shared bus for GPU → CPU field values.
// WebGPUBackground writes here; any component can poll.
export interface GPUFieldSnapshot {
  sigma: number
  rho: number
  lambda: number
  frame: number
}

export const gpuBus = {
  snapshot: { sigma: 0, rho: 0, lambda: 0, frame: 0 } as GPUFieldSnapshot,
}
