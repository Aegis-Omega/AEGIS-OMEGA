/* AEGIS Ω — whole-site visual architecture regression checks.
   Pure Node tests: structural guarantees, not a substitute for browser QA. */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const files = {
  visual: readFileSync(new URL('../src/aegis-visual-universe.css',import.meta.url),'utf8'),
  holon: readFileSync(new URL('../src/HolonGlass.tsx',import.meta.url),'utf8'),
  app: readFileSync(new URL('../src/App.tsx',import.meta.url),'utf8'),
}
const embedded = ['PricingPage','CompliancePage','DocsPage','ToolsPage']
  .map(name=>readFileSync(new URL('../src/components/'+name+'.tsx',import.meta.url),'utf8'))

test('all published hub surfaces inherit the same global visual system',()=>{
  assert.match(files.holon,/import '\.\/aegis-visual-universe\.css'/)
  const routes=[...files.app.matchAll(/case '\/([^']+)'/g)].map(x=>x[1])
  assert.equal(routes.length,8,'8 non-home routes + homepage')
  for(const route of routes)assert.ok(files.visual.includes('.hg-route-'+route),
    'Missing visual coverage for /'+route)
  assert.ok(files.visual.includes('.hg-site-home'))
})
test('duplicate nested navigation is visually suppressed, never deleted from page logic',()=>{
  for(const [index,source] of embedded.entries()){
    assert.match(source,/className="av-embedded-nav /,'Nav not tagged: '+index)
  }
  assert.match(files.visual,/\.hg-route \.hg-legacy-content \.av-embedded-nav\{display:none!important\}/)
  assert.match(files.holon,/aria-label="Primary navigation"/)
  assert.match(files.holon,/href="#hg-main"/)
})
test('editorial asymmetry does not remove responsive single-column fallback',()=>{
  assert.match(files.visual,/\.hg-domains \.hg-domain:nth-child\(1\)/)
  assert.match(files.visual,/@media\(max-width:900px\)/)
  assert.match(files.visual,/@media\(max-width:600px\)/)
  assert.match(files.visual,/@media\(max-width:360px\)/)
})
test('accessibility preferences win over ambient motion',()=>{
  assert.match(files.visual,/@media\(prefers-reduced-motion:reduce\)/)
  assert.match(files.visual,/animation-duration:\.01ms!important/)
  assert.match(files.visual,/@media\(prefers-contrast:more\)/)
  assert.match(files.visual,/:focus-visible/)
})
test('visual design tokens follow canonical AEGIS identity rather than imported themes',()=>{
  assert.match(files.visual,/var\(--aegis-phi,/)
  assert.match(files.visual,/--hg-bg: var\(--av-canvas\)/)
  assert.match(files.visual,/--av-foil: var\(--aegis-phi,/)
  assert.doesNotMatch(files.visual,/@import\s+url\(/)
})
function rgb(hex) {
  return hex.match(/[a-f\d]{2}/gi).map(s=>parseInt(s,16)/255)
    .map(s=>s<=.04045?s/12.92:((s+.055)/1.055)**2.4)
}
function luminance(hex) {
  const [r,g,b]=rgb(hex)
  return .2126*r+.7152*g+.0722*b
}
function contrast(a,b){
  const x=luminance(a),y=luminance(b)
  return (Math.max(x,y)+.05)/(Math.min(x,y)+.05)
}
test('canonical body, muted text and primary call-to-action pairs meet WCAG AA text contrast',()=>{
  assert.ok(contrast('#eeeae1','#080c0f')>=4.5)
  assert.ok(contrast('#b5b9b6','#080c0f')>=4.5)
  assert.ok(contrast('#0d1415','#d6c19a')>=4.5)
})
test('visual system stylesheet syntax is balanced, independent of optional WebGL',()=>{
  const raw=files.visual.replace(/\/\*[\s\S]*?\*\//g,'')
  let count=0
  for (const character of raw){
    if(character==='{')count++
    if(character==='}')count--
    assert.ok(count>=0)
  }
  assert.equal(count,0)
  assert.doesNotMatch(raw,/canvas\.getContext|fetch\(|WebGLRenderingContext/)
})


test('section context rail replaces duplicated visual heading on nested pages',()=>{
  assert.match(files.holon,/className="av-route-rail hg-content"/)
  assert.match(files.visual,/\.hg-route:not\(\.hg-route-docs\) > \.hg-route-header\{display:none\}/)
  assert.match(files.visual,/\.hg-route-docs > \.hg-route-header/)
  const docs=readFileSync(new URL('../src/components/DocsPage.tsx',import.meta.url),'utf8')
  assert.doesNotMatch(docs,/<main(?:\s|>)/,'nested main landmark under shared main')
  assert.match(docs,/aria-label="API reference sections"/)
})
