import test from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'

// Guard only the mobile editorial rules. This is not an automated visual,
// screen-reader, WCAG or real-user usability verdict.
const stylesheet = readFileSync(new URL('../src/holon-glass.css', import.meta.url), 'utf8')
const marker = '/* Responsive editorial legibility pass: preserve Holon Glass hierarchy, remove sub-10px mobile copy. */'

function mobileRules(css) {
  const start = css.lastIndexOf(marker)
  if (start < 0) throw Error('mobile legibility override not found')
  const tail = css.slice(start)
  if (!tail.startsWith(marker) || !tail.includes('@media (max-width:600px)')) throw Error('invalid mobile override')
  return tail
}
function requireSize(css, selector, size) {
  const tail = mobileRules(css)
  return tail.includes(selector+'{font-size:'+size+'px')
}

test('mobile editorial rules explicitly follow the base stylesheet', () => {
  assert.ok(stylesheet.indexOf('.hg-orbit-caption{') < stylesheet.lastIndexOf(marker))
  assert.ok(stylesheet.indexOf('@media(max-width:600px)') < stylesheet.lastIndexOf(marker))
})
test('hero narrative and overlay captions are not 7-8px on mobile', () => {
  assert.ok(requireSize(stylesheet, '.hg-hero-note', 11))
  assert.ok(requireSize(stylesheet, '.hg-orbit-caption', 11))
})
test('domain information labels remain readable', () => {
  assert.match(mobileRules(stylesheet), /\.hg-domain-top,\.hg-domain-tag\{font-size:11px/)
  assert.ok(requireSize(stylesheet, '.hg-footer-bottom', 11))
})
test('brand subline stays larger while very narrow navigation omits it', () => {
  assert.ok(requireSize(stylesheet, '.hg-brand-word small', 10))
  assert.match(mobileRules(stylesheet), /@media \(max-width:360px\)\s*\{[^}]*\.hg-brand-word small\{display:none\}/)
})
test('long micro-labels wrap instead of forcing horizontal overflow', () => {
  assert.match(mobileRules(stylesheet), /\.hg-hero-note\{[^}]*overflow-wrap:anywhere/)
  assert.match(mobileRules(stylesheet), /\.hg-orbit-caption\{[^}]*overflow-wrap:anywhere/)
})
test('negative: removal of mobile override is noticed', () => {
  assert.throws(() => mobileRules(stylesheet.replace(marker, '')), /not found/)
})
test('negative: reintroduction of 7px hero label is detected', () => {
  assert.equal(requireSize(stylesheet.replace('.hg-hero-note{font-size:11px', '.hg-hero-note{font-size:7px'), '.hg-hero-note', 11), false)
})
test('negative: removing 360px collision guard is detected', () => {
  const edited = stylesheet.replace('@media (max-width:360px)', '@media (max-width:120px)')
  assert.doesNotMatch(mobileRules(edited), /@media \(max-width:360px\)/)
})
