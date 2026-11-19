/**
 * AEGIS Ω ResearchOS / source-first fusion regression.
 * Static source guards + bounded data-model checks; not browser, a11y or CI certification.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { selectEvidenceFilament } from '../src/lib/evidenceFilament.ts'

const component = readFileSync(new URL('../src/components/ResearchWorkbench.tsx', import.meta.url),'utf8')
const css = readFileSync(new URL('../src/components/research-workbench.css', import.meta.url),'utf8')
const material = readFileSync(new URL('../src/components/EvidenceFilament.tsx', import.meta.url),'utf8')

const samples = Object.freeze([
  Object.freeze({id:'math',index:'01',title:'Mathematics',kind:'SOURCE',status:'OPEN',question:'Is the proof closed?',boundaries:Object.freeze(['Source must be pinned'])}),
  Object.freeze({id:'biology',index:'02',title:'Biology',kind:'RESTRICTED',status:'UNKNOWN',question:'Does holdout reproduce?',boundaries:Object.freeze(['Holdout is not published','Scope remains open'])}),
])

test('one source selection drives both existing data-bound views',()=>{
  assert.match(component,/import \{ SovereignField \} from '\.\/SovereignField\.js'/)
  assert.match(component,/import \{ EvidenceFilament \} from '\.\/EvidenceFilament\.js'/)
  assert.match(component,/const \[perspective,setPerspective\]=useState<'lineage'\|'atlas'>\('lineage'\)/)
  assert.match(component,/perspective==='lineage'\s*\? <EvidenceFilament sources=\{shown\} selectedId=\{detail\?\.id \?\? null\} onSelect=\{setActive\}/)
  assert.match(component,/: <SovereignField sources=\{shown\} selectedId=\{detail\?\.id \?\? null\} onSelect=\{setActive\}/)
  assert.doesNotMatch(component,/<EvidenceFilament.*\/>\s*<SovereignField/s)
})

test('view selection is keyboard-native, explicit and non-executing',()=>{
  assert.match(component,/role="group" aria-label="Choose evidence view"/)
  assert.match(component,/aria-pressed=\{perspective==='lineage'\}/)
  assert.match(component,/aria-pressed=\{perspective==='atlas'\}/)
  assert.match(component,/onClick=\{\(\)=>setPerspective\('lineage'\)\}/)
  assert.match(component,/onClick=\{\(\)=>setPerspective\('atlas'\)\}/)
  assert.doesNotMatch(component,/onClick=\{[^}]*fetch\(/)
})

test('data-bound lineage is limited to actual supplied source and boundaries',()=>{
  const picked=selectEvidenceFilament(samples,'biology')
  assert.equal(picked.source,samples[1])
  assert.deepEqual(picked.links.map(link=>link.relationship),['recorded_open_question','declared_boundary','declared_boundary'])
  assert(picked.links.every(link=>link.from.includes('biology')&&link.to.includes('biology')))
  assert(!picked.links.some(link=>link.label.includes('Source must be pinned')))
  assert.equal(selectEvidenceFilament([],null),null)
})

test('an unavailable or stale selection cannot manufacture a new source',()=>{
  assert.equal(selectEvidenceFilament(samples.slice(1),'math').source.id,'biology')
  assert.equal(selectEvidenceFilament(samples.slice(1),'not-a-source').source.id,'biology')
  assert.equal(samples[1].boundaries.length,2)
})

test('material composition is source-scoped, without fabricated telemetry or synthetic conclusion',()=>{
  assert.match(material,/<SovereignMatter sourceId=\{flow\.source\.id\} limitCount=\{flow\.source\.boundaries\.length\}/)
  assert.match(material,/CURATED DATA · NOT LIVE TELEMETRY/)
  assert.match(material,/not mathematical proof dependencies, independent verification, or provider availability/)
  assert.match(component,/no live agent activity, inferred proof, or execution permission/)
})

test('Sketch-derived reading surfaces and touch targets have explicit bounds',()=>{
  assert.match(css,/AEGIS RESEARCHOS \/ SOURCE-FIRST FUSION V1/)
  assert.match(css,/Sketch source reading hierarchy: 17px\/24px body/)
  assert.match(css,/\.rw-hero p \{font-size:17px;line-height:1\.45\}/)
  assert.match(css,/\.rw-entry p \{font-size:15px;line-height:1\.6\}/)
  assert.match(css,/\.rw-search input \{font-size:16px\}/)
  assert.match(css,/\.rw-perspective-controls button \{[\s\S]*?min-height:46px/)
  assert.match(css,/@media\(max-width:610px\)/)
  assert.match(css,/\.rw-perspective-controls button \{min-height:48px/)
})

test('contrast, focus and motion alternatives are explicit without counterfeit Apple font files',()=>{
  assert.match(css,/\.rw-perspective-controls button:focus-visible \{outline:3px/)
  assert.match(css,/@media\(prefers-reduced-motion:reduce\)/)
  assert.match(css,/@media\(prefers-contrast:more\)/)
  assert.match(css,/@media\(prefers-reduced-transparency:reduce\)/)
  assert.doesNotMatch(css,/@font-face[\s\S]{0,180}SF Pro/)
})

test('negative guard: absent wired filament or accessible view state fails',()=>{
  const broken=component.replace("import { EvidenceFilament } from './EvidenceFilament.js'","")
  assert.doesNotMatch(broken,/import \{ EvidenceFilament \}/)
  const brokenAria=component.replace(/aria-pressed=\{perspective==='atlas'\}/,'')
  assert.doesNotMatch(brokenAria,/aria-pressed=\{perspective==='atlas'\}/)
})
