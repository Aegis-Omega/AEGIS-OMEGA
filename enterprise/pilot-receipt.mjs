import { createHash } from 'node:crypto'
import { readFileSync } from 'node:fs'
import { checkBridge } from './check-bridge.mjs'

const origin = 'https://enterprise.example.test'
const bridgeUrl = 'https://bridge.example.test'
const digest = (value) => createHash('sha256').update(value).digest('hex')

const fixtures = {
  '/node': {
    sequence: 1,
    epoch: 2,
    corruption_count: 0,
    constitutional_hash: digest('seq=1:epoch=2:corruption=0'),
    t0_verdict: true,
  },
  '/network': { peer_count: 0, peers: [] },
  '/resonance': { is_resonant: false },
  '/telemetry': { sequence: 1 },
  '/coherence': { global_section_exists: false },
  '/pipeline': { replay_fingerprint: 'synthetic-pilot' },
  '/drift': { current_drift_class: 'D0' },
}

function syntheticBridge(withholdNode) {
  return async (url, options) => {
    const target = new URL(url)
    if (target.origin !== bridgeUrl || options.headers?.Origin !== origin) {
      throw new Error('Unexpected synthetic request')
    }
    if (withholdNode && target.pathname === '/node') {
      return new Response(null, { status: 401 })
    }
    if (!Object.hasOwn(fixtures, target.pathname)) {
      return new Response(null, { status: 404 })
    }
    return Response.json(fixtures[target.pathname], {
      headers: { 'Access-Control-Allow-Origin': origin },
    })
  }
}

async function makeReceipt(revision) {
  if (!/^[a-f0-9]{40}$/.test(revision ?? '')) {
    throw new Error('Provide a full Git commit SHA')
  }
  const [available, withheld] = await Promise.all([
    checkBridge(bridgeUrl, origin, syntheticBridge(false)),
    checkBridge(bridgeUrl, origin, syntheticBridge(true)),
  ])
  const passed = available.length === Object.keys(fixtures).length
    && available.every(({ error }) => error === null)
    && withheld.length === available.length
    && withheld.some(({ path, error }) => path === '/node' && error === 'HTTP 401')
    && withheld.every(({ path, error }) => path === '/node' || error === null)
  const evidence = {
    schema: 'aegis.enterprise.synthetic-bridge.v1',
    revision,
    source: {
      bridgeCheckSha256: digest(readFileSync(new URL('./check-bridge.mjs', import.meta.url))),
      pilotSha256: digest(readFileSync(new URL(import.meta.url))),
      fixtureSha256: digest(JSON.stringify(fixtures)),
    },
    externalRequests: 0,
    paidActions: 0,
    result: passed ? 'PASS' : 'FAIL',
    cases: { available, withheld },
  }
  return { ...evidence, sha256: digest(JSON.stringify(evidence)) }
}

async function main([command, revision, path, ...extra]) {
  if (extra.length || !((command === 'run' && !path) || (command === 'verify' && path))) {
    throw new Error('Usage: node enterprise/pilot-receipt.mjs run <commit> | verify <commit> <file>')
  }
  const expected = await makeReceipt(revision)
  if (command === 'run') {
    console.log(JSON.stringify(expected, null, 2))
  } else {
    const observed = JSON.parse(readFileSync(path, 'utf8'))
    if (JSON.stringify(observed) !== JSON.stringify(expected)) {
      throw new Error('Receipt does not match the pinned source and replay')
    }
    console.log('Synthetic bridge receipt verified')
  }
  process.exitCode = Number(expected.result !== 'PASS')
}

try {
  await main(process.argv.slice(2))
} catch (error) {
  console.error(error.message)
  process.exitCode = 1
}
