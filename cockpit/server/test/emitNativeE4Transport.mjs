/**
 * CI evidence adapter. Runs the EXISTING bridgeControl.js against an actual
 * RiskBudgetManager decision generated in a separate, SHA-pinned #817 checkout.
 * No network calls, credential access, or production mutation execution.
 */
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { encodeAdmittedGovernanceMutation } from '../dist/bridgeControl.js'

const file = process.argv[2]
if (!file || !process.env.AEGIS_NATIVE_E4_SOURCE_SHA) {
  throw new Error('NEED_PINNED_NATIVE_E4_FIXTURE')
}
const input = JSON.parse(readFileSync(file, 'utf8'))
assert.equal(input.schema, 'AEGIS_E4_NATIVE_PR817_TEST_V1')
assert.equal(input.source, 'RiskBudgetManager.evaluate')
assert.equal(input.fixture_class, 'SYNTHETIC_CI_ONLY_NOT_MUTATION_PROOF')
assert.equal(input.exact_e4_source_sha, process.env.AEGIS_NATIVE_E4_SOURCE_SHA)
assert.equal(input.capability_class, 'SELF_MODIFYING')
assert.equal(input.registered_operator, 'bridge-e4-synthetic-test-v1')
assert.equal(input.decision.component_id, 'bridge-e4-synthetic-mutation')
assert.equal(input.decision.accepted, true)
assert.equal(input.decision.method, 'anytime_valid_bernstein')
assert.equal(input.insufficient.accepted, false)
assert.equal(input.insufficient.rejection_reason, 'E_VALUE_FAIL')
assert.equal(input.insufficient.component_id, input.decision.component_id)
assert.equal(input.insufficient.method, input.decision.method)
assert.ok(input.insufficient.lcb_value > 0)
assert.ok(input.insufficient.e_value > 0)

const transport = encodeAdmittedGovernanceMutation({
  decision: input.decision,
  capabilityClass: input.capability_class,
  operatorId: input.registered_operator,
  sequence: input.sequence,
  payload: Buffer.from(input.payload_hex, 'hex'),
  verifier: Buffer.from(input.verifier_hex, 'hex'),
  context: Buffer.from(input.context_hex, 'hex'),
})
// A real E4-rejected decision must never be transformed into an admission,
// even though its LCB may be positive.
assert.throws(() => encodeAdmittedGovernanceMutation({
  decision: input.insufficient,
  capabilityClass: input.capability_class,
  operatorId: input.registered_operator,
  sequence: input.sequence + 1,
  payload: Buffer.from(input.payload_hex, 'hex'),
  verifier: Buffer.from(input.verifier_hex, 'hex'),
  context: Buffer.from(input.context_hex, 'hex'),
}), /accepted/)

process.stdout.write(JSON.stringify({
  schema: 'AEGIS_NATIVE_E4_BRIDGE_PARITY_V1',
  source: 'native-PR817-RiskBudgetManager-to-PR811-codec',
  fixture_class: 'SYNTHETIC_CI_ONLY_NOT_MUTATION_PROOF',
  e4_sha: input.exact_e4_source_sha,
  native_component: input.decision.component_id,
  registered_operator: input.registered_operator,
  admitted: transport,
  weak_decision: input.insufficient,
}) + '\n')
