export class SensoriumModelError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'SensoriumModelError'
  }
}

function assertBps(name: string, value: number): void {
  if (!Number.isSafeInteger(value) || value < 0 || value > 10_000) {
    throw new SensoriumModelError(`${name} must be an integer in [0,10000]`)
  }
}

function assertCapacity(current: bigint, capacity: bigint): void {
  if (capacity <= 0n) throw new SensoriumModelError('carrying capacity must be positive')
  if (current < 0n || current > capacity) {
    throw new SensoriumModelError('active load must be within carrying capacity')
  }
}

export function nextLogisticLoad(current: bigint, capacity: bigint, growthRateBps: number): bigint {
  assertCapacity(current, capacity)
  assertBps('growthRateBps', growthRateBps)
  const delta = BigInt(growthRateBps) * current * (capacity - current) / (10_000n * capacity)
  const next = current + delta
  if (next < 0n) return 0n
  if (next > capacity) return capacity
  return next
}

export function capacityPressureBps(active: bigint, capacity: bigint): number {
  if (capacity <= 0n) throw new SensoriumModelError('carrying capacity must be positive')
  if (active < 0n) throw new SensoriumModelError('active load must be non-negative')
  const pressure = active * 10_000n / capacity
  const bounded = pressure > 10_000n ? 10_000n : pressure
  return Number(bounded)
}

export function nextRetentionBps(current: number, decayBps: number, reinforcementBps: number): number {
  assertBps('retentionBps', current)
  assertBps('decayBps', decayBps)
  assertBps('reinforcementBps', reinforcementBps)
  const retained = Math.floor(current * (10_000 - decayBps) / 10_000)
  return Math.min(10_000, Math.max(0, retained + reinforcementBps))
}
