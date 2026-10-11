// Source-level regression guards for Holon Glass navigation and decorative motion.
// These do NOT replace real browser, assistive-technology, usability or WCAG testing.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const jsx = readFileSync(new URL('../src/HolonGlass.tsx', import.meta.url), 'utf8')
const css = readFileSync(new URL('../src/holon-glass.css', import.meta.url), 'utf8')

function inspect(ui, stylesheet) {
  const checks = {
    mobileMenuBound: /<nav ref=\{menuRef\} id="hg-primary-nav"/.test(ui) &&
      /ref=\{menuToggleRef\} className="hg-menu-toggle"/.test(ui),
    menuDisclosure: /aria-controls="hg-primary-nav" aria-expanded=\{open\}/.test(ui),
    menuOpensAtFirstLink: /if \(open\) menuRef\.current\?\.querySelector\('a'\)\?\.focus\(\)/.test(ui),
    menuEscapeRestoresFocus: /if \(event\.key === 'Escape'\) \{\s*setOpen\(false\)\s*menuToggleRef\.current\?\.focus\(\)/.test(ui),
    motionDefaultIsPaused: /const \[motionEnabled,setMotionEnabled\] = useState\(false\)/.test(ui) &&
      /motionEnabled\?'':' hg-motion-paused'/.test(ui),
    motionControlOutsideHiddenVisual: /<div className="hg-orbit-stage"><Orbit\/><button/.test(ui) &&
      /className="hg-orbit" aria-hidden="true"/.test(ui),
    motionIsOperable: /className="hg-motion-control" aria-label="Ambient animation" aria-pressed=\{motionEnabled\}/.test(ui) &&
      /onClick=\{\(\)=>setMotionEnabled\(enabled=>!enabled\)\}/.test(ui),
    orbitAndHolonsStop: /\.hg-motion-paused \.hg-orbit-turn,\s*\.hg-motion-paused \.hg-holon-a,\s*\.hg-motion-paused \.hg-holon-b\s*\{animation-play-state:paused!important\}/.test(stylesheet),
    prefersReducedMotionWins: /@media\(prefers-reduced-motion:reduce\)\s*\{[\s\S]*?\.hg-motion-control\{display:none\}[\s\S]*?\.hg-orbit-turn,\.hg-holon-a,\.hg-holon-b\{animation:none!important\}/.test(stylesheet),
    controlHasTouchTargetAndFocus: /\.hg-motion-control\{[\s\S]*?min-height:44px/.test(stylesheet) &&
      /\.hg-motion-control:focus-visible\{outline:2px solid/.test(stylesheet),
  }
  return checks
}
const checklist = inspect(jsx, css)

for (const [name, present] of Object.entries(checklist)) {
  test('current source: ' + name, () => assert.equal(present, true, 'required interaction contract missing'))
}

test('negative: missing ref is detected', () => {
  assert.equal(inspect(jsx.replace('ref={menuToggleRef} className="hg-menu-toggle"',
    'className="hg-menu-toggle"'), css).mobileMenuBound, false)
})
test('negative: Escape without focus restoration is detected', () => {
  assert.equal(inspect(jsx.replace('menuToggleRef.current?.focus()', ''),
    css).menuEscapeRestoresFocus, false)
})
test('negative: unpaused auto-playing motion is detected', () => {
  assert.equal(inspect(jsx.replace('useState(false)', 'useState(true)'),
    css).motionDefaultIsPaused, false)
})
test('negative: control without real state transition is detected', () => {
  assert.equal(inspect(jsx.replace('setMotionEnabled(enabled=>!enabled)',
    'setMotionEnabled(enabled=>enabled)'), css).motionIsOperable, false)
})
test('negative: silent removal of pause CSS is detected', () => {
  assert.equal(inspect(jsx, css.replace('animation-play-state:paused!important',
    'animation-play-state:running!important')).orbitAndHolonsStop, false)
})
test('negative: removing explicit reduced-motion override is detected', () => {
  assert.equal(inspect(jsx, css.replace('.hg-orbit-turn,.hg-holon-a,.hg-holon-b{animation:none!important}',
    '')).prefersReducedMotionWins, false)
})
