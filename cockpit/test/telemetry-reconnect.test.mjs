/**
 * Executes the committed Cockpit TypeScript module after TypeScript transpilation.
 * The Vite-only import.meta.env value is replaced with a fixed test URL.
 * All EventSource, clock and interval behavior is deterministic and stubbed.
 *
 * This is a native Node test of the real telemetry state machine, not a
 * browser/network/prod integration or proof of runtime availability.
 */
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { test } from 'node:test'
import ts from 'typescript'

const source = await readFile(new URL('../src/lib/telemetry.ts', import.meta.url), 'utf8')
assert.equal(source.split('import.meta.env.VITE_BRIDGE_URL').length, 2)

let counter = 0
async function fixture(fn) {
  const saved = {
    EventSource: globalThis.EventSource,
    setInterval: globalThis.setInterval,
    clearInterval: globalThis.clearInterval,
    now: Date.now,
  }
  let now = 1000
  const instances = []
  const intervals = new Map()
  let nextInterval = 1

  class FakeEventSource {
    constructor(url) {
      this.url = url
      this.closed = false
      this.onmessage = null
      this.onerror = null
      instances.push(this)
    }
    close() { this.closed = true }
    frame(value) { this.onmessage?.({ data: JSON.stringify(value) }) }
    invalidFrame() { this.onmessage?.({ data: '{invalid-json' }) }
    disconnected() { this.onerror?.({ type: 'error' }) }
  }

  globalThis.EventSource = FakeEventSource
  globalThis.setInterval = (fn, ms) => {
    assert.equal(ms, 5000)
    const id = nextInterval++
    intervals.set(id, fn)
    return id
  }
  globalThis.clearInterval = id => intervals.delete(id)
  Date.now = () => now

  const transformed = source.replace(
    'import.meta.env.VITE_BRIDGE_URL', '"http://test.invalid:7890"'
  )
  const js = ts.transpileModule(transformed, {
    compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext },
    reportDiagnostics: true,
  })
  assert.equal(js.diagnostics?.length ?? 0, 0)
  const url = 'data:text/javascript;charset=utf-8,' +
    encodeURIComponent(js.outputText) + '#telemetry-test-' + (++counter)

  try {
    const client = await import(url)
    await fn({
      client, instances, intervals,
      setNow: value => { now = value },
      tick: () => { for (const cb of [...intervals.values()]) cb() },
    })
  } finally {
    Date.now = saved.now
    if (saved.EventSource === undefined) delete globalThis.EventSource
    else globalThis.EventSource = saved.EventSource
    globalThis.setInterval = saved.setInterval
    globalThis.clearInterval = saved.clearInterval
  }
}

test('normal one-frame SSE disconnect keeps native reconnect active', async () => {
  await fixture(({ client, instances, intervals, setNow, tick }) => {
    const observed = []
    const stop = client.subscribeTelemetry(state => observed.push(state))
    assert.equal(instances.length, 1)
    assert.equal(intervals.size, 1)
    const es = instances[0]
    assert.match(es.url, /\/telemetry\/stream$/)
    assert.equal(client.getCurrentTelemetry().status, 'offline')

    es.frame({ sequence: 12, epoch: 3 })
    assert.equal(client.getCurrentTelemetry().status, 'online')
    assert.equal(client.getCurrentTelemetry().streaming, true)
    assert.equal(client.getCurrentTelemetry().data.sequence, 12)

    setNow(6000)
    es.disconnected() // Server intentionally closes after 1 frame.
    assert.equal(es.closed, false, 'do not cancel EventSource native retry')
    assert.equal(client.getCurrentTelemetry().status, 'online')
    tick()
    assert.equal(client.getCurrentTelemetry().status, 'online')

    setNow(11000)
    es.frame({ sequence: 13, epoch: 4 }) // Automatic native reconnection.
    assert.equal(client.getCurrentTelemetry().data.epoch, 4)
    setNow(26000)
    tick()
    assert.equal(client.getCurrentTelemetry().status, 'online')
    setNow(32001)
    tick()
    assert.equal(client.getCurrentTelemetry().status, 'offline')
    assert.equal(es.closed, false, 'offline does not disable future reconnects')

    es.frame({ sequence: 14, epoch: 5 })
    assert.equal(client.getCurrentTelemetry().status, 'online')
    const calls = observed.length
    stop()
    assert.equal(es.closed, true)
    assert.equal(intervals.size, 0)
    es.frame({ sequence: 15, epoch: 6 })
    assert.equal(observed.length, calls, 'aborted observer receives no frames')
  })
})

test('malformed SSE data does not refresh liveness and multiple listeners share one connection', async () => {
  await fixture(({ client, instances, intervals, setNow, tick }) => {
    const a = [], b = []
    const stopA = client.subscribeTelemetry(s => a.push(s))
    const stopB = client.subscribeTelemetry(s => b.push(s))
    assert.equal(instances.length, 1)
    assert.equal(intervals.size, 1)
    const es = instances[0]
    es.frame({ sequence: 1, epoch: 1 })
    es.invalidFrame()
    setNow(22000)
    tick()
    assert.equal(client.getCurrentTelemetry().status, 'offline')
    stopA()
    assert.equal(es.closed, false, 'one active listener keeps SSE alive')
    es.frame({ sequence: 2, epoch: 2 })
    assert.equal(client.getCurrentTelemetry().status, 'online')
    assert.equal(b.at(-1).data.sequence, 2)
    stopB()
    assert.equal(es.closed, true)
    assert.equal(intervals.size, 0)
  })
})
