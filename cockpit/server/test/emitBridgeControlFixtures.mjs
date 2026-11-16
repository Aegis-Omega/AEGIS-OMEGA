/** Deterministic Node output consumed independently by Python CI. */
import { encodeAdmittedGovernanceMutation } from '../dist/bridgeControl.js'

const cases = [
  {
    name: 'ascii-and-binary',
    decision: { proposal_id: 'E4:test:0001', accepted: true, lcb_value: 0.125,
      e_value: 32, risk_spent: 0.05, sample_size: 20, method: 'anytime_valid_bernstein' },
    sequence: 17,
    payload: Buffer.from('hello', 'utf8'),
    verifier: Uint8Array.of(0x00),
    context: Uint8Array.of(0x00, 0x7f, 0xff),
  },
  {
    name: 'bosnian-and-holon',
    decision: { proposal_id: 'E4:holon:42', accepted: true, lcb_value: 0.375,
      e_value: 32, risk_spent: 0.05, sample_size: 20, method: 'anytime_valid_bernstein' },
    sequence: 123456,
    payload: Buffer.from('AEGIS Ω | holon: značenje', 'utf8'),
    verifier: Uint8Array.of(0x00, 0xff),
    context: Uint8Array.of(0x00, 0x01, 0xfe, 0xff),
  },
  {
    name: 'empty-payload-and-context',
    decision: { proposal_id: 'E4:empty:1', accepted: true, lcb_value: 0.03125,
      e_value: 32, risk_spent: 0.05, sample_size: 20, method: 'anytime_valid_bernstein' },
    sequence: 123457,
    payload: new Uint8Array(),
    verifier: Uint8Array.of(0x00),
    context: new Uint8Array(),
  },
]

const vectors = cases.map(({ name, ...input }) => ({
  name,
  ...encodeAdmittedGovernanceMutation(input),
}))

process.stdout.write(JSON.stringify({
  schema: 'AEGIS_BRIDGE_MUTATION_TRANSPORT_V1',
  source: 'native-node-bridge-control',
  vectors,
}) + '\n')
