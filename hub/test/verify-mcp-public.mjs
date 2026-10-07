/** Exact-source replay for the static evidence page. No deployment or authority grant. */
import { spawnSync } from 'node:child_process'
import { readFileSync, writeFileSync, mkdirSync, readdirSync } from 'node:fs'
import { createHash } from 'node:crypto'
const hash = bytes => createHash('sha256').update(bytes).digest('hex')
function git(...args) {
  const p = spawnSync('git', args, {encoding:'utf8'})
  if (p.status !== 0) throw new Error('Git source observation unavailable')
  return p.stdout.trim()
}
const source = git('rev-parse','HEAD'), statusBefore = git('status','--porcelain','--untracked-files=no')
mkdirSync('evidence/mcp-public', {recursive:true})
const paths = ['public/labs/mcp','test','docs'].flatMap(dir=> readdirSync(dir,{recursive:true,withFileTypes:true})
  .filter(p=>p.isFile() && (dir==='public/labs/mcp' || /mcp-public|mcp-evidence|mcp-routing/.test(p.name)))
  .map(p=>`${p.parentPath}/${p.name}`))
paths.push('vercel.json','../vercel.json','../hook-generator/vercel.json','../platform-picker/vercel.json')
const manifest = [...new Set(paths)].sort().map(path=>({path,sha256:hash(readFileSync(path))}))
const stages = []
for (const [name,args] of [['unit-routing',['--test','test/mcp-evidence.test.mjs','test/mcp-routing.test.mjs']],
  ['browser',['test/mcp-public-browser.mjs']]]) {
  const p = spawnSync(process.execPath,args,{encoding:'utf8',timeout:120000,maxBuffer:4*1024*1024})
  const log=(p.stdout??'')+(p.stderr??'')+(p.error?String(p.error):'')
  writeFileSync(`evidence/mcp-public/${name}.log`,log)
  stages.push({name,command:[process.execPath,...args],status:p.status===0?'PASS':'FAIL',exit_code:p.status,log_sha256:hash(log)})
  console.log(`${name}: ${p.status===0?'PASS':'FAIL'}`)
}
const unchanged = statusBefore==='' && git('status','--porcelain','--untracked-files=no')==='' && manifest.every(f=>hash(readFileSync(f.path))===f.sha256)
const receipt = {schema_version:'1.0.0',source_commit:source,recorded_mcp_source:'897fa55556a639a04a67d25481b7a432af007d04',
 observed_at:new Date().toISOString(),runtime:{node:process.version,platform:process.platform},
 verdict:unchanged && stages.every(s=>s.status==='PASS')?'PASS':'FAIL',source_unchanged:unchanged,stages,source_manifest:manifest,
 scope:'Static evidence-page tests and actual local Chromium; original MCP execution is historical, not repeated by this page',
 deployment:'NOT_ESTABLISHED_BY_THIS_RECEIPT',admission:'NOT_ADMITTED',
 artifacts:readdirSync('evidence/mcp-public').filter(n=>!['receipt.json','REPORT.md'].includes(n)).sort()
 .map(path=>({path,sha256:hash(readFileSync(`evidence/mcp-public/${path}`))}))}
writeFileSync('evidence/mcp-public/receipt.json',JSON.stringify(receipt,null,2)+'\n')
writeFileSync('evidence/mcp-public/REPORT.md',`# Static MCP evidence page\n\n${receipt.verdict}\n\nSource: ${source}\n\n`+
 stages.map(s=>`${s.name}: ${s.status}; exit ${s.exit_code}`).join('\n\n')+`\n\n${receipt.scope}\n\nNo production deployment or authority admission is established by this replay.\n`)
if(receipt.verdict!=='PASS')process.exitCode=1
