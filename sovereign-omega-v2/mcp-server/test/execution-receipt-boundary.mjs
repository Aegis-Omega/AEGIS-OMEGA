import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { dirname, join } from 'node:path'
import { fileURLToPath } from 'node:url'

const here = dirname(fileURLToPath(import.meta.url))
const source = readFileSync(join(here, '..', 'src', 'index.ts'), 'utf8')

function before(haystack, left, right) {
  const a = haystack.indexOf(left)
  const b = haystack.indexOf(right)
  return a >= 0 && b > a
}

assert.equal(source.includes("mutation_receipt_root?: string"), false,
  'AuthorityDecision must not advertise a pre-execution mutation receipt')

assert.equal(source.includes("runAutomaton('finalize'"), true,
  'execution finalizer must invoke Automaton-3 finalize')
assert.equal(source.includes('function extractPostStateDigest'), true,
  'MCP boundary must extract an observed post-state root')
assert.equal(source.includes("'audit_chain_hash'"), true)
assert.equal(source.includes("'lineage_terminal_hash'"), true)
assert.equal(source.includes("'kan_terminal_hash'"), true)
assert.equal(source.includes("['chain_hash']"), true)
assert.equal(source.includes('POST_STATE_UNAVAILABLE'), true,
  'missing post-state must fail closed as unattested')
assert.equal(source.includes('ASYNC_EXECUTION_NOT_TERMINAL'), true,
  'async initiation must not be attested as terminal success')

assert.equal(source.includes('function observedExecutionOutcome'), true,
  'MCP boundary must classify an observed invalid chain as failed execution')
assert.equal(source.includes("chain_valid'] === false"), true,
  'chain_valid=false must be an explicit failed-execution signal')
assert.equal(source.includes("observedExecutionOutcome(result)"), true,
  'collaboration finalizer must consume the observed execution outcome')

assert.equal(before(
  source,
  "await bridgePost('/platform/collaborate'",
  "finalizeExecution(authorityInput, result, extractPostStateDigest(result, 'collaboration'), observedExecutionOutcome(result))",
), true, 'collaboration receipt must be finalized only after the side effect returns')

assert.equal(before(
  source,
  "await bridgePost('/claude'",
  "finalizeExecution(authorityInput, result, extractPostStateDigest(result, 'claude'), observedExecutionOutcome(result))",
), true, 'Claude receipt must be finalized only after the side effect returns')

console.log('EXECUTION_RECEIPT_BOUNDARY_PASS admission != execution; terminal receipts are post-result only')
