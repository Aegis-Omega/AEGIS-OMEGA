// ============================================================
// AST Normalizer — Semantic preprocessing for structural fingerprinting
// EPISTEMIC TIER: T2 (engineering hypothesis)
// Constitutional root: AdaptivePower(T) ≤ ReplayVerifiability(T)
//
// Prevents false DEADLOCKs in the BFT Synthesis Swarm by normalizing
// code before fingerprinting. Key invariant:
//   semantically equivalent code → identical semantic features
//
// Example invariance:
//   if (!x) throw new Error('empty')       ← guard clause
//   if (x) { doWork() } else { throw ... } ← nested conditional
// Both map to { has_error_handling: true, has_early_return: true }
// ============================================================

export const AST_NORMALIZER_VERSION = '1.0.0' as const

// Strip comments and collapse whitespace.
// Run before ALL pattern detection to prevent false regex matches on comments.
export function stripComments(code: string): string {
  return code
    .replace(/\/\/[^\n]*/g, '')        // single-line comments
    .replace(/\/\*[\s\S]*?\*\//g, '')  // block comments
    .replace(/\s+/g, ' ')             // collapse whitespace
    .trim()
}

// Detect guard clause / early exit — normalizes over syntactic form.
// Guard clause:        if (!x) throw new Error(...)
// Nested conditional:  if (x) { ... } else { throw ... }
// Nullish guard:       x ?? (() => { throw ... })()
// All three → has_early_return = true
export function hasEarlyReturn(code: string): boolean {
  const n = stripComments(code)
  return (
    /if\s*\([^)]{0,120}\)\s*(throw|return)\b/.test(n) ||   // guard clause
    /\belse\s*\{[^}]{0,200}(throw|return)\b/.test(n) ||    // else-throw
    /\?\s*(?:throw|null|undefined)\b/.test(n)              // ternary guard
  )
}

// Detect iterative computation — semantically equivalent patterns:
//   for (...)  while (...)  .forEach(  .map(  .filter(  .reduce(
export function hasLoop(code: string): boolean {
  const n = stripComments(code)
  return /\bfor\s*\(|\bwhile\s*\(|\.forEach\s*\(|\.map\s*\(|\.filter\s*\(|\.reduce\s*\(/.test(n)
}

// Detect destructuring patterns in any position.
//   const { a, b } = ...   const [x, y] = ...   function f({ a }) ...
export function hasDestructuring(code: string): boolean {
  const n = stripComments(code)
  return (
    /(?:const|let|var)\s*\{/.test(n) ||   // object destructuring
    /(?:const|let|var)\s*\[/.test(n) ||   // array destructuring
    /\(\s*\{[^}]{1,120}\}/.test(n)        // destructured parameter
  )
}

// Semantic function count — counts named function definitions only.
// Key invariant: guard clause vs nested conditional → same count.
//
// Atomic match `(?:async\s+)?function` prevents double-counting:
//   `async function solve()` matches once as a unit, not twice
//   as separate `async` and `function` sweeps.
//
// Named arrow: `const foo = async (...) =>` detected separately.
// Inline lambdas/callbacks excluded (no leading const/let/var).
export function semanticFunctionCount(code: string): number {
  const n = stripComments(code)
  // Atomic: matches both `function foo(` and `async function foo(` as one unit
  const funcDecls = (n.match(/\b(?:async\s+)?function\s+\w+\s*\(/g) ?? []).length
  // Named arrow assignments: `const foo = (...) =>` or `const foo = async (...) =>`
  // Requires `=>` to be present — prevents false matches on `const x = (expr + 1)`
  const namedArrow = (n.match(/(?:const|let|var)\s+\w+\s*=\s*(?:async\s*)?\([^)]*\)\s*=>/g) ?? []).length
  return funcDecls + namedArrow
}

// Count exports from normalized code (stripping comments first eliminates
// false matches on commented-out exports).
export function normalizedExportCount(code: string): number {
  return (stripComments(code).match(/\bexport\b/g) ?? []).length
}

// Count interface/type definitions from normalized code.
export function normalizedInterfaceCount(code: string): number {
  return (stripComments(code).match(/\binterface\b|\btype\b\s+\w+\s*=/g) ?? []).length
}
