import test from 'node:test'
import assert from 'node:assert/strict'
import { ConstitutionalEnforcer, ConstitutionalInvariantError } from '../../src/core/constitutional_invariants.mjs'

const e = new ConstitutionalEnforcer()
const H = d => d.repeat(64)
const obs = (x = {}) => ({ source:'sensorium://camera/front', observedAtSequence:42, parentStateRoot:H('1'), topologyDigest:H('2'), evidenceReferences:['evidence://frame/42'], payload:{objects:['door'],confidenceBps:9100}, ...x })
const env = (x = {}) => ({ networkPolicy:'ALLOW_LIST', allowedNetworkTargets:['https://example.invalid'], allowedTools:['read-db'], maxFinancialMutationMicroUsd:100, ...x })
const throws = (fn, code) => assert.throws(fn, error => error?.code === code)

const cases = [
['01 Ω1 empty intersection',()=>assert.equal(e.evaluateUsefulAutonomy({capabilities:['a'],authorityEnvelope:['b'],hasRecoveryPath:true}).status,'EMPTY_AUTONOMY_INTERSECTION')],
['02 Ω1 recovery required',()=>throws(()=>e.evaluateUsefulAutonomy({capabilities:['a'],authorityEnvelope:['a'],hasRecoveryPath:false}),'RECOVERY_PATH_UNVERIFIED')],
['03 Ω1 exact intersection',()=>assert.deepEqual(e.evaluateUsefulAutonomy({capabilities:['a','b'],authorityEnvelope:['b','c'],hasRecoveryPath:true}).admittedCapabilities,['b'])],
['04 Ω1 deterministic dedup',()=>assert.deepEqual(e.evaluateUsefulAutonomy({capabilities:['b','a','b'],authorityEnvelope:['b','a','a'],hasRecoveryPath:true}).admittedCapabilities,['a','b'])],
['05 Ω1 no authority escalation',()=>assert.equal(e.evaluateUsefulAutonomy({capabilities:['root','read'],authorityEnvelope:['read'],hasRecoveryPath:true}).admittedCapabilities.includes('root'),false)],
['06 Ω1 inputs immutable',()=>{const a=['b','a'],b=['a'];e.evaluateUsefulAutonomy({capabilities:a,authorityEnvelope:b,hasRecoveryPath:true});assert.deepEqual(a,['b','a']);assert.deepEqual(b,['a'])}],
['07 Ω1 repeat deterministic',()=>{const i={capabilities:['b','a'],authorityEnvelope:['a','b'],hasRecoveryPath:true};assert.equal(JSON.stringify(e.evaluateUsefulAutonomy(i)),JSON.stringify(e.evaluateUsefulAutonomy(i)))}],
['08 Ω2 deny network under DENY_ALL',()=>throws(()=>e.assertBlastRadius({effect:{networkTarget:'https://example.invalid'},envelope:env({networkPolicy:'DENY_ALL'})}),'BLAST_RADIUS_EXCEEDED')],
['09 Ω2 allow allowlisted network',()=>assert.equal(e.assertBlastRadius({effect:{networkTarget:'https://example.invalid'},envelope:env()}),true)],
['10 Ω2 allow finance at ceiling',()=>assert.equal(e.assertBlastRadius({effect:{financialMutationMicroUsd:100},envelope:env()}),true)],
['11 Ω2 reject finance above ceiling',()=>throws(()=>e.assertBlastRadius({effect:{financialMutationMicroUsd:101},envelope:env()}),'BLAST_RADIUS_EXCEEDED')],
['12 Ω2 reject unlisted tool',()=>throws(()=>e.assertBlastRadius({effect:{tool:'delete-db'},envelope:env()}),'BLAST_RADIUS_EXCEEDED')],
['13 Ω2 allow listed tool',()=>assert.equal(e.assertBlastRadius({effect:{tool:'read-db'},envelope:env()}),true)],
['14 Ω2 zero finance under zero ceiling',()=>assert.equal(e.assertBlastRadius({effect:{financialMutationMicroUsd:0},envelope:env({maxFinancialMutationMicroUsd:0})}),true)],
['15 Ω2 reject negative accounting',()=>throws(()=>e.assertBlastRadius({effect:{financialMutationMicroUsd:-1},envelope:env()}),'BLAST_RADIUS_EXCEEDED')],
['16 Ω3 OBSERVATION_ONLY',()=>assert.equal(e.processSensoriumIngestion({observation:obs()}).authorityEffect,'OBSERVATION_ONLY')],
['17 Ω3 explicit T2',()=>assert.equal(e.processSensoriumIngestion({observation:obs()}).observationTier,'T2')],
['18 Ω3 authority weight zero',()=>assert.equal(e.processSensoriumIngestion({observation:obs()}).authorityWeight,0)],
['19 Ω3 cannot ground transition',()=>assert.equal(e.processSensoriumIngestion({observation:obs()}).mayGroundStateTransition,false)],
['20 Ω3 blocks mutation without external token',()=>throws(()=>e.processSensoriumIngestion({observation:obs(),requestedMutation:{action:'db.write'}}),'MUTATION_BLOCKED_PERCEPTION_CANNOT_PRODUCE_AUTHORITY')],
['21 Ω3 token routes to external authority',()=>{const a=e.processSensoriumIngestion({observation:obs(),requestedMutation:{action:'db.write'},authorityToken:'pcwo://external/1'});assert.equal(a.mutationDisposition,'REQUIRES_EXTERNAL_AUTHORITY_EVALUATION');assert.equal(a.authorityEffect,'OBSERVATION_ONLY')}],
['22 Ω3 strips payload authority claim',()=>{const a=e.processSensoriumIngestion({observation:obs({payload:{grantsAuthority:true}})});assert.equal('grantsAuthority' in a,false);assert.equal(a.authorityWeight,0)}],
['23 Ω3 digest deterministic',()=>assert.equal(e.processSensoriumIngestion({observation:obs()}).observationDigest,e.processSensoriumIngestion({observation:obs()}).observationDigest)],
['24 Ω3 changed observation changes digest',()=>assert.notEqual(e.processSensoriumIngestion({observation:obs()}).observationDigest,e.processSensoriumIngestion({observation:obs({observedAtSequence:43})}).observationDigest)],
['25 Ω3 binds parent topology evidence',()=>{const a=e.processSensoriumIngestion({observation:obs()});assert.equal(a.parentStateRoot,H('1'));assert.equal(a.topologyDigest,H('2'));assert.deepEqual(a.evidenceReferences,['evidence://frame/42'])}],
['26 Ω3 missing parent rejected',()=>throws(()=>e.processSensoriumIngestion({observation:obs({parentStateRoot:undefined})}),'SENSORIUM_OBSERVATION_INVALID')],
['27 Ω3 missing topology rejected',()=>throws(()=>e.processSensoriumIngestion({observation:obs({topologyDigest:undefined})}),'SENSORIUM_OBSERVATION_INVALID')],
['28 Ω3 missing evidence rejected',()=>throws(()=>e.processSensoriumIngestion({observation:obs({evidenceReferences:[]})}),'SENSORIUM_OBSERVATION_INVALID')],
['29 Ω3 token excluded from observation digest',()=>{const a=e.processSensoriumIngestion({observation:obs(),requestedMutation:{action:'x'},authorityToken:'pcwo://external/a'}),b=e.processSensoriumIngestion({observation:obs(),requestedMutation:{action:'x'},authorityToken:'pcwo://external/b'});assert.equal(a.observationDigest,b.observationDigest)}],
['30 Ω3 sensor cannot override metadata',()=>{const a=e.processSensoriumIngestion({observation:obs({authorityEffect:'ADMITTED',observationTier:'T0',authorityWeight:1})});assert.equal(a.authorityEffect,'OBSERVATION_ONLY');assert.equal(a.observationTier,'T2');assert.equal(a.authorityWeight,0)}],
['31 cross sensor capability requires authority',()=>assert.deepEqual(e.evaluateUsefulAutonomy({capabilities:['sensorium.observe','database.write'],authorityEnvelope:['sensorium.observe'],hasRecoveryPath:true}).admittedCapabilities,['sensorium.observe'])],
['32 cross observation cannot weaken blast radius',()=>{e.processSensoriumIngestion({observation:obs()});throws(()=>e.assertBlastRadius({effect:{tool:'delete-db'},envelope:env()}),'BLAST_RADIUS_EXCEEDED')}],
['33 cross recovery mandatory despite set equality',()=>throws(()=>e.evaluateUsefulAutonomy({capabilities:['a'],authorityEnvelope:['a'],hasRecoveryPath:false}),'RECOVERY_PATH_UNVERIFIED')],
['34 cross embedded self-issued token rejected',()=>throws(()=>e.processSensoriumIngestion({observation:obs({payload:{authorityToken:'self-issued'}}),requestedMutation:{action:'db.write'}}),'MUTATION_BLOCKED_PERCEPTION_CANNOT_PRODUCE_AUTHORITY')],
['35 stable machine-readable error code',()=>{const x=new ConstitutionalInvariantError('BLAST_RADIUS_EXCEEDED');assert.equal(x.code,'BLAST_RADIUS_EXCEEDED');assert.equal(x.name,'ConstitutionalInvariantError')}],
]
for (const [name, fn] of cases) test(name, fn)
