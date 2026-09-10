import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const scriptPath = 'native/dlss5-windows-preflight/aegis_dlss5_windows_host_bootstrap.ps1'
const workflowPath = '../../.github/workflows/dlss5-windows-bootstrap-smoke.yml'
const script = readFileSync(scriptPath, 'utf8')
const workflow = readFileSync(workflowPath, 'utf8')

const STREAMLINE_SHA256 = '92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b'
const STREAMLINE_SOURCE_SHA = '2122257e0fce486f91b385aa63b9a09b0a34b363'

assert.match(script, /param\s*\([\s\S]*CandidateSha/, 'bootstrap must require an exact candidate SHA')
assert.match(script, /\^\[0-9a-fA-F\]\{40\}\$/, 'candidate SHA must be exactly 40 hex characters')
assert.match(script, /nvidia-smi/, 'bootstrap must interrogate the physical NVIDIA adapter')
assert.match(script, /--query-gpu=name,driver_version/, 'bootstrap must bind GPU name and driver version')
assert.ok(script.includes('GeForce\\s+RTX\\s+50'), 'bootstrap must enforce a GeForce RTX 50 regex rather than a generic NVIDIA GPU')
assert.match(script, /GEFORCE_RTX50_REQUIRED/, 'bootstrap must fail closed when no eligible RTX 50 GPU is present')
assert.match(script, new RegExp(STREAMLINE_SHA256), 'bootstrap must pin the official Streamline 2.14.1 release digest')
assert.match(script, new RegExp(STREAMLINE_SOURCE_SHA), 'bootstrap receipt must bind the reviewed Streamline source commit')
assert.match(script, /Get-FileHash[\s\S]*SHA256/, 'downloaded Streamline archive must be SHA-256 verified')
assert.match(script, /SDK_DOWNLOAD_FAILED/, 'network/download failure must emit a bounded denial receipt')
assert.match(script, /System\.Security\.Cryptography\.SHA256\]::Create\(/, 'receipt hashing must use the Windows PowerShell 5.1-compatible SHA256 instance API')
assert.doesNotMatch(script, /::HashData\(|::ToHexString\(/, 'bootstrap must not depend on newer static .NET hash APIs absent from Windows PowerShell 5.1')
assert.match(script, /AEGIS_DLSS5_WINDOWS_HOST_BOOTSTRAP_RECEIPT_V1/, 'bootstrap must emit a versioned evidence receipt')
assert.match(script, /support_query_executed[^\r\n]*false/i, 'bootstrap stage must not claim the Streamline support query ran')
assert.match(script, /evaluation_executed[^\r\n]*false/i, 'bootstrap stage must never claim evaluation ran')
assert.match(script, /rendering_claim[^\r\n]*NOT_ESTABLISHED/i, 'rendering claim must remain not established')
assert.match(script, /quality_claim[^\r\n]*NOT_ESTABLISHED/i, 'quality claim must remain not established')
assert.match(script, /claim_promotion[^\r\n]*BLOCKED/i, 'claim promotion must remain blocked')
assert.match(script, /authority_effect[^\r\n]*NONE/i, 'bootstrap must grant no authority')
assert.doesNotMatch(script, /slEvaluateFeature|Start-Process\s+.*aegis-dlss5-windows-preflight/i, 'bootstrap contract must not execute the DLSS feature or preflight binary')

assert.match(workflow, /runs-on:\s*windows-latest/, 'smoke lane must execute on a GitHub-hosted Windows runner')
assert.match(workflow, /github\.event\.pull_request\.head\.sha/, 'PR smoke lane must checkout the exact PR head')
assert.match(workflow, /shell:\s*powershell/, 'smoke lane must exercise Windows PowerShell 5.1 compatibility')
assert.match(workflow, /powershell\.exe[\s\S]*aegis_dlss5_windows_host_bootstrap\.ps1/, 'smoke lane must execute the real bootstrap script')
assert.match(workflow, /HOST_UNSUPPORTED/, 'non-RTX50 hosted runner must be accepted only as an explicit fail-closed smoke outcome')
assert.match(workflow, /support_query_executed[\s\S]*false/, 'smoke verification must require support_query_executed=false')
assert.match(workflow, /evaluation_executed[\s\S]*false/, 'smoke verification must require evaluation_executed=false')
assert.match(workflow, /upload-artifact/, 'smoke lane must retain its bounded receipt')
assert.doesNotMatch(workflow, /slEvaluateFeature|aegis_dlss5_windows_preflight\.exe/, 'smoke workflow must not execute DLSS-NR support/evaluation binaries')

console.log('DLSS5_WINDOWS_BOOTSTRAP_SOURCE_PASS gpu_identity=1 sdk_digest=1 ps51=1 smoke=1 support_query=0 evaluate=0 authority=NONE')
