/**
 * AEGIS Ω / Sovereign Matter v2 — source-level non-regression checks.
 * Scope: source guards only; not browser GPU, UX or independent WCAG.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const matter = readFileSync(new URL('../src/components/SovereignMatter.tsx', import.meta.url), 'utf8')
const field = readFileSync(new URL('../src/components/SovereignField.tsx', import.meta.url), 'utf8')
const filament = readFileSync(new URL('../src/components/EvidenceFilament.tsx', import.meta.url), 'utf8')

function shader() {
  const tick = String.fromCharCode(96)
  const start = matter.indexOf('const FRAGMENT = ' + tick)
  const end = matter.indexOf(tick + '\n\nconst DOMAIN', start)
  assert(start >= 0 && end > start)
  return matter.slice(start, end)
}

test('WebGL2 uses in-house SDF + GGX, Fresnel, ACES tone mapping', () => {
  assert.match(matter, /getContext\('webgl2'/)
  assert.match(shader(), /float distributionGGX\(/)
  assert.match(shader(), /float geometrySmith\(/)
  assert.match(shader(), /vec3 fresnelSchlick\(/)
  assert.match(shader(), /vec3 tonemapACES\(/)
  assert.match(shader(), /float ambientOcclusion\(/)
  assert.doesNotMatch(matter, /new THREE\.|<model-viewer|import.*three/)
})

test('boundary count governs orbit geometry, never represents a verdict', () => {
  const glsl = shader()
  assert.match(glsl, /ring=u_limits>=\.5\?/)
  assert.match(glsl, /ring2=u_limits>=1\.5\?/)
  assert.match(glsl, /ring3=u_limits>=2\.5\?/)
  assert.match(filament, /not mathematical proof dependencies, independent verification, or provider availability/)
})

test('spatial source gesture rotates actual SDF geometry via uniform', () => {
  assert.match(field, /const \[yaw, setYaw\] = useState/)
  assert.match(field, /viewYaw=\{yaw\} motionOverride=\{false\}/)
  assert.match(shader(), /uniform float u_view_angle/)
  assert.match(shader(), /float a=u_view_angle-/)
  assert.match(matter, /yawRef.current = viewYaw \?\? localYaw/)
  assert.match(matter, /gl\.uniform1f\(viewAngle, yawRef\.current\)/)
})

test('dragging changes yaw uniform without recompiling shader on every move', () => {
  assert.match(matter, /redrawRef\.current\?\.\(\)/)
  assert.match(matter, /frame = window\.requestAnimationFrame\(draw\)/)
  assert.match(matter, /\}, \[sourceId, limitCount, activeMotion, reduced, visible, contextEpoch, conceptArt\]\)/)
})

test('render is opt-in, visibility-aware and CPU/GPU budgeted', () => {
  assert.match(matter, /const \[motion, setMotion\] = useState\(false\)/)
  assert.match(matter, /if \(now - last >= 1000 \/ 24\)/)
  assert.match(matter, /w < 600 \? 55 : 82/)
  assert.match(matter, /Math\.min\(1200/)
  assert.match(matter, /Math\.min\(900/)
  assert.match(matter, /IntersectionObserver/)
  assert.match(matter, /document\.hidden/)
})

test('GPU/context fallback disables inaccessible actions', () => {
  assert.match(matter, /webglcontextlost/)
  assert.match(matter, /webglcontextrestored/)
  assert.match(matter, /prefers-reduced-motion: reduce/)
  assert.match(matter, /aria-label="Rotate sculpture left" disabled=\{!available\}/)
  assert.match(matter, /aria-label="Rotate sculpture right" disabled=\{!available\}/)
  assert.match(matter, /disabled=\{reduced \|\| !available\}/)
  assert.match(matter, /PROCEDURAL ART · NOT TELEMETRY/)
})

test('native rotate control never performs model inference or agent actions', () => {
  assert.match(matter, /onClick=\{\(\) => setLocalYaw\(value => Math\.max/)
  assert.match(matter, /onClick=\{\(\) => setLocalYaw\(value => Math\.min/)
  assert.match(matter, /aria-pressed=\{motion && !reduced && available\}/)
  assert.doesNotMatch(matter, /setInterval|Math\.random|fetch\(|broadcastTransaction|sendTransaction/)
})

test('negative mutation guards detect loss of perspective wiring and safety', () => {
  assert.doesNotMatch(field.replace('viewYaw={yaw}', ''), /viewYaw=\{yaw\} motionOverride=\{false\}/)
  assert.doesNotMatch(matter.replace('disabled={!available}', ''), /aria-label="Rotate sculpture left" disabled=\{!available\}/)
  assert.doesNotMatch(shader().replace('float distributionGGX(', 'float broken('), /float distributionGGX\(/)
})
