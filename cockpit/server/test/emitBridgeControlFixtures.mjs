/** Deterministic Node output consumed independently by Python CI. */
import { encodeAdmittedGovernanceMutation } from '../dist/bridgeControl.js'

const cases = [
  {
    name: 'ascii-and-binary',
    proposalId: 'E4:test:0001',
    sequence: 17,
    lcb: 0.125,
    payload: Buffer.from('hello', 'utf8'),
    verifier: Uint8Array.of(0x00),
    context: Uint8Array.of(0x00, 0x7f, 0xff),
  },
  {
    name: 'bosnian-and-holon',
    proposalId: 'E4:holon:42',
    sequence: 123456,
    lcb: 0.375,
    payload: Buffer.from('AEGIS Ω | holon: značenje', 'utf8'),
    verifier: Uint8Array.of(0x00, 0xff),
    context: Uint8Array.of(0x00, 0x01, 0xfe, 0xff),
  },
  {
    name: 'empty-payload-and-context',
    proposalId: 'E4:empty:1',
    sequence: 123457,
    lcb: 0.03125,
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
