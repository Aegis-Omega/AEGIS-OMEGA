"""AEGIS Ω / #758: corpus-wide, fail-closed, non-promoting evolution coverage.

Every indexed *object* is joined to a reviewed outcome; every accessible distinct
blob is included in a bounded, deterministic evolutionary search for its best
round-trip *representation*. This is NOT a claim of scientific discovery.
Source code, formal proof terms, unsafe/executable data are NEVER executed.

Structured CSVs additionally receive a bounded observational forecasting
experiment (three safe predictors); all results remain NOT_ADMITTED.
"""
from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import math
import os
from pathlib import Path
import sqlite3
import statistics
import time
import zlib
from collections import Counter, defaultdict

SCHEMA = "AEGIS_CORPUS_WIDE_EVOLUTION_V1"
MAX_TEXT_PARSE = 2_000_000
MAX_CSV_ROWS = 5000
MAX_COLUMN = 64
MAX_EVALUATIONS_PER_RUN = 100_000
READ_CHUNK = 1 << 20
BINARY_EXTENSIONS = {'.png','.jpeg','.jpg','.pdf','.npz','.zip','.gz','.olean','.vo','.pack','.parquet'}
SENSITIVE_PATH_SEGMENTS = ('/.ssh/','/secrets/','/credentials/','/.env','private.key','.pem','/wallet/','/token/')


def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def json_bytes(o) -> bytes:
    return json.dumps(o, sort_keys=True, separators=(',',':'), ensure_ascii=True,
                      allow_nan=False).encode('ascii')


def validate_source(root: Path, rel: str, declared_sha: str, declared_size: int) -> Path:
    """Never resolve an untrusted relative path outside the mounted data root."""
    if not isinstance(rel,str) or not rel or '\\' in rel or '\x00' in rel:
        raise ValueError('SOURCE_PATH_INVALID')
    p=Path(rel)
    if p.is_absolute() or '..' in p.parts or '.' in p.parts:
        raise ValueError('SOURCE_TRAVERSAL')
    current=root
    for bit in p.parts:
        current=current/bit
        if current.is_symlink():
            raise ValueError('SOURCE_SYMLINK')
    if not current.resolve().is_relative_to(root.resolve()):
        raise ValueError('SOURCE_ESCAPE')
    if not current.is_file() or current.stat().st_size != declared_size:
        raise ValueError('SOURCE_BYTES_OR_SIZE_MISSING')
    if not isinstance(declared_sha,str) or len(declared_sha)!=64:
        raise ValueError('SOURCE_SHA_INVALID')
    return current


def _encoded_length_and_sha(p: Path, level: int) -> tuple[int,str,str]:
    """Stream entire file and check losslessness through independent decompression.

    No decompressed buffers or encoded copies retained in RAM. All bytes tested,
    including multi-GB files. The selected codec can be reproduced from source.
    """
    compressor=zlib.compressobj(level)
    decompressor=zlib.decompressobj()
    original=hashlib.sha256(); reconstructed=hashlib.sha256()
    encoded_bytes=0; decoded_bytes=0; input_bytes=0
    with p.open('rb') as f:
        while True:
            raw=f.read(READ_CHUNK)
            if not raw:break
            input_bytes+=len(raw); original.update(raw)
            enc=compressor.compress(raw)
            if enc:
                encoded_bytes+=len(enc)
                dec=decompressor.decompress(enc)
                reconstructed.update(dec); decoded_bytes+=len(dec)
        tail=compressor.flush()
        encoded_bytes+=len(tail)
        dec=decompressor.decompress(tail)
        reconstructed.update(dec); decoded_bytes+=len(dec)
        dec=decompressor.flush();reconstructed.update(dec);decoded_bytes+=len(dec)
    if not decompressor.eof or decompressor.unused_data or input_bytes != decoded_bytes or original.digest()!=reconstructed.digest():
        raise ValueError('ROUNDTRIP_FAILED')
    return encoded_bytes,original.hexdigest(),reconstructed.hexdigest()


def evolve_representation(p:Path, expected_sha:str, size:int, *, full_budget:int=2_000_000)->dict:
    """All bytes are verified. Two or three *actual* codecs compete per asset."""
    if full_budget < 0:raise ValueError('INVALID_BUDGET')
    trials=[{'candidate':'RAW','bytes':size,'verified':True}]
    for level in ([1,6] if size<=full_budget else [1]):
        n,observed,reconstructed=_encoded_length_and_sha(p,level)
        if observed!=expected_sha or reconstructed!=expected_sha:
            raise ValueError('SOURCE_SHA_MISMATCH')
        trials.append({'candidate':f'ZLIB_{level}','bytes':n,'verified':True})
    champion=min(trials,key=lambda x:(x['bytes'],x['candidate']))
    return {'winner':champion['candidate'],'winner_bytes':champion['bytes'],
            'original_bytes':size,'verified_full_file':True,'trials':trials,
            'representation_gain_bytes':size-champion['bytes']}


def evolve_numeric_csv(p:Path, max_bytes:int=4_000_000)->dict:
    """Read-only 3-program competition on numeric time series; blocked from promotion.

    60% development, 20% validation; *one* 20% temporal test. Adjacent rows are
    correlated, so these are descriptive outcomes, NOT independent claims.
    """
    if p.stat().st_size>max_bytes:
        return {'state':'DATA_LARGE_SEMANTIC_REPLAY_PENDING','reason':'BYTE_BUDGET'}
    raw=p.read_bytes()
    try:
        rdr=csv.reader(io.StringIO(raw.decode('utf-8-sig'),newline=''),strict=True)
        head=next(rdr)
        if len(head)<2 or len(head)>MAX_COLUMN or len(set(head))!=len(head):
            return {'state':'NOT_NUMERIC_TIMESERIES','reason':'COLUMN_SCHEMA'}
        rows=[]
        for idx,row in enumerate(rdr):
            if idx>=MAX_CSV_ROWS:break
            if len(row)!=len(head):return {'state':'NOT_NUMERIC_TIMESERIES','reason':'ROW_WIDTH'}
            rows.append(row)
    except (UnicodeError,csv.Error,StopIteration):
        return {'state':'NOT_NUMERIC_TIMESERIES','reason':'CSV_PARSE'}
    # A sorted parameter sweep or benchmark record is not a time series.
    # Require an explicit monotonic independent time axis before forecasting.
    time_positions=[j for j,name in enumerate(head) if name.lower().strip() in
                    ('time','time_fs','time_ps','time_s','timestamp','elapsed_time','t_fs','t_ps')]
    if not time_positions:
        return {'state':'NOT_NUMERIC_TIMESERIES','reason':'NO_DECLARED_TIME_AXIS'}
    try:
        times=[float(row[time_positions[0]]) for row in rows]
        if not all(math.isfinite(t) for t in times) or not all(t2>t1 for t1,t2 in zip(times,times[1:])):
            return {'state':'NOT_NUMERIC_TIMESERIES','reason':'INVALID_TIME_AXIS'}
    except (ValueError,OverflowError):
        return {'state':'NOT_NUMERIC_TIMESERIES','reason':'TIME_AXIS_NONNUMERIC'}
    n=len(rows)
    if n<120:return {'state':'NOT_NUMERIC_TIMESERIES','reason':'INSUFFICIENT_OBSERVATIONS','n':n}
    columns=[]
    for k in range(len(head)):
        try:
            a=[float(row[k]) for row in rows]
            if not all(math.isfinite(x) for x in a):continue
            if max(a)-min(a)<=1e-12:continue
            # Independent axis is not a research target; otherwise a linear
            # forecast 'discovers' only that timestamps increase predictably.
            name=head[k].lower().strip()
            if any(word in name for word in ('time','timestamp','index','iteration','step_id','sample_id')):
                continue
            # Axis detection does not depend on the held-out values.
            t=a[:int(len(a)*.6)]
            delta=(t[-1]-t[0])/(len(t)-1)
            if delta and max(abs(v-(t[0]+j*delta)) for j,v in enumerate(t)) <= 1e-10*max(1,abs(t[0]),abs(t[-1])):
                continue
            columns.append((k,a))
        except (ValueError,OverflowError):continue
    if not columns:return {'state':'NOT_NUMERIC_TIMESERIES','reason':'NO_FINITE_VARIANT_COLUMN'}
    # Value-based heuristic, NOT guided by held-out observations: choose highest
    # variance on train ONLY; guard against huge magnitude numerical instability.
    cut=int(n*.6); valid_end=int(n*.8)
    variants=sorted([(statistics.pvariance(x[:cut]),k,x) for k,x in columns],key=lambda v:(-v[0],v[1]))
    _,chosen,values=variants[0]
    if not math.isfinite(variants[0][0]):return {'state':'NOT_NUMERIC_TIMESERIES','reason':'VARIANCE_OVERFLOW'}
    def loss(a:int,b:int,method:str)->float:
        acc=0.0
        for i in range(a,b):
            last=values[i-1]
            if method=='HOLD':pred=last
            elif method=='LINEAR':pred=2*last-values[i-2]
            elif method=='SMOOTH':pred=(last+values[i-2])/2
            else:raise ValueError('UNSUPPORTED_PROGRAM')
            if not math.isfinite(pred):return math.inf
            diff=pred-values[i]
            acc+=diff*diff
        return acc/(b-a)
    try:
        dev={k:loss(cut,valid_end,k) for k in ('HOLD','LINEAR','SMOOTH')}
        if not all(math.isfinite(v) for v in dev.values()):raise OverflowError()
        winner=min(dev,key=lambda k:(dev[k],k))
        test={k:loss(valid_end,n,k) for k in ('HOLD',winner)}
        if not all(math.isfinite(v) for v in test.values()):raise OverflowError()
    except (ArithmeticError,OverflowError):
        return {'state':'NOT_NUMERIC_TIMESERIES','reason':'NUMERIC_OVERFLOW'}
    return {'state':'OBSERVATIONAL_EVALUATED_NOT_ADMITTED',
            'target_column':head[chosen], 'rows':n, 'rows_truncated':n>=MAX_CSV_ROWS,
            'selected_on':'TEMPORAL_VALIDATION_ONLY', 'candidate':winner,
            'validation_mse':dev,'test_mse':test,'test_improvement':test['HOLD']-test[winner],
            'limitation':'CORRELATED_TEMPORAL_TEST_NOT_INDEPENDENT','promotion':'DENIED'}



def evolve_tabular_relations(p:Path, *, max_bytes:int=4_000_000)->dict:
    """Bounded generic discovery: predict one measured numeric column from another.

    No file-specific target specified. All variables, regression feature and
    model are selected from development/validation, not the isolated final 20%.
    The evaluation is observational and never satisfies issue #758 admission.
    """
    if p.stat().st_size>max_bytes:
        return {'state':'TABULAR_REPLAY_PENDING','reason':'BYTE_BUDGET'}
    try:
        rdr=csv.reader(io.StringIO(p.read_bytes().decode('utf-8-sig'),newline=''),strict=True)
        names=next(rdr)
        if not 2<=len(names)<=MAX_COLUMN or len(set(names))!=len(names):
            return {'state':'TABULAR_NOT_EVALUATED','reason':'HEADER_SCHEMA'}
        rows=[]
        for i,row in enumerate(rdr):
            if i>=MAX_CSV_ROWS:break
            if len(row)!=len(names):return {'state':'TABULAR_NOT_EVALUATED','reason':'ROW_SCHEMA'}
            rows.append(row)
    except (UnicodeError,StopIteration,csv.Error):
        return {'state':'TABULAR_NOT_EVALUATED','reason':'CSV_PARSE'}
    n=len(rows)
    if n<60:return {'state':'TABULAR_NOT_EVALUATED','reason':'INSUFFICIENT_ROWS','rows':n}
    vectors={}
    for j,name in enumerate(names):
        try:
            z=[float(r[j]) for r in rows]
            if all(math.isfinite(v) for v in z) and max(z)>min(z):
                vectors[j]=z
        except (ValueError,OverflowError):pass
    if len(vectors)<2:return {'state':'TABULAR_NOT_EVALUATED','reason':'INSUFFICIENT_NUMERIC_COLUMNS'}
    target_names=('error','score','residual','success','fitness','quality','mse',
                  'cost','coherence','fidelity','prediction','value','yield','rate')
    outcomes=[j for j in vectors if any(k in names[j].lower() for k in target_names)]
    if outcomes:target=outcomes[-1]
    else:
        # No semantic outcome identified: do not invent a scientific target.
        return {'state':'TABULAR_NOT_EVALUATED','reason':'TARGET_SEMANTICS_NOT_IDENTIFIED'}
    candidates=[j for j in vectors if j!=target and not any(v in names[j].lower()
                for v in ('id','index','uuid','hash','checksum','seed'))]
    if not candidates:return {'state':'TABULAR_NOT_EVALUATED','reason':'NO_EXPLANATORY_VARIABLE'}
    cut=int(n*.6);val=int(n*.8)
    y=vectors[target];ymean=sum(y[:cut])/cut
    if not math.isfinite(ymean):return {'state':'TABULAR_NOT_EVALUATED','reason':'NUMERIC_OVERFLOW'}
    trained=[]
    for j in candidates:
        x=vectors[j];mx=sum(x[:cut])/cut
        vx=sum((v-mx)**2 for v in x[:cut]);cov=sum((x[i]-mx)*(y[i]-ymean) for i in range(cut))
        if vx>1e-20 and math.isfinite(vx) and math.isfinite(cov):
            a=cov/vx
            if math.isfinite(a):trained.append((j,mx,a))
    if not trained:return {'state':'TABULAR_NOT_EVALUATED','reason':'UNIDENTIFIABLE_REGRESSION'}
    def mse(a,b,proposal):
        j,mx,coef=proposal
        acc=0.0
        for k in range(a,b):
            pred=ymean+coef*(vectors[j][k]-mx)
            acc+=(pred-y[k])**2
        return acc/(b-a)
    base=(-1,0.0,0.0)
    trials=[]
    for j,mx,a in trained:
        for shrink in (0.25,0.5,1.):
            proposal=(j,mx,shrink*a)
            v=mse(cut,val,proposal)
            if math.isfinite(v):trials.append((v,j,shrink,proposal))
    if not trials:return {'state':'TABULAR_NOT_EVALUATED','reason':'NO_FINITE_CANDIDATES'}
    winner=min(trials,key=lambda t:(t[0],t[1],t[2]))
    bval=sum((ymean-y[i])**2 for i in range(cut,val))/(val-cut)
    btest=sum((ymean-y[i])**2 for i in range(val,n))/(n-val)
    test=mse(val,n,winner[3])
    if not all(math.isfinite(v) for v in (test,bval,btest)):
        return {'state':'TABULAR_NOT_EVALUATED','reason':'NONFINITE_SCORE'}
    return {'state':'OBSERVATIONAL_TABULAR_EVALUATED_NOT_ADMITTED','rows':n,
            'target':names[target],'feature':names[winner[1]],
            'genome':{'linear_shrinkage':winner[2]}, 'candidate_count':len(trials),
            'validation_baseline_mse':bval,'validation_candidate_mse':winner[0],
            'test_baseline_mse':btest,'test_candidate_mse':test,
            'test_improvement':btest-test,
            'limitation':'ROW_DEPENDENCE_AND_TARGET_SEMANTICS_NOT_INDEPENDENTLY_VERIFIED',
            'admission':'DENIED','source_mutated':False}


def inspect_structure(p:Path, ext:str)->dict:
    """Parse bounded structured sources without executing imported code."""
    if p.stat().st_size>MAX_TEXT_PARSE:
        return {'state':'BOUNDED_UNPARSED','reason':'BYTE_BUDGET'}
    try:
        if ext=='.json':
            x=json.loads(p.read_text('utf-8'))
            return {'state':'PARSED_JSON','root_type':type(x).__name__}
        if ext=='.py':
            x=ast.parse(p.read_text('utf-8'))
            return {'state':'PARSED_PYTHON_AST','top_level_nodes':len(x.body),
                    'warning':'NOT_EXECUTED'}
        if ext=='.csv':
            temporal=evolve_numeric_csv(p)
            if temporal['state']=='OBSERVATIONAL_EVALUATED_NOT_ADMITTED':
                return {'state':'CSV_TIME_SERIES_EVOLUTION','detail':temporal}
            tabular=evolve_tabular_relations(p)
            if tabular['state']=='OBSERVATIONAL_TABULAR_EVALUATED_NOT_ADMITTED':
                return {'state':'CSV_TABULAR_EVOLUTION','detail':tabular}
            return {'state':'CSV_EVALUATOR_PENDING', 'time_result':temporal,
                    'tabular_result':tabular}
        if ext in ('.lean','.v'):
            text=p.read_text('utf-8',errors='replace')
            return {'state':'FORMAL_SOURCE_STATIC_ONLY','proof_compiled':False,
                    'requires':'PINNED_LEAN_OR_ROCQ_KERNEL',
                    'suspicious_placeholders':sum(text.count(t) for t in ('sorry','admit','Admitted.'))}
    except (UnicodeError,json.JSONDecodeError,SyntaxError,OSError,OverflowError) as e:
        return {'state':'STRUCTURE_PARSE_FAILED','reason':type(e).__name__}
    return {'state':'BINARY_OR_UNSUPPORTED_STRUCTURE', 'data_loss':False}


def make_db(p:Path):
    p.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(p)
    con.execute('PRAGMA journal_mode=WAL')
    con.execute('PRAGMA busy_timeout=5000')
    con.executescript('''
    CREATE TABLE IF NOT EXISTS assets(
      digest TEXT PRIMARY KEY,member TEXT NOT NULL,relpath TEXT NOT NULL,
      category TEXT NOT NULL,format TEXT NOT NULL,bytes INTEGER NOT NULL,
      winner TEXT,encoded_bytes INTEGER,science_state TEXT,science_json TEXT,
      state TEXT NOT NULL,verified INTEGER NOT NULL);
    CREATE TABLE IF NOT EXISTS trials(
      digest TEXT NOT NULL,candidate TEXT NOT NULL,bytes INTEGER,verified INTEGER,
      PRIMARY KEY(digest,candidate));
    CREATE TABLE IF NOT EXISTS coverage(
      object_id INTEGER PRIMARY KEY,digest TEXT, state TEXT NOT NULL,
      reason TEXT,FOREIGN KEY(digest) REFERENCES assets(digest));
    CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    ''')
    return con


def _summary(con, indexed):
    cov=con.execute('SELECT COUNT(*) FROM coverage').fetchone()[0]
    states=dict(con.execute('SELECT state,COUNT(*) FROM coverage GROUP BY state').fetchall())
    assetstates=dict(con.execute('SELECT state,COUNT(*) FROM assets GROUP BY state').fetchall())
    science=dict(con.execute('SELECT science_state,COUNT(*) FROM assets GROUP BY science_state').fetchall())
    gains=con.execute('SELECT SUM(bytes), SUM(encoded_bytes) FROM assets WHERE state=?',('EVOLVED_ROUNDTRIP_VERIFIED',)).fetchone()
    return {'total_indexed':indexed,'objects_accounted_for':cov,'complete':indexed==cov,
            'object_states':states,'unique_asset_states':assetstates,
            'science_states':science,'representation_original_bytes':gains[0],
            'representation_winning_bytes':gains[1],
            'representation_savings_bytes':None if None in gains else gains[0]-gains[1],
            'candidate_trials':con.execute('SELECT COUNT(*) FROM trials').fetchone()[0],
            'scientific_promotion':'DENIED'}


def run(catalog:Path,root:Path,out:Path, *, budget:int=MAX_EVALUATIONS_PER_RUN,
        optimize_dependencies:bool=True)->dict:
    """Idempotent durable run. Every indexed row must receive a coverage status."""
    if not 0<budget<=MAX_EVALUATIONS_PER_RUN:raise ValueError('INVALID_RUN_BUDGET')
    if out.resolve()==catalog.resolve():raise ValueError('INPUT_MUTATION_FORBIDDEN')
    source=sqlite3.connect(f'file:{catalog.resolve()}?mode=ro',uri=True)
    dest=make_db(out)
    start=time.monotonic()
    indexed=source.execute('SELECT COUNT(*) FROM objects').fetchone()[0]
    # Preserve original catalog rows and source integrity claims exactly.
    q='''SELECT id,member,extracted_path,sha256,bytes,format,category,status
         FROM objects ORDER BY id'''
    evaluated=0
    try:
        for oid,member,rel,sha,size,ext,cat,status in source.execute(q):
            prior=dest.execute('SELECT state FROM coverage WHERE object_id=?',(oid,)).fetchone()
            if prior and prior[0]!='AWAITING_RUN_BUDGET':continue
            if prior:dest.execute('DELETE FROM coverage WHERE object_id=?',(oid,))
            if status!='IMPORTED_BYTES_VERIFIED' or not rel or not sha:
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,None,'SOURCE_QUARANTINED',status))
                continue
            if not optimize_dependencies and cat=='DEPENDENCY_OR_GENERATED':
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,None,'DEPENDENCY_INTENTIONALLY_EXCLUDED','POLICY'))
                continue
            if any(s in '/'+member.lower() for s in SENSITIVE_PATH_SEGMENTS):
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,None,'SENSITIVE_METADATA_ONLY','CONTENT_NOT_SCANNED'))
                continue
            existing=dest.execute('SELECT state FROM assets WHERE digest=?',(sha,)).fetchone()
            if existing and existing[0]=='EVOLVED_ROUNDTRIP_VERIFIED':
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,sha,'DEDUP_LINKED_TO_EVALUATED_CONTENT',None))
                continue
            if existing and existing[0]=='SOURCE_ERROR':
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,sha,'EXPERIMENT_BLOCKED','PREVIOUS_SOURCE_ERROR'))
                continue
            if evaluated>=budget:
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,None,'AWAITING_RUN_BUDGET','RESUME_REQUIRED'))
                continue
            try:
                p=validate_source(root,rel,sha,size)
                evolution=evolve_representation(p,sha,size)
                science=inspect_structure(p,ext or '')
                dest.execute('''INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                         (sha,member,rel,cat,ext or '',size,evolution['winner'],
                          evolution['winner_bytes'],science['state'],
                          json_bytes(science).decode('ascii'),'EVOLVED_ROUNDTRIP_VERIFIED',1))
                for t in evolution['trials']:
                    dest.execute('INSERT INTO trials VALUES(?,?,?,?)',
                                 (sha,t['candidate'],t['bytes'],int(t['verified'])))
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,sha,'UNIQUE_REPRESENTATION_EVOLVED','NOT_SCIENTIFIC_PROMOTION'))
                evaluated+=1
            except (OSError,ValueError,OverflowError) as e:
                dest.execute('INSERT INTO assets VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                             (sha,member,rel,cat,ext or '',size,None,None,'NOT_EVALUATED',
                              json_bytes({'reason':type(e).__name__}).decode('ascii'),
                              'SOURCE_ERROR',0))
                dest.execute('INSERT INTO coverage VALUES (?,?,?,?)',
                             (oid,sha,'EXPERIMENT_BLOCKED',type(e).__name__))
            if oid%500==0:dest.commit()
        dest.commit()
        receipt=_summary(dest,indexed)
        receipt.update({'schema':SCHEMA,'run_evaluated_new_unique':evaluated,
                        'elapsed_seconds':round(time.monotonic()-start,3),
                        'catalog_digest':sha256(catalog.read_bytes()),
                        'admission':'DENIED','source_mutated':False,
                        'not_scientific_discovery':True})
        dest.execute('INSERT OR REPLACE INTO meta VALUES (?,?)',('last_receipt',json_bytes(receipt).decode()))
        dest.commit()
        return receipt
    finally:
        source.close();dest.close()


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    p.add_argument('--receipt',type=Path,required=True)
    p.add_argument('--budget',type=int,default=MAX_EVALUATIONS_PER_RUN)
    a=p.parse_args()
    result=run(a.catalog,a.root,a.out,budget=a.budget)
    a.receipt.parent.mkdir(parents=True,exist_ok=True)
    a.receipt.write_bytes(json_bytes(result)+b'\n')
    print(json.dumps(result,indent=2,sort_keys=True))

if __name__=='__main__':main()
