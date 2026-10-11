import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read=p=>readFileSync(new URL(p,import.meta.url),'utf8')
const shell=read('../src/HolonGlass.tsx')
const hero=read('../src/components/CosmicCommand.tsx')
const jump=read('../src/components/CommandJump.tsx')
const jumpModel=read('../src/lib/commandPaletteModel.ts')
const css=read('../src/components/cosmic-command.css')
const app=read('../src/App.tsx')
const valid=new Set(['/',...Array.from(app.matchAll(/case '([^']+)'/g),m=>m[1])])

test('one shared shell and cinematic homepage without old duplicated hero',()=>{
  assert.match(shell,/import \{ CosmicCommand \} from '\.\/components\/CosmicCommand\.js'/)
  assert.match(shell,/<CosmicCommand \/>/)
  assert.doesNotMatch(shell,/<SovereignMatter /)
  assert.match(shell,/<aside className="cc-side-rail"/)
  assert.match(shell,/<CommandJump \/>/)
})
test('every cinematic node navigates to a published operational route',()=>{
  const block=hero.match(/const NODES = \[([\s\S]*?)\] as const/)?.[1]??''
  const urls=[...block.matchAll(/href:'([^']+)'/g)].map(m=>m[1])
  assert.equal(urls.length,5)
  for(const url of urls)assert.ok(valid.has(url),'Unpublished destination: '+url)
  assert.ok(hero.includes('mode===\'atlas\''))
  assert.ok(hero.includes(".includes(x.href)"))
})
test('sidebar destinations are real and do not duplicate global top navigation on desktop',()=>{
  const block=shell.match(/const SIDE = \[([\s\S]*?)\] as const/)?.[1]??''
  const urls=[...block.matchAll(/href:'([^']+)'/g)].map(m=>m[1])
  assert.equal(urls.length,8)
  for(const url of urls)assert.ok(valid.has(url),'Unpublished sidebar link '+url)
  assert.match(css,/@media\(min-width:1200px\)/)
  assert.match(css,/\.hg-site \.hg-links\{display:none\}/)
})
test('route command search indexes published routes only and supports escape',()=>{
  const block=jumpModel.match(/const COMMAND_ROUTES = \[([\s\S]*?)\] as const/)?.[1]??''
  const urls=[...block.matchAll(/href:'([^']+)'/g)].map(m=>m[1])
  assert.equal(urls.length,9)
  assert.equal(new Set(urls).size,urls.length)
  for(const url of urls)assert.ok(valid.has(url))
  assert.match(jump,/e\.metaKey\|\|e\.ctrlKey/)
  assert.match(jump,/e\.key==='Escape'/)
  assert.match(jump,/root\.current\?\.contains\(e\.target\)/)
  assert.match(jump,/trigger\.current\?\.focus\(\)/)
  assert.match(jump,/nextPaletteIndex\(/)
  assert.match(jump,/filterCommandRoutes\(/)
  assert.doesNotMatch(jump,/fetch\(|localStorage|sessionStorage/)
})
test('no fake metrics, activity, health, proof, or agent status in authored scene',()=>{
  assert.doesNotMatch(hero,/all systems online|verified results|running agents|Math\.random|fetch\(/i)
  assert.match(hero,/NO LIVE TELEMETRY/)
  assert.match(hero,/not scientific or runtime telemetry/i)
  assert.match(shell,/Unknown stays unknown|UNKNOWN/)
})
test('mobile, reduced motion, enhanced contrast and keyboard focus have explicit paths',()=>{
  assert.match(css,/@media\(max-width:600px\)/)
  assert.match(css,/@media\(max-width:360px\)/)
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/)
  assert.match(css,/@media\(prefers-contrast:more\)/)
  assert.match(css,/:focus-visible/)
  assert.match(css,(/\.hg-site \.hg-nav-cta\{width:44px;min-width:44px;height:44px/))
})
test('hero SVG is decorative and outside the reading order of real links',()=>{
  assert.match(hero,/role="img" aria-label="Decorative planetary/)
  assert.match(css,/pointer-events:none/)
  assert.match(hero,/className="cc-map-node" href=\{x.href\}/)
})
test('cosmic material CSS braces are balanced',()=>{
  let depth=0
  for(const char of css.replace(/\/\*[\s\S]*?\*\//g,'')){
    if(char==='{')depth++
    if(char==='}')depth--
    assert.ok(depth>=0)
  }
  assert.equal(depth,0)
})
