// ============================================================
// SOVEREIGN OMEGA — Immutability Infrastructure
// EPISTEMIC TIER: T0 (mechanically enforced)
// BUILD GATE 3: Zero reference leakage under stress
// ============================================================
// All state objects must be deeply frozen after construction.
// Reducers receive frozen state and return new frozen state.
// The withImmutableBoundary wrapper enforces this contract.
// ============================================================

/**
 * Deeply freeze an object and all its reachable properties.
 * Returns the input typed as deeply frozen for compile-time safety.
 */
export function deepFreeze<T>(obj: T): Readonly<T> {
  if (obj === null || typeof obj !== 'object') return obj

  // Freeze all nested objects before freezing the parent
  for (const key of Object.getOwnPropertyNames(obj)) {
    const value = (obj as Record<string, unknown>)[key]
    if (value !== null && typeof value === 'object' && !Object.isFrozen(value)) {
      deepFreeze(value)
    }
  }

  Object.freeze(obj)
  return obj as Readonly<T>
}

/**
 * Assert that a state object is frozen (used in tests and assertions).
 */
export function assertFrozen(obj: unknown, path = 'root'): void {
  if (obj === null || typeof obj !== 'object') return
  if (!Object.isFrozen(obj)) {
    throw new ImmutabilityViolationError(`Object at '${path}' is not frozen`)
  }
  for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
    assertFrozen(value, `${path}.${key}`)
  }
}

/**
 * Assert that two objects do not share any mutable references.
 * Critical invariant: reducers must never share references between
 * the input state and the output state.
 */
export function assertNoSharedReferences<T extends object>(orig: T, clone: T): void {
  if (orig === clone) {
    throw new ImmutabilityViolationError('Reducer violated immutable boundary: identity reference leakage')
  }
  // Deep check: walk the structure and verify no nested object is shared
  checkNoSharedRefs(orig, clone, new WeakSet(), 'root')
}

function checkNoSharedRefs(
  orig: unknown,
  clone: unknown,
  visited: WeakSet<object>,
  path: string
): void {
  /* c8 ignore next -- recursive calls are guarded at L79 to only recurse on object values */
  if (orig === null || typeof orig !== 'object') return
  /* c8 ignore next -- same as above; clone mirrors orig structure */
  if (clone === null || typeof clone !== 'object') return

  // If they're the same object reference (and it's an object), that's a leak
  if (orig === clone) {
    throw new ImmutabilityViolationError(`Shared reference at '${path}'`)
  }

  if (visited.has(orig as object)) return
  visited.add(orig as object)

  const origObj = orig as Record<string, unknown>
  const cloneObj = clone as Record<string, unknown>

  for (const key of Object.keys(origObj)) {
    const origVal = origObj[key]
    const cloneVal = cloneObj[key]
    if (origVal !== null && typeof origVal === 'object') {
      checkNoSharedRefs(origVal, cloneVal, visited, `${path}.${key}`)
    }
  }
}

/**
 * Wrap a reducer function to enforce immutability boundaries:
 * 1. Input state must be frozen before reducer is called.
 * 2. Output state is deeply frozen before being returned.
 * 3. No shared references between input and output.
 */
export function withImmutableBoundary<TState, TEvent>(
  reducer: (state: Readonly<TState>, event: TEvent) => TState
): (state: Readonly<TState>, event: TEvent) => Readonly<TState> {
  return (state: Readonly<TState>, event: TEvent): Readonly<TState> => {
    if (typeof state === 'object' && state !== null && !Object.isFrozen(state)) {
      throw new ImmutabilityViolationError('Reducer received unfrozen state')
    }

    const nextState = reducer(state, event)

    if (nextState === (state as unknown)) {
      // Reducer returned same reference — only acceptable if state is truly immutable
      // and no mutation occurred. We allow this for no-op reducers.
      return nextState as Readonly<TState>
    }

    // Freeze the output and verify no shared references
    const frozen = deepFreeze(nextState)

    if (typeof state === 'object' && state !== null &&
        typeof frozen === 'object' && frozen !== null) {
      assertNoSharedReferences(state as object, frozen as object)
    }

    return frozen
  }
}

/**
 * Create an immutable initial state.
 * All initial states must be constructed through this function.
 */
export function createInitialState<T>(state: T): Readonly<T> {
  return deepFreeze(structuredClone(state) as T)
}

// ─── Error Types ───────────────────────────────────────────

export class ImmutabilityViolationError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'ImmutabilityViolationError'
  }
}
