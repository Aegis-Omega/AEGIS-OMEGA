import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const compileWorkflow = readFileSync('../../.github/workflows/dlss5-windows-preflight-compile.yml', 'utf8')
const runtimeWorkflow = readFileSync('../../.github/workflows/dlss5-windows-rtx50-preflight.yml', 'utf8')

const DOWNLOAD_ARTIFACT_SHA = 'd3f86a106a0bac45b974a628896c90dbdf5c8093'

assert.match(
  compileWorkflow,
  /name:\s*aegis-dlss5-windows-preflight-bundle-\$\{\{\s*github\.run_id\s*\}\}/,
  'hosted compile lane must publish an exact-run preflight bundle'
)
assert.match(
  compileWorkflow,
  /path:\s*\|[\s\S]*dlss5-windows-preflight-compile\.txt[\s\S]*\$\{\{\s*env\.DLSS5_PREFLIGHT_EXE\s*\}\}/,
  'preflight bundle must contain both compile receipt and compiled executable'
)

assert.match(runtimeWorkflow, /compile_run_id:/, 'RTX50 workflow must require the hosted compile run id')
assert.match(
  runtimeWorkflow,
  new RegExp(`actions/download-artifact@${DOWNLOAD_ARTIFACT_SHA}`),
  'RTX50 workflow must pin actions/download-artifact v4 by commit SHA'
)
assert.match(
  runtimeWorkflow,
  /run-id:\s*\$\{\{\s*inputs\.compile_run_id\s*\}\}/,
  'RTX50 workflow must download artifacts from the operator-selected compile run'
)
assert.match(
  runtimeWorkflow,
  /candidate_sha[\s\S]*inputs\.candidate_sha[\s\S]*Exact-head compile receipt mismatch/i,
  'RTX50 workflow must bind the downloaded compile receipt to the requested exact candidate'
)
assert.match(
  runtimeWorkflow,
  /preflight_exe_sha256[\s\S]*Get-FileHash[\s\S]*Preflight executable digest mismatch/i,
  'RTX50 workflow must independently verify the downloaded executable SHA-256'
)
assert.doesNotMatch(
  runtimeWorkflow,
  /vswhere\.exe|cl\s+\/nologo|VsDevCmd\.bat/,
  'RTX50 runtime host must not require a compiler once the hosted bundle exists'
)
assert.match(runtimeWorkflow, /slIsFeatureSupported|support query/i, 'runtime lane must still execute the support-only query')
assert.doesNotMatch(runtimeWorkflow, /slEvaluateFeature/, 'runtime lane must not execute DLSS evaluation')
assert.match(runtimeWorkflow, /authority_effect[\s\S]*NONE/i, 'precompiled-bundle path must grant no authority')

console.log('DLSS5_PRECOMPILED_BUNDLE_SOURCE_PASS hosted_compile=1 runtime_compile=0 exact_head=1 exe_sha256=1 support_query=1 evaluate=0 authority=NONE')
