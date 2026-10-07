/** Reproducible exact-head evidence collector. Failed or skipped stages never produce PASS. */
import assert from 'node:assert/strict'
import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { mkdirSync, readFileSync, writeFileSync, readdirSync, rmSync, existsSync } from 'node:fs'
import { resolve, join, relative } from 'node:path'
import { validateDemoTrace } from '../web/client.mjs'

const sha = bytes => createHash('sha256').update(bytes).digest('hex')
const git = (...args) => {
  const run = spawnSync('git', args, { encoding: 'utf8' })
  if (run.status !== 0) throw new Error(`Git evidence unavailable: ${args[0]}`)
  return run.stdout.trim()
}
const root = git('rev-parse', '--show-toplevel')
const sourceCommit = git('rev-parse', 'HEAD')
const sourcePrefix = 'sovereign-omega-v2/mcp-server/'
const initialStatus = git('status', '--porcelain', '--untracked-files=no')
const sourcePaths = ['package.json', 'package-lock.json', 'tsconfig.json', ...['src', 'web', 'test', 'docs'].flatMap(dir =>
  readdirSync(dir, { recursive: true, withFileTypes: true }).filter(item => item.isFile()).map(item =>
    relative(process.cwd(), join(item.parentPath, item.name))))]
sourcePaths.push(relative(process.cwd(), join(root, 'harness/policies/consequence-policy.v1.json')),
  relative(process.cwd(), join(root, 'scripts/automaton3-authority.py')),
  relative(process.cwd(), join(root, 'harness/sdk/sovereign_execution.py')),
  relative(process.cwd(), join(root, '.github/workflows/alexa-mcp-lane.yml')))
const sourceManifest = [...new Set(sourcePaths)].sort().map(path => {
  const bytes = readFileSync(path)
  return { path: relative(root, resolve(path)), bytes: bytes.length, sha256: sha(bytes),
    git_blob_sha1: createHash('sha1').update(Buffer.concat([Buffer.from(`blob ${bytes.length}\0`), bytes])).digest('hex') }
})
rmSync('evidence', { recursive: true, force: true }); mkdirSync('evidence')
const stages = [
  ['build', 'npm', ['run', 'build']],
  ['browser-client', process.execPath, ['--test', 'test/browser-client.mjs']],
  ['streamable-http', process.execPath, ['--test', 'test/streamable-http.mjs']],
  ['legacy-resources', process.execPath, ['test/resources.mjs']],
  ['legacy-automaton3', process.execPath, ['test/automaton3-authority.mjs']],
  ['browser-e2e', process.execPath, ['test/browser-e2e.mjs']],
]
const results = []
for (const [name, command, args] of stages) {
  const start = performance.now()
  const run = spawnSync(command, args, { encoding: 'utf8', timeout: 180000, maxBuffer: 8 * 1024 * 1024,
    env: { ...process.env, AEGIS_EXECUTION_IDENTITY_JSON: '', AEGIS_APPROVAL_GRANT_JSON: '', AEGIS_API_KEY: '' } })
  const output = (run.stdout ?? '') + (run.stderr ?? '') + (run.error ? `\n${run.error.message}\n` : '')
  writeFileSync(`evidence/${name}.log`, output)
  const result = { name, command: [command, ...args], exit_code: run.status, signal: run.signal,
    elapsed_ms: Math.round(performance.now() - start), status: run.status === 0 ? 'PASS' : 'FAIL',
    log: `${name}.log`, log_sha256: sha(output) }
  results.push(result); console.log(`${name}: ${result.status}`)
  if (name === 'build' && run.status !== 0) break
}
let verificationError = null
try {
  assert.equal(results.length, stages.length, 'All stages must execute')
  assert.ok(results.every(item => item.status === 'PASS'), 'One or more verification stages failed')
  assert.equal(initialStatus, '', 'Tracked source must be clean at replay start')
  assert.equal(git('status', '--porcelain', '--untracked-files=no'), '', 'Replay mutated tracked source')
  for (const item of sourceManifest) assert.equal(sha(readFileSync(join(root, item.path))), item.sha256, `Source changed: ${item.path}`)
  const http = JSON.parse(readFileSync('evidence/http-trace.json', 'utf8'))
  assert.equal((await validateDemoTrace(http.trace)).verdict, 'PASS')
  assert.equal(http.bridge_requests_observed, 0)
  for (const name of ['desktop', 'mobile']) {
    const browser = JSON.parse(readFileSync(`evidence/browser-${name}-trace.json`, 'utf8'))
    assert.equal((await validateDemoTrace(browser.trace)).verdict, 'PASS')
    assert.equal(browser.bridge_requests_observed, 0)
  }
} catch (error) { verificationError = error.message }
const sdkVersion = existsSync('node_modules/@modelcontextprotocol/sdk/package.json')
  ? JSON.parse(readFileSync('node_modules/@modelcontextprotocol/sdk/package.json', 'utf8')).version : 'UNAVAILABLE'
const observedAt = new Date().toISOString()
const allPassed = verificationError === null
const contract = JSON.parse(readFileSync('docs/feedback-contract.json', 'utf8'))
const evidenceRef = name => ({ path: name, sha256: sha(readFileSync(`evidence/${name}`)) })
const feedback = { schema_version: contract.schema_version, contract: contract.name,
  prior_artifact_binding: contract.provenance.prior_artifact_binding, records: [{
    tool: 'Alexa+ track self-hosted MCP / own web simulator route', provider: 'Amazon', usage_status: 'DOCUMENTATION_ONLY',
    version_or_endpoint: 'https://amazonappdev2026.devpost.com/details/faqs (reviewed October 7, 2026)',
    purpose: 'Select the permitted self-hosted MCP submission path without gated Alexa+ tools.',
    worked_well: 'The FAQ explicitly describes a web page that sends MCP initialize, tools/list and tools/call over Streamable HTTP.',
    improvements: 'Repeat the same ungated path and tooling-availability notice in each linked setup guide; the FAQ itself acknowledges inconsistent setup-page messaging.',
    onboarding: 'Documentation was sufficient to choose the local route. No Alexa developer-console onboarding or Amazon runtime execution was attempted.',
    use_again: { decision: 'YES_FOR_THIS_DOCUMENTED_ROUTE', reason: 'A locally runnable simulator can demonstrate the protocol without cloud spend or additional identity authority.' },
    observation: { kind: 'OFFICIAL_DOCUMENTATION_REVIEW', observed_at: '2026-10-07', source_commit: sourceCommit },
    evidence: [{ official_url: 'https://amazonappdev2026.devpost.com/details/faqs', sections: ['gated Alexa+ tooling', 'real MCP client web page', 'local public repository'] }]
  }, {
    tool: '@modelcontextprotocol/sdk', provider: 'Model Context Protocol project (not Amazon)',
    usage_status: allPassed ? 'ACTUALLY_EXECUTED' : 'BLOCKED', version_or_endpoint: `${sdkVersion}; local POST /mcp`,
    purpose: 'Expose the existing AEGIS tool registry using both stdio and Streamable HTTP.',
    worked_well: allPassed ? 'Actual SDK lifecycle, policy read, consequential denial, preserved stdio resources and desktop/mobile Chromium replay all passed.' : 'No complete runtime-success claim: inspect stage logs.',
    improvements: 'This integration requires explicit Host/Origin validation, session quotas, caller-to-authority separation and evidence redaction outside the tool registry.',
    onboarding: results.map(item => `${item.name}: ${item.status}, ${item.elapsed_ms} ms, ${item.log}`).join('; '),
    use_again: { decision: allPassed ? 'YES' : 'PENDING_VERIFICATION', reason: allPassed ? 'The same registry serves both transports without duplicating authority decisions.' : 'A complete runtime replay has not passed.' },
    observation: { kind: allPassed ? 'ACTUAL_LOCAL_SDK_REPLAY' : 'INCOMPLETE_RUNTIME_REPLAY', observed_at: observedAt, source_commit: sourceCommit },
    evidence: results.map(item => evidenceRef(item.log))
  }], not_used: ['Alexa+ Category SDK', 'Alexa+ MCP Toolkit', 'Alexa+ CLI', 'Amazon Web Simulator', 'AWS services', 'Bedrock'] }
for (const record of feedback.records) {
  for (const field of contract.required_per_tool) assert.ok(Object.hasOwn(record, field), `Missing feedback dimension: ${field}`)
  for (const field of contract.use_again_required) assert.ok(record.use_again[field])
  for (const field of contract.observation_required) assert.ok(record.observation[field])
  assert.ok(contract.usage_status_enum.includes(record.usage_status)); assert.ok(record.evidence.length)
}
writeFileSync('evidence/friction-log.json', JSON.stringify(feedback, null, 2) + '\n')
writeFileSync('evidence/friction-log.md', '# Amazon lane feedback\n\nPrior contract artifact binding: NOT_LOCATED. Existing requested dimensions are preserved.\n\n' +
  feedback.records.map(record => `## ${record.tool}\n\nProvider: ${record.provider}. Usage: ${record.usage_status}.\n\n` +
    ['version_or_endpoint', 'purpose', 'worked_well', 'improvements', 'onboarding'].map(key => `**${key}:** ${record[key]}\n\n`).join('') +
    `**Use again:** ${record.use_again.decision} — ${record.use_again.reason}\n\nEvidence: ${JSON.stringify(record.evidence)}\n`).join('\n'))
// Bounded secret scan over this lane's sources and generated text evidence; not a whole-repo security audit.
const forbidden = [/-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----/, /\b(?:AKIA|ASIA)[A-Z0-9]{16}\b/,
  /\bgh[pousr]_[A-Za-z0-9]{30,}\b/, /\bsk-(?:proj-)?[A-Za-z0-9_-]{30,}\b/]
const scanPaths = sourceManifest.filter(item => item.path.startsWith(sourcePrefix)).map(item => join(root, item.path))
scanPaths.push(...readdirSync('evidence').filter(file => /\.(json|md|log)$/.test(file)).map(file => resolve('evidence', file)))
const findings = scanPaths.filter(path => forbidden.some(pattern => pattern.test(readFileSync(path, 'utf8')))).map(path => relative(root, path))
if (findings.length) verificationError = 'Potential credential material found; do not publish evidence'
const artifacts = readdirSync('evidence').sort().map(path => { const bytes = readFileSync(`evidence/${path}`); return { path, bytes: bytes.length, sha256: sha(bytes) } })
const receipt = { schema_version: '1.0.0', observation: 'EXECUTED_REPLAY_NOT_SIGNED_ATTESTATION', observed_at: observedAt,
  source_commit: sourceCommit, base_commit: '495bfd85d79abcb2b4f6898fe9c156488492426a', sdk_version: sdkVersion,
  runtime: { node: process.version, platform: process.platform, architecture: process.arch },
  verdict: verificationError ? 'FAIL' : 'PASS', verification_error: verificationError, stages: results,
  secret_scan: { scope: 'Lane source and generated text evidence; pattern-based, not exhaustive', findings },
  source_manifest: sourceManifest, artifacts, admission: 'NOT_ADMITTED', submission: 'NOT_SUBMITTED',
  limits: ['No Alexa runtime or gated tool access.', 'HTTP caller identity deliberately unbound.', 'Missing-identity gate exercised; approved consequential execution is not exercised.',
    'No external model call or AWS service is used by the tested sequence.', 'No whole-monorepo test or complete security audit is claimed.'] }
writeFileSync('evidence/receipt.json', JSON.stringify(receipt, null, 2) + '\n')
writeFileSync('evidence/REPORT.md', `# AEGIS Alexa+ lane replay\n\n**${receipt.verdict}** · source \`${sourceCommit}\` · ${observedAt}\n\n` +
  results.map(item => `${item.name}: **${item.status}**, exit ${item.exit_code}, ${item.elapsed_ms} ms. Log: ${item.log}.`).join('\n\n') +
  `\n\nSDK ${sdkVersion}. Repository admission: NOT_ADMITTED. Hackathon submission: NOT_SUBMITTED.\n\n` +
  (verificationError ? `Failure: ${verificationError}\n\n` : 'Actual HTTP and Chromium traces were independently validated; bridge canaries observed zero requests.\n\n') +
  receipt.limits.join('\n\n') + '\n')
console.log(`AEGIS_ALEXA_LANE ${receipt.verdict} ${sourceCommit}`)
if (verificationError) process.exitCode = 1
