import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const PINNED_STREAMLINE_SHA = '2122257e0fce486f91b385aa63b9a09b0a34b363'
const headerPath = 'native/dlss5-host-shim/aegis_dlss5_host_shim.hpp'
const sourcePath = 'native/dlss5-host-shim/aegis_dlss5_host_shim.cpp'

const header = readFileSync(headerPath, 'utf8')
const source = readFileSync(sourcePath, 'utf8')

assert.match(header, /#include\s+[<"]sl\.h[>"]/, 'shim must compile against the public Streamline header')
assert.match(header, /HostProbeObservation/, 'shim must expose a bounded observation object')
assert.match(header, /probeOnce/, 'shim must expose one host-owned probe entry point')

assert.match(source, new RegExp(PINNED_STREAMLINE_SHA), 'source must bind its reviewed API surface to the pinned Streamline release commit')
assert.match(source, /static_assert\s*\(\s*sl::kFeatureDLSS_NR\s*==\s*1004/, 'official DLSS-NR feature identifier must be compile-time checked')
assert.match(source, /slIsFeatureSupported\s*\(\s*sl::kFeatureDLSS_NR\s*,/, 'support query must use the public Streamline API')
assert.match(source, /slEvaluateFeature\s*\(\s*sl::kFeatureDLSS_NR\s*,/, 'evaluation must use the public Streamline API')
assert.doesNotMatch(source, /NVSDK_NGX|nvngx_dlssnr|GetModuleHandle|LoadLibrary|dlopen/, 'shim must not bypass Streamline through direct NGX or dynamic-loader routes')
assert.doesNotMatch(source, /system\s*\(|popen\s*\(|CreateProcess|ShellExecute/, 'shim must not spawn external processes')

console.log('DLSS5_HOST_SHIM_SOURCE_PASS streamline=2122257e0fce486f91b385aa63b9a09b0a34b363 feature=1004 query=slIsFeatureSupported evaluate=slEvaluateFeature standalone=0 bypass=0 authority=NONE')
