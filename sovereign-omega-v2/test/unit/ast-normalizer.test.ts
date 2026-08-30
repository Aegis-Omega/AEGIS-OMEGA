import { describe, it, expect } from 'vitest'
import {
  stripComments,
  hasEarlyReturn,
  hasLoop,
  hasDestructuring,
  semanticFunctionCount,
  normalizedExportCount,
  normalizedInterfaceCount,
  AST_NORMALIZER_VERSION,
} from '../../src/consensus/ast-normalizer.js'

describe('AST Normalizer — constants', () => {
  it('AST_NORMALIZER_VERSION is 1.0.0', () => {
    expect(AST_NORMALIZER_VERSION).toBe('1.0.0')
  })
})

describe('AST Normalizer — stripComments', () => {
  it('removes single-line comments', () => {
    const code = `const x = 1 // this is a comment\nconst y = 2`
    expect(stripComments(code)).not.toContain('//')
    expect(stripComments(code)).toContain('const x = 1')
    expect(stripComments(code)).toContain('const y = 2')
  })

  it('removes block comments', () => {
    const code = `/* header comment */\nconst x = 1`
    expect(stripComments(code)).not.toContain('/*')
    expect(stripComments(code)).toContain('const x = 1')
  })

  it('prevents false error_handling match from comment', () => {
    const code = `// throw new Error was removed\nconst x = 1`
    const normalized = stripComments(code)
    expect(normalized).not.toMatch(/throw/)
  })

  it('prevents false export match from comment', () => {
    const code = `// export function foo() {}\nconst x = 1`
    expect(normalizedExportCount(code)).toBe(0)
  })

  it('collapses whitespace', () => {
    const code = `const   x   =   1`
    expect(stripComments(code)).toBe('const x = 1')
  })
})

describe('AST Normalizer — hasEarlyReturn', () => {
  it('detects guard clause: if (!x) throw', () => {
    expect(hasEarlyReturn(`if (!input.length) throw new Error('empty')`)).toBe(true)
  })

  it('detects guard clause: if (!x) return', () => {
    expect(hasEarlyReturn(`if (!x) return null`)).toBe(true)
  })

  it('detects nested conditional with else-throw', () => {
    expect(hasEarlyReturn(`if (x > 0) { return x } else { throw new Error('negative') }`)).toBe(true)
  })

  it('detects ternary guard pattern: null in then-branch signals early exit', () => {
    // `!x ? null : doWork(x)` — null immediately after `?` = early-exit pattern
    expect(hasEarlyReturn(`const r = !x ? null : doWork(x)`)).toBe(true)
  })

  it('guard clause ≡ nested conditional → both true (the key false-deadlock fix)', () => {
    const guardClause = `if (!input.length) throw new Error('empty')\nreturn await process(input)`
    const nested = `if (input.length > 0) {\n  return await process(input)\n} else {\n  throw new Error('empty')\n}`
    expect(hasEarlyReturn(guardClause)).toBe(true)
    expect(hasEarlyReturn(nested)).toBe(true)
  })

  it('returns false for code with no early exit', () => {
    expect(hasEarlyReturn(`const x = doWork()\nreturn x`)).toBe(false)
  })

  it('comment throw does not trigger', () => {
    expect(hasEarlyReturn(`// if (!x) throw new Error('empty')\nconst y = 1`)).toBe(false)
  })
})

describe('AST Normalizer — hasLoop', () => {
  it('detects for loop', () => {
    expect(hasLoop(`for (const x of items) { process(x) }`)).toBe(true)
  })

  it('detects while loop', () => {
    expect(hasLoop(`while (queue.length > 0) { process(queue.shift()) }`)).toBe(true)
  })

  it('detects .map(', () => {
    expect(hasLoop(`const results = items.map(x => x * 2)`)).toBe(true)
  })

  it('detects .filter(', () => {
    expect(hasLoop(`const valid = items.filter(x => x > 0)`)).toBe(true)
  })

  it('detects .reduce(', () => {
    expect(hasLoop(`const sum = items.reduce((a, b) => a + b, 0)`)).toBe(true)
  })

  it('detects .forEach(', () => {
    expect(hasLoop(`items.forEach(x => process(x))`)).toBe(true)
  })

  it('returns false for non-iterative code', () => {
    expect(hasLoop(`const x = await hashValue({ input })\nreturn x`)).toBe(false)
  })
})

describe('AST Normalizer — hasDestructuring', () => {
  it('detects object destructuring', () => {
    expect(hasDestructuring(`const { a, b } = obj`)).toBe(true)
  })

  it('detects array destructuring', () => {
    expect(hasDestructuring(`const [first, second] = arr`)).toBe(true)
  })

  it('detects destructured parameter', () => {
    expect(hasDestructuring(`function f({ name, value }: Input) { return name }`)).toBe(true)
  })

  it('returns false for non-destructuring code', () => {
    expect(hasDestructuring(`const x = obj.value\nconst y = arr[0]`)).toBe(false)
  })
})

describe('AST Normalizer — semanticFunctionCount', () => {
  it('counts named function declaration', () => {
    expect(semanticFunctionCount(`function solve(x: string): string { return x }`)).toBe(1)
  })

  it('counts async function declaration', () => {
    expect(semanticFunctionCount(`async function solve(x: string): Promise<string> { return x }`)).toBe(1)
  })

  it('counts named arrow function assignment', () => {
    expect(semanticFunctionCount(`const solve = async (x: string) => x`)).toBe(1)
  })

  it('does NOT count inline callback lambda', () => {
    // arr.map(x => x) — inline lambda, not a named function
    const code = `const results = items.map(x => x * 2)`
    expect(semanticFunctionCount(code)).toBe(0)
  })

  it('counts multiple named functions', () => {
    const code = `function alpha() {}\nfunction beta() {}\nasync function gamma() {}`
    expect(semanticFunctionCount(code)).toBe(3)
  })

  it('guard clause vs nested conditional → same count', () => {
    const guard = `async function solve(input: readonly string[]): Promise<string> {
  if (!input.length) throw new Error('empty')
  return await hashValue({ input })
}`
    const nested = `async function solve(input: readonly string[]): Promise<string> {
  if (input.length) {
    return await hashValue({ input })
  } else {
    throw new Error('empty')
  }
}`
    expect(semanticFunctionCount(guard)).toBe(semanticFunctionCount(nested))
  })
})

describe('AST Normalizer — normalizedExportCount', () => {
  it('counts exports in real code', () => {
    expect(normalizedExportCount(`export const A = 1\nexport function B() {}`)).toBe(2)
  })

  it('does not count commented-out export', () => {
    expect(normalizedExportCount(`// export const A = 1\nexport function B() {}`)).toBe(1)
  })

  it('returns 0 for no exports', () => {
    expect(normalizedExportCount(`const x = 1`)).toBe(0)
  })
})

describe('AST Normalizer — normalizedInterfaceCount', () => {
  it('counts interface declarations', () => {
    expect(normalizedInterfaceCount(`interface Foo { x: string }\ninterface Bar { y: number }`)).toBe(2)
  })

  it('counts type aliases', () => {
    expect(normalizedInterfaceCount(`type Foo = { x: string }\ntype Bar = string`)).toBe(2)
  })

  it('does not count commented interfaces', () => {
    expect(normalizedInterfaceCount(`// interface Foo {}\ninterface Bar { y: number }`)).toBe(1)
  })
})
