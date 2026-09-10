import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const scriptPath = 'native/dlss5-windows-preflight/aegis_dlss5_windows_host_bootstrap.ps1'
const script = readFileSync(scriptPath, 'utf8')

const STREAMLINE_SHA256 = '92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b'
const STREAMLINE_SOURCE_SHA = '2122257e0fce486f91b385aa63b9a09b0a34b363'

assert.match(script, /param\s*\([\s\S]*CandidateSha/, 'bootstrap must require an exact candidate SHA')
assert.match(script, /\^\[0-9a-fA-F\]\{40\}\$/, 'candidate SHA must be exactly 40 hex characters')
assert.match(script, /nvidia-smi/, 'bootstrap must interrogate the physical NVIDIA adapter')
assert.match(script, /--query-gpu=name,driver_version/, 'bootstrap must bind GPU name and driver version')
assert.match(script, /GeForce\s+RTX\s+50/i, 'bootstrap must reject non-GeForce RTX 50 hardware')
assert.match(script, new RegExp(STREAMLINE_SHA256), 'bootstrap must pin the official Streamline 2.14.1 release digest')
assert.match(script, new RegExp(STREAMLINE_SOURCE_SHA), 'bootstrap receipt must bind the reviewed Streamline source commit')
assert.match(script, /Get-FileHash[\s\S]*SHA256/, 'downloaded Streamline archive must be SHA-256 verified')
assert.match(script, /AEGIS_DLSS5_WINDOWS_HOST_BOOTSTRAP_RECEIPT_V1/, 'bootstrap must emit a versioned evidence receipt')
assert.match(script, /support_query_executed[^\r\n]*false/i, 'bootstrap stage must not claim the Streamline support query ran')
assert.match(script, /evaluation_executed[^\r\n]*false/i, 'bootstrap stage must never claim evaluation ran')
assert.match(script, /rendering_claim[^\r\n]*NOT_ESTABLISHED/i, 'rendering claim must remain not established')
assert.match(script, /quality_claim[^\r\n]*NOT_ESTABLISHED/i, 'quality claim must remain not established')
assert.match(script, /claim_promotion[^\r\n]*BLOCKED/i, 'claim promotion must remain blocked')
assert.match(script, /authority_effect[^\r\n]*NONE/i, 'bootstrap must grant no authority')
assert.doesNotMatch(script, /slEvaluateFeature|Start-Process\s+.*aegis-dlss5-windows-preflight/i, 'bootstrap contract must not execute the DLSS feature or preflight binary')

console.log('DLSS5_WINDOWS_BOOTSTRAP_SOURCE_PASS gpu_identity=1 sdk_digest=1 support_query=0 evaluate=0 authority=NONE')
