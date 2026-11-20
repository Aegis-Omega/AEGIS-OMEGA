import assert from 'node:assert/strict'
import test from 'node:test'
import { toConsoleSnapshot, unknownSnapshot, isPlatformStatus, isCalibrationStatus } from '../src/lib/platformContract.ts'

const status = () => ({
  version:'1.0.0', contract_version:'1.0.0', total_agents:39,
  chain_valid:true, audit_chain_hash:'abcd', available:true,
})
const calibration = () => ({
  homeostasis_zone:'optimal', recommendation:'MAINTAIN', fitness_mean:0.612,
  fitness_variance:0.014, hd_equivalent:0.118, stagnation_rate:0,
  window_size:10, trend:'rising', constitutional_factor_mean:0.94,
})
const tool = {api_name:'GitHub',endpoint_url:'https://api.github.com',capabilities:['read'],tier_required:'explorer'}
const live = (s=status(), c=calibration(), t={tools:[tool]}) => toConsoleSnapshot(s,c,t)

test('valid provider evidence yields live with actual values', () => {
  const x=live(); assert.equal(x.source,'live'); assert.equal(x.status.total_agents,39)
  assert.equal(x.tools.length,1)
})
test('missing status remains UNKNOWN, not success', () => {
  const x=toConsoleSnapshot(undefined,calibration(),{tools:[tool]}); assert.equal(x.source,'unknown')
  assert.equal(x.status,null); assert.equal(x.calibration,null); assert.equal(x.tools.length,0)
  assert.equal(x.checks.length,1); assert.equal(x.checks[0].ok,false)
})
test('missing calibration is UNKNOWN', () => assert.equal(toConsoleSnapshot(status(),undefined,{tools:[tool]}).source,'unknown'))
test('malformed JSON status is UNKNOWN', () => assert.equal(live({},calibration()).source,'unknown'))
test('boolean string cannot spoof chain health', () => assert.equal(live({...status(),chain_valid:'true'}).source,'unknown'))
test('NaN calibration is UNKNOWN', () => assert.equal(live(status(),{...calibration(),fitness_mean:NaN}).source,'unknown'))
test('Infinity calibration is UNKNOWN', () => assert.equal(live(status(),{...calibration(),stagnation_rate:Infinity}).source,'unknown'))
test('negative agent count is UNKNOWN', () => assert.equal(live({...status(),total_agents:-1}).source,'unknown'))
test('available=false remains observed, with a failing availability check', () => {
 const x=live({...status(),available:false}); assert.equal(x.source,'live')
 assert.equal(x.checks.find(c=>c.label.startsWith('Platform availability')).ok,false)
})
test('chain self-report is not described as independently verified', () => {
 const x=live(); assert.match(x.checks.find(c=>c.label.startsWith('Hash chain')).reason,/independent replay not established/)
})
test('missing tools are UNKNOWN, with no invented tool list', () => {
 const x=toConsoleSnapshot(status(),calibration(),undefined); assert.equal(x.source,'live')
 assert.deepEqual(x.tools,[]); assert.match(x.reason,/UNKNOWN/)
})
test('malformed tools cannot pass through', () => {
 const x=live(status(),calibration(),{tools:[{...tool,capabilities:3}]}); assert.equal(x.source,'live')
 assert.deepEqual(x.tools,[])
})
test('schema drift in contract is observed but not silently approved', () => {
 const x=live({...status(),contract_version:'2.0.0'}); assert.equal(x.source,'live')
 assert.equal(x.checks.find(c=>c.label==='Contract version').ok,false)
})
test('unknown snapshot contains no fabricated status', () => {
 const x=unknownSnapshot('timeout'); assert.equal(x.source,'unknown')
 assert.equal(x.status,null); assert.equal(x.calibration,null)
})
test('validators reject primitive and array input', () => {
 assert.equal(isPlatformStatus([]),false); assert.equal(isCalibrationStatus('fine'),false)
})
