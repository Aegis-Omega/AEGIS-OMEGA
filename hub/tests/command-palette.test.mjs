import test from 'node:test'
import assert from 'node:assert/strict'
import { COMMAND_ROUTES, filterCommandRoutes, nextPaletteIndex } from '../src/lib/commandPaletteModel.ts'

test('command route registry contains nine distinct published destinations',()=>{
  const routes=COMMAND_ROUTES.map(item=>item.href)
  assert.equal(routes.length,9)
  assert.equal(new Set(routes).size,routes.length)
  for(const route of routes)assert.match(route,/^\/(?:[a-z-]+)?$/)
})
test('search ignores case and surrounding whitespace without network access',()=>{
  assert.deepEqual(filterCommandRoutes('  RESEARCH ' ).map(r=>r.href),['/platform'])
  assert.deepEqual(filterCommandRoutes('console').map(r=>r.href),['/console'])
  assert.deepEqual(filterCommandRoutes('absent query'),[])
})
test('empty query exposes all published route choices, no synthesized entries',()=>{
  const original=COMMAND_ROUTES.map(r=>r.href)
  assert.deepEqual(filterCommandRoutes(' ').map(r=>r.href),original)
})
test('ArrowDown starts at first result and wraps after last',()=>{
  assert.equal(nextPaletteIndex(-1,4,'ArrowDown'),0)
  assert.equal(nextPaletteIndex(2,4,'ArrowDown'),3)
  assert.equal(nextPaletteIndex(3,4,'ArrowDown'),0)
})
test('ArrowUp starts at last result and returns to input from the first',()=>{
  assert.equal(nextPaletteIndex(-1,4,'ArrowUp'),3)
  assert.equal(nextPaletteIndex(2,4,'ArrowUp'),1)
  assert.equal(nextPaletteIndex(0,4,'ArrowUp'),-1)
})
test('Home and End move to actual first and last indices',()=>{
  assert.equal(nextPaletteIndex(2,4,'Home'),0)
  assert.equal(nextPaletteIndex(0,4,'End'),3)
})
test('empty list cannot receive focus',()=>{
  for(const key of ['ArrowDown','ArrowUp','Home','End'])
    assert.equal(nextPaletteIndex(-1,0,key),-1)
})
test('no access to a route outside the source-owned registry',()=>{
  assert.equal(filterCommandRoutes('admin').length,0)
  assert.equal(filterCommandRoutes('secret').length,0)
})
