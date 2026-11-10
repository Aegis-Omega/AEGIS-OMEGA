/**
 * Exact React-component GLSL extraction guards for the Sovereign Matter renderer.
 * These validate source syntax boundaries, not WebGL driver certification.
 */
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const tsx=readFileSync(new URL('../src/components/SovereignMatter.tsx',import.meta.url),'utf8')
function shaderFromSource(source) {
  const mark='const FRAGMENT = '+String.fromCharCode(96)
  const start=source.indexOf(mark)
  const end=source.indexOf(String.fromCharCode(96)+'\n\nconst DOMAIN',start)
  assert(start>=0&&end>start,'React component must contain exactly one bounded GLSL template')
  return source.slice(start+mark.length,end)
}
function assertBraces(source) {
  // Match executable GLSL, excluding comments; tests separately verify source markers.
  const clean=source.replace(/\/\*[\s\S]*?\*\//g,'').replace(/\/\/[^\n]*/g,'')
  let depth=0
  for(const c of clean) {
    if(c==='{')depth++
    if(c==='}')depth--
    assert(depth>=0,'unexpected shader closing brace')
  }
  assert.equal(depth,0,'unclosed shader brace')
}

test('the actual component shader has balanced GLSL scope and a single main',()=>{
  const shader=shaderFromSource(tsx)
  assertBraces(shader)
  assert.match(shader,/^#version 300 es\nprecision highp float;/)
  assert.equal([...shader.matchAll(/\bvoid main\(\)/g)].length,1)
  assert.match(shader,/\n}\s*$/,'shader closes cleanly after main')
})

test('regression catches the original extra-brace bug in the React shader',()=>{
  const valid=shaderFromSource(tsx)
  assert.throws(()=>assertBraces(valid+'}'),/closing brace/)
  assert.throws(()=>assertBraces(valid.slice(0,valid.lastIndexOf('}'))),/unclosed shader brace/)
})

test('implicit field, authored strands and mobile shader steps belong to the real component',()=>{
  const shader=shaderFromSource(tsx)
  for(const token of ['float holonField(','float evidenceStrand(','float distributionGGX(','uniform float u_limits;',
    'uniform float u_view_angle;','uniform float u_step_count;','float shell=u_concept>.5?omega(p):holonField(p)']) {
    assert(shader.includes(token),'missing shader symbol: '+token)
  }
  for(const token of ['ring=u_limits>=.5?','ring2=u_limits>=1.5?','ring3=u_limits>=2.5?'])assert(shader.includes(token))
  assert.match(tsx,/w < 600 \? 55 : 82/)
  assert.match(tsx,/Math\.min\(1200/)
  assert.match(tsx,/Math\.min\(900/)
})

test('shader source never invents execution authority or uses non-deterministic progress',()=>{
  const shader=shaderFromSource(tsx)
  assert.doesNotMatch(shader,/fetch\(|Math\.random|approved|proofComplete|transaction/i)
  assert.match(tsx,/PROCEDURAL ART · NOT TELEMETRY/)
})
