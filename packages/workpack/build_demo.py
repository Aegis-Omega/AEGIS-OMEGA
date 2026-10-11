#!/usr/bin/env python3
"""Generate deterministic, entirely synthetic six-domain workpack fixtures."""
import copy
import csv
import hashlib
import json
from pathlib import Path
from aegis_workpack.protocol import canonical, verify

OUT=Path(__file__).parent/'examples'
CASES={
 'code':('implementation.py',b'def evaluate(value):\n    return value * 2\n','text_contains',{'value':'def evaluate('}),
 'science':('research.json',b'{"method":"simulated","observations":12,"claim":"unverified"}\n','json_keys',{'keys':['method','observations','claim']}),
 'data':('sample.csv',b'id,value\n1,0.3\n2,0.7\n','csv_columns',{'columns':['id','value'],'min_rows':2}),
 'operations':('checklist.txt',b'Backup exported: UNVERIFIED\nRollback plan: described\n','text_contains',{'value':'Rollback plan:'}),
 'design':('design.json',b'{"screens":["Home","Detail"],"contrast_check":"pending"}\n','json_keys',{'keys':['screens','contrast_check']}),
 'writing':('draft.md',b'# Product overview\nEvidence-bound agent delivery.\n','text_contains',{'value':'Evidence-bound'}),
}
summary=[]
for domain,(name,content,kind,properties) in CASES.items():
    for tampered in (False,True):
        label=domain+('-tampered' if tampered else '-baseline')
        dest=OUT/label
        dest.mkdir(parents=True,exist_ok=True)
        (dest/name).write_bytes(content + (b'\nTAMPERED' if tampered else b''))
        manifest={'schema':'aegis.workpack.v1','task_id':'pilot-'+label,'domain':domain,
                  'authority':'read_only','objective':f'Create a structurally checkable synthetic {domain} fixture',
                  'producer':{'agent':'fixture-generator-not-a-real-agent'},
                  'artifacts':[{'path':name,'sha256':hashlib.sha256(content).hexdigest()}],
                  'checks':[{'id':'A1','kind':'sha256','artifact':name},
                            {'id':'A2','kind':kind,'artifact':name,**properties}]}
        (dest/'manifest.json').write_bytes(json.dumps(manifest,indent=2,ensure_ascii=False).encode()+b'\n')
        receipt=verify(dest,manifest)
        (dest/'receipt.json').write_text(json.dumps(receipt,indent=2,ensure_ascii=False)+'\n')
        result=receipt['disposition']
        assert result == ('NOT_ADMITTED' if tampered else 'LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED')
        summary.append({'id':label,'domain':domain,'result':result,'artifact_integrity':receipt['artifact_integrity'],
                        'quality':receipt['domain_quality'],'synthetic':True})
(OUT/'synthetic_benchmark.json').write_text(json.dumps({'schema':'aegis.workpack.synthetic-benchmark.v1',
 'warning':'Fixture-generated, not a cross-model or real-world success benchmark.',
 'cases':summary,'valid_fixtures':6,'rejected_tampering':6},indent=2)+'\n')
print('generated',len(summary),'synthetic fixtures',sum(x['result']=='NOT_ADMITTED' for x in summary),'rejected')
