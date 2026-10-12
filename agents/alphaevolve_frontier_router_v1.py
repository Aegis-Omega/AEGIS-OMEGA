"""AEGIS Ω #758 — deterministic self-discovered research queue over entire corpus.

All unique contents are assigned to a frontier cohort. Qualified evaluators are
marked executable; unsupported domains explicitly request an evaluator rather
than being silently ignored. NO scientific promotion or untrusted code execution.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import sqlite3
from collections import Counter,defaultdict
from pathlib import Path

SCHEMA='AEGIS_ALPHAEVOLVE_FRONTIER_V1'


def descriptor(fmt: str, category:str, lens:str)->tuple[str,str,str]:
    if lens=='CSV_TIME_SERIES_EVOLUTION':
        return ('NUMERIC_TIME_SERIES','EXECUTED_OBSERVATIONAL','DEVELOP_HYPOTHESIS_FROM_TIME_AXIS')
    if lens=='CSV_TABULAR_EVOLUTION':
        return ('NUMERIC_TABULAR','EXECUTED_OBSERVATIONAL','DEVELOP_CROSS_ROW_GENERALIZATION')
    if category=='FORMAL_SOURCE' or fmt in ('.lean','.v'):
        return ('FORMAL_VERIFICATION','EVALUATOR_REQUIRED','PINNED_KERNEL_COMPILE_AND_EXACT_HEAD')
    if fmt=='.npz':
        return ('QUANTUM_TENSOR','EVALUATOR_REQUIRED','DENSITY_MATRIX_PHYSICAL_INVARIANTS')
    if fmt in ('.csv','.json','.jsonl','.parquet','.xlsx','.sqlite','.h5','.hdf5','.pdb','.fasta','.fastq'):
        return ('STRUCTURED_RESEARCH','EVALUATOR_REQUIRED','SCHEMA_AND_INDEPENDENT_FALSIFIER')
    if fmt in ('.jpeg','.jpg','.png','.svg','.webp','.pdf'):
        return ('MULTIMODAL_EVIDENCE','EVALUATOR_REQUIRED','CONTENT_SEMANTICS_AND_GROUNDED_BENCHMARK')
    if category=='SOURCE_CODE' or fmt in ('.py','.ts','.js','.mjs','.rs','.c','.cpp','.cjs'):
        return ('SOFTWARE_SYNTHESIS','EVALUATOR_REQUIRED','SAFE_RUNTIME_TEST_HARNESS')
    if category=='DEPENDENCY_OR_GENERATED':
        return ('DEPENDENCY_BINARY','LOSSLESS_EVOLVED','REPRODUCIBLE_PACKAGING_ONLY')
    return ('GENERAL_CORPUS','LOSSLESS_EVOLVED','DOMAIN_SPECIFIC_OBJECTIVE_REQUIRED')


def router(db:Path)->dict:
    con=sqlite3.connect(f'file:{db.resolve()}?mode=ro',uri=True)
    try:
        source_count=con.execute('SELECT COUNT(*) FROM assets').fetchone()[0]
        cover_count=con.execute('SELECT COUNT(*) FROM coverage').fetchone()[0]
        pending=con.execute("SELECT COUNT(*) FROM coverage WHERE state IN ('AWAITING_RUN_BUDGET','EXPERIMENT_BLOCKED')").fetchone()[0]
        if pending:raise ValueError('CORPUS_INCOMPLETE_OR_BLOCKED')
        if source_count==0:raise ValueError('NO_EVOLVED_ASSETS')
        families={}
        total=0
        for sha,fmt,category,lens,byte_count in con.execute('''SELECT digest,format,category,science_state,bytes
                                                            FROM assets ORDER BY digest'''):
            domain,status,gap=descriptor(fmt,category,lens)
            key=f'{domain}/{status}/{fmt or "UNKNOWN"}'
            if key not in families:
                families[key]={'domain':domain,'evaluation_status':status,'next_evaluator':gap,
                    'extension':fmt or 'UNKNOWN','asset_count':0,'bytes':0,
                    'example_digests':[],'digest_accumulator':hashlib.sha256()}
            g=families[key];g['asset_count']+=1;g['bytes']+=byte_count;total+=1
            # Stable membership commitment; deterministic, full 64-digit SHA path.
            g['digest_accumulator'].update((sha+'\n').encode('ascii'))
            if len(g['example_digests'])<3:g['example_digests'].append(sha)
        if total!=source_count:raise ValueError('FRONTIER_LOST_ASSETS')
        items=[]
        for key,g in sorted(families.items()):
            g['membership_digest']=g.pop('digest_accumulator').hexdigest()
            g['cohort_key']=key
            items.append(g)
        counters=dict(Counter(x['evaluation_status'] for x in items))
        assets_by_state=dict(Counter({k:sum(x['asset_count'] for x in items if x['evaluation_status']==k)
                                       for k in ('EXECUTED_OBSERVATIONAL','EVALUATOR_REQUIRED','LOSSLESS_EVOLVED')}))
        return {'schema':SCHEMA,'unique_assets_assigned':total,'indexed_objects_covered':cover_count,
            'cohorts':items,'cohort_count':len(items),'cohorts_by_status':counters,
            'assets_by_status':assets_by_state,
            'source_data_execution':'EVALUATORS_ONLY_WHERE_SUPPORTED',
            'unsupported_inputs':'EXPLICIT_EVALUATOR_REQUIRED',
            'scientific_admission':'DENIED','source_mutated':False}
    finally:con.close()


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    args=p.parse_args()
    d=router(args.db);args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in d.items() if k!='cohorts'},indent=2))

if __name__=='__main__':main()
