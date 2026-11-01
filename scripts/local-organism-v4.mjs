#!/usr/bin/env node
// AEGIS Ω local-only organism runtime adapter. No deployment, no external calls.
// Requires the EXISTING native evidence-cycle.mjs, evidence-ledger.mjs and chain.mjs
// from AEGIS PR #560. No fallback mocks and no automatic grants.
import {readFileSync} from 'node:fs'
import {resolve,join,dirname} from 'node:path'
import {fileURLToPath} from 'node:url'
import {tmpdir} from 'node:os'
import {runLocalOrganismStep} from '../.claude/metacog/organism-coordinator.mjs'
import {runEvidenceCycle} from '../.claude/metacog/evidence-cycle.mjs'
import {verifyReceipt,certifyLedger} from '../.claude/metacog/evidence-ledger.mjs'

const root=resolve(dirname(fileURLToPath(import.meta.url)),'..')
try{
 const [snapshotArg,planArg]=process.argv.slice(2)
 if(!snapshotArg||!planArg) throw new Error('USAGE: local-organism-v4.mjs <snapshot.json> <plan.json>')
 const plan=JSON.parse(readFileSync(resolve(planArg),'utf8'))
 if(!plan||!Array.isArray(plan.candidates)||!plan.sourcePaths)throw new Error('PLAN_CANDIDATES_AND_SOURCE_PATHS_REQUIRED')
 const env={...process.env}
 const result=runLocalOrganismStep({
  snapshotPath:resolve(snapshotArg),
  receiptPath:env.AEGIS_EVIDENCE_RECEIPT||join(root,'.claude/metacog/evidence-receipt.tmp'),
  ledgerPath:env.AEGIS_EVIDENCE_LEDGER||join(root,'.claude/metacog/evidence-transitions.log'),
  chainPath:join(root,'.claude/metacog/chain.mjs'),
  historyPath:env.AEGIS_ORGANISM_HISTORY||join(root,'.claude/metacog/organism-history.json'),
  sandbox:env.AEGIS_ORGANISM_SANDBOX||join(tmpdir(),'aegis-organism-v4-proposals'),
  candidates:plan.candidates,operator_budget:plan.operator_budget??0,
  sourcePaths:plan.sourcePaths,initialState:plan.initial_state??{},
  allowInitialize:env.AEGIS_ORGANISM_INIT==='1',env,
  evidenceCycle:runEvidenceCycle,receiptVerifier:verifyReceipt,
  ledgerVerifier:entries=>certifyLedger(entries).is_valid===true,
 })
 process.stdout.write(JSON.stringify(result,null,2)+'\n')
}catch(e){console.error('AEGIS_ORGANISM_HOLD '+String(e?.message??e));process.exitCode=2}
