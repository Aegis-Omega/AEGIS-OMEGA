import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const PINNED_STREAMLINE_SHA = '2122257e0fce486f91b385aa63b9a09b0a34b363'
const RELEASE_SHA256 = '92c4d954631a1710da86ca3fa8d5034f2b9503838c95fc4ae977ae149319781b'
const sourcePath = 'native/dlss5-windows-preflight/aegis_dlss5_windows_preflight.cpp'
const compileWorkflowPath = '../../.github/workflows/dlss5-windows-preflight-compile.yml'
const runtimeWorkflowPath = '../../.github/workflows/dlss5-windows-rtx50-preflight.yml'

const source = readFileSync(sourcePath, 'utf8')
const compileWorkflow = readFileSync(compileWorkflowPath, 'utf8')
const runtimeWorkflow = readFileSync(runtimeWorkflowPath, 'utf8')

assert.match(source, new RegExp(PINNED_STREAMLINE_SHA), 'preflight source must bind reviewed API semantics to the pinned Streamline commit')
assert.match(source, new RegExp(RELEASE_SHA256), 'preflight source must bind the official x64 release ZIP digest')
assert.match(source, /static_assert\s*\(\s*sl::kFeatureDLSS_NR\s*==\s*1004/, 'DLSS-NR feature id must be compile-time checked')
assert.match(source, /slInit\s*\(/, 'preflight must initialize Streamline before DXGI enumeration')
assert.match(source, /CreateDXGIFactory/, 'preflight must enumerate the Windows DXGI adapter')
assert.match(source, /AdapterLuid/, 'preflight must bind support query to a concrete adapter LUID')
assert.match(source, /slIsFeatureSupported\s*\(\s*sl::kFeatureDLSS_NR\s*,/, 'preflight must use the public support-query API')
assert.match(source, /slShutdown\s*\(/, 'preflight must close Streamline')
assert.doesNotMatch(source, /slEvaluateFeature\s*\(/, 'preflight must not execute DLSS-NR evaluation or rendering')
assert.doesNotMatch(source, /eBypassOSVersionCheck|NVSDK_NGX|nvngx_dlssnr/, 'preflight must not bypass OS or Streamline policy')

assert.match(compileWorkflow, /windows-latest/, 'compile lane must use a Windows hosted runner')
assert.match(compileWorkflow, new RegExp(RELEASE_SHA256), 'compile lane must verify the exact official release digest')
assert.match(compileWorkflow, /github\.event\.pull_request\.head\.sha/, 'PR compile lane must checkout the exact PR head rather than the synthetic merge commit')
assert.match(compileWorkflow, /git\s+rev-parse\s+HEAD/, 'compile lane must bind its receipt to the checked-out commit')
assert.match(compileWorkflow, /AEGIS_CANDIDATE_SHA/, 'compile receipt must use the checked-out exact candidate SHA')
assert.match(compileWorkflow, /gpu_execution=false/, 'compile receipt must state that no GPU execution occurred')

assert.match(runtimeWorkflow, /workflow_dispatch:/, 'runtime lane must be manual-only')
assert.match(runtimeWorkflow, /self-hosted/, 'runtime lane must require a self-hosted GPU runner')
assert.match(runtimeWorkflow, /windows/, 'runtime lane must require Windows')
assert.match(runtimeWorkflow, /rtx50/, 'runtime lane must require RTX-50 capability labeling')
assert.match(runtimeWorkflow, /timeout-minutes:/, 'runtime lane must have a hard timeout')
assert.match(runtimeWorkflow, /git\s+rev-parse\s+HEAD/, 'runtime lane must bind the requested SHA to the actual checkout')
assert.doesNotMatch(runtimeWorkflow, /pull_request:|push:/, 'paid/runtime lane must never auto-run on code changes')

console.log('DLSS5_WINDOWS_PREFLIGHT_SOURCE_PASS support_only=1 evaluate=0 exact_head=1 manual_runtime=1 authority=NONE')
