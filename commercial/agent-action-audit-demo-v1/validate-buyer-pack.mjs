import { readFileSync } from 'node:fs'
import { createHash } from 'node:crypto'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

const here=dirname(fileURLToPath(import.meta.url))
const manifestPath=resolve(here,'BUYER_PACK_MANIFEST_V1.json')
const manifestBytes=readFileSync(manifestPath)
const manifest=JSON.parse(manifestBytes.toString('utf8'))
const sidecar=readFileSync(resolve(here,'BUYER_PACK_MANIFEST_V1.sha256'),'utf8').trim()

function fail(message){
  process.stderr.write(`BUYER_PACK_VALIDATION_FAILED: ${message}\n`)
  process.exit(1)
}
function gitBlobSha1(bytes){
  return createHash('sha1')
    .update(`blob ${bytes.length}\0`)
    .update(bytes)
    .digest('hex')
}
function text(name){ return readFileSync(resolve(here,name),'utf8') }

if(manifest.schema!=='AEGIS_AGENT_ACTION_AUDIT_BUYER_PACK_MANIFEST_V1') fail('schema')
if(typeof manifest.content_source_head!=='string'||!/^[0-9a-f]{40}$/.test(manifest.content_source_head)) fail('content_source_head')
if('source_head' in manifest) fail('ambiguous source_head field forbidden')
const manifestSha256=createHash('sha256').update(manifestBytes).digest('hex')
if(sidecar!==`${manifestSha256}  BUYER_PACK_MANIFEST_V1.json`) fail('manifest sha256 sidecar drift')
if(manifest.offer?.price_minor_units!==300000||manifest.offer?.currency!=='USD') fail('price manifest drift')
if(manifest.offer?.scope!=='one tool-using workflow') fail('scope manifest drift')
if(manifest.authority_effect!=='NONE') fail('authority effect')
if(manifest.send_boundary?.external_message_authority!=='NOT_GRANTED') fail('external message authority')
if(manifest.send_boundary?.legal_commitment_authority!=='NOT_GRANTED') fail('legal authority')
if(manifest.send_boundary?.financial_authority!=='NOT_GRANTED') fail('financial authority')
if(manifest.send_boundary?.exact_pack_binding_required!==true) fail('exact pack binding')

for(const [key,value] of Object.entries(manifest.evidence_boundary??{})){
  if(value!==false) fail(`evidence boundary promoted: ${key}`)
}

for(const entry of manifest.files??[]){
  const prefix='commercial/agent-action-audit-demo-v1/'
  if(typeof entry.path!=='string'||!entry.path.startsWith(prefix)) fail('manifest path scope')
  const local=entry.path.slice(prefix.length)
  const bytes=readFileSync(resolve(here,local))
  const actual=gitBlobSha1(bytes)
  if(actual!==entry.blob_sha) fail(`blob drift: ${local}: ${actual} != ${entry.blob_sha}`)
}

const landing=text('LANDING.md')
const faq=text('FAQ.md')
const due=text('ENTERPRISE_DUE_DILIGENCE.md')
const worksheet=text('PILOT_SCOPE_WORKSHEET.md')
const findings=text('SAMPLE_FINDINGS.md')

if(!landing.includes('Price: USD 3,000 fixed fee')) fail('landing price')
if(!landing.includes('Scope: one tool-using workflow')) fail('landing scope')
if(!landing.includes('Do not send credentials, private keys, customer records, or production secrets')) fail('landing secret boundary')
if(!faq.includes('USD 3,000 fixed fee for one agreed tool-using workflow')) fail('faq price/scope')
if(!faq.includes('not certification or a platform-wide safety guarantee')) fail('faq certification boundary')
if(!due.includes('It is not a certification, legal opinion, compliance attestation')) fail('due diligence claim boundary')
if(!due.includes('Production access is not required for initial scoping')) fail('production access boundary')
if(!due.includes('Do not send credentials, API keys, private keys, customer records, access tokens, production secrets')) fail('due diligence secret boundary')
if(!worksheet.includes('Status: NON-CONTRACTUAL TECHNICAL WORKSHEET')) fail('worksheet contractual boundary')
if(!worksheet.includes('Payment observed:')) fail('payment stage')
if(!worksheet.includes('Audit actually started:')) fail('audit-start stage')
for(const state of ['DEMONSTRATED_FAIL_CLOSED','DEMONSTRATED_FAIL_OPEN','NOT_VERIFIED']){
  if(!findings.includes(state)) fail(`missing finding state: ${state}`)
}

process.stdout.write(JSON.stringify({
  schema:'AEGIS_AGENT_ACTION_AUDIT_BUYER_PACK_VALIDATION_V1',
  status:'PASS',
  content_source_head:manifest.content_source_head,
  manifest_sha256:manifestSha256,
  file_count:manifest.files.length,
  price_minor_units:manifest.offer.price_minor_units,
  currency:manifest.offer.currency,
  external_message_authority:'NOT_GRANTED',
  legal_commitment_authority:'NOT_GRANTED',
  financial_authority:'NOT_GRANTED',
  authority_effect:'NONE',
},null,2)+'\n')
