"""AEGIS Ω #758 — bounded observational evolution of headerless bioreactor series.

Discovers previously excluded yeast bioreactor CSVs from the actual read-only
corpus catalog, including both ';' delimiters and decimal-comma measurements.
Program candidates forecast next measured value causally. Chronological
validation selects the program; disjoint later holdout is read only once.

The source does not establish independent biological replicates. Improvement in
prediction loss is observational and NEVER grants scientific or code admission.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import math
import sqlite3
from pathlib import Path
import numpy as np

SCHEMA="AEGIS_ALPHAEVOLVE_BIOREACTOR_OBSERVATIONAL_V1"
MAX_CSV_BYTES=5_000_000
MAX_ROWS=250_000
PROGRAMS=("HOLD","MEAN_2","MEAN_4","MEAN_8","MEAN_16","MEAN_32",
          "TREND_2_QUARTER","TREND_4_HALF","TREND_8_QUARTER",
          "EMA_0.25","EMA_0.5","EMA_0.75")


def _sha256(p:Path)->str:
    h=hashlib.sha256()
    with p.open('rb') as f:
        for x in iter(lambda:f.read(1<<20),b''):h.update(x)
    return h.hexdigest()


def parse_unlabeled_series(path:Path)->tuple[np.ndarray,np.ndarray,dict]:
    """Recognize source-specific CSV grammar without guessing an absent header."""
    if not path.is_file() or path.is_symlink() or path.stat().st_size>MAX_CSV_BYTES:
        raise ValueError('UNSUPPORTED_SOURCE_SIZE_OR_SYMLINK')
    with path.open('r',encoding='utf-8-sig',newline='') as f:
        peek=f.readline()
        if not peek:raise ValueError('EMPTY_SOURCE')
        delim=';' if ';' in peek else ','
        decimal_comma=delim==';' and ',' in peek
        f.seek(0)
        rows=[]
        for i,row in enumerate(csv.reader(f,delimiter=delim,strict=True)):
            if i>=MAX_ROWS:raise ValueError('TOO_MANY_ROWS')
            if len(row)<2 or len(row)>12:raise ValueError('INVALID_ROW_WIDTH')
            try:
                numeric=[float(x.replace(',','.') if decimal_comma else x) for x in row]
            except ValueError as e:raise ValueError('NONNUMERIC_UNLABELED_DATA') from e
            if not all(math.isfinite(v) for v in numeric):raise ValueError('NONFINITE_INPUT')
            if rows and len(numeric)!=len(rows[0]):raise ValueError('INCONSISTENT_WIDTH')
            rows.append(numeric)
    if len(rows)<160:raise ValueError('INSUFFICIENT_SERIES')
    a=np.asarray(rows,dtype=np.float64)
    t=a[:,0];y=a[:,1:]
    if not np.all(np.diff(t)>0):raise ValueError('INVALID_TIME_AXIS')
    if not np.all(np.ptp(y,axis=0)>0):raise ValueError('CONSTANT_SENSOR')
    return t,y,{'rows':len(t),'measured_channels':y.shape[1],
                 'delimiter':delim,'decimal_comma':decimal_comma,
                 'no_header':True,'time_axis_observed_not_target':True}


def candidate_predict(y:np.ndarray,program:str)->np.ndarray:
    """At row i a predictor uses only y[0:i]; no future samples."""
    if program not in PROGRAMS:raise ValueError('UNKNOWN_PROGRAM')
    a=np.asarray(y,dtype=np.float64)
    n=len(a)
    p=np.full(n,np.nan,dtype=np.float64)
    if program=='HOLD':p[1:]=a[:-1];return p
    if program.startswith('MEAN_'):
        k=int(program.split('_')[1]);c=np.r_[0.,np.cumsum(a)]
        idx=np.arange(k,n)
        p[idx]=(c[idx]-c[idx-k])/k
        return p
    if program.startswith('TREND_'):
        _,k,factor=program.split('_'); k=int(k);gain={'QUARTER':.25,'HALF':.5}[factor]
        idx=np.arange(k+1,n)
        p[idx]=a[idx-1]+gain*(a[idx-1]-a[idx-1-k])/k
        return p
    if program.startswith('EMA_'):
        alpha=float(program.split('_')[1]);level=a[0]
        for i in range(1,n):
            p[i]=level
            level=alpha*a[i]+(1-alpha)*level
        return p
    raise ValueError('UNKNOWN_PROGRAM')


def _mse(truth:np.ndarray,pred:np.ndarray,lo:int,hi:int)->float:
    diff=truth[lo:hi]-pred[lo:hi]
    if len(diff)==0 or not np.all(np.isfinite(diff)):raise ValueError('NONFINITE_PREDICTION')
    return float(np.mean(np.square(diff)))


def evolve(path:Path,expected_sha:str)->dict:
    if _sha256(path)!=expected_sha:raise ValueError('SOURCE_HASH_MISMATCH')
    t,matrix,meta=parse_unlabeled_series(path)
    n=len(t);valid_lo=int(n*.6);test_lo=int(n*.8)
    results=[]
    for channel in range(matrix.shape[1]):
        y=matrix[:,channel]
        # Search evaluates only validation; test is observed ONCE for winner.
        validation={}
        for program in PROGRAMS:
            validation[program]=_mse(y,candidate_predict(y,program),valid_lo,test_lo)
        best=min(validation,key=lambda x:(validation[x],x))
        baseline=candidate_predict(y,'HOLD')
        champion=candidate_predict(y,best)
        loss0=_mse(y,baseline,test_lo,n); loss1=_mse(y,champion,test_lo,n)
        results.append({'channel':channel+1,'candidate_count':len(PROGRAMS),
            'winner':best,'validation_mse':validation[best],
            'test_baseline_mse':loss0,'test_candidate_mse':loss1,
            'test_improvement':loss0-loss1,
            'relative_test_improvement':0. if loss0==0 else (loss0-loss1)/loss0,
            'positive_holdout_gain':loss1<loss0})
    return {'schema':SCHEMA,'source_sha256':expected_sha, 'source_name':path.name,
        'source_format':meta,'split':{'train_end':valid_lo,'validation_end':test_lo,'test_end':n},
        'chronological_holdout':'TEST_ONLY_AFTER_VALIDATION_SELECTION',
        'observational_results':results,
        'independent_biological_replication':'NOT_ESTABLISHED',
        'evidence_level':'TEMPORAL_PREDICTION_NOT_BIOLOGICAL_CAUSATION',
        'admission':'DENIED','source_mutated':False}


def run_catalog(catalog:Path,root:Path)->dict:
    """Catalog-discovers all eligible bioreactor sources. Never executes their code."""
    if not catalog.is_file():raise ValueError('CATALOG_MISSING')
    con=sqlite3.connect(f'file:{catalog.resolve()}?mode=ro',uri=True)
    try:
        entries=con.execute("""SELECT digest,relpath,science_state FROM assets
             WHERE lower(relpath) LIKE '%bioreactor%' AND format='.csv'
             ORDER BY digest""").fetchall()
    finally: con.close()
    out=[];blocked=[]
    for digest,relative,state in entries:
        p=Path(relative)
        if p.is_absolute() or '..' in p.parts or '\\' in relative or not p.parts:
            blocked.append({'digest':digest,'status':'SOURCE_PATH_BLOCKED'});continue
        cur=root
        for segment in p.parts:
            cur=cur/segment
            if cur.is_symlink():break
        if cur.is_symlink() or not cur.resolve().is_relative_to(root.resolve()):
            blocked.append({'digest':digest,'status':'SOURCE_PATH_BLOCKED'});continue
        try:out.append(evolve(cur,digest))
        except (ValueError,OSError,csv.Error) as e:
            blocked.append({'digest':digest,'status':'NOT_EVALUATED','reason':str(e)[:120]})
    all_results=[channel for item in out for channel in item['observational_results']]
    return {'schema':'AEGIS_BIOREACTOR_COHORT_REPLAY_V1',
      'discovered':len(entries),'evaluated':len(out),'blocked':blocked,
      'distinct_source_sha256':[x['source_sha256'] for x in out],
      'channels_evaluated':len(all_results),
      'positive_holdout_channels':sum(bool(x['positive_holdout_gain']) for x in all_results),
      'not_independent_p_values':True,'scientific_admission':'DENIED',
      'evaluations':out}


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    report=run_catalog(args.catalog,args.root)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,sort_keys=True,indent=2,allow_nan=False)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='evaluations'},indent=2))

if __name__=='__main__':main()
