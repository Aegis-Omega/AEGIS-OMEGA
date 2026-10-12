"""AEGIS #758: autonomous scientific evaluator for quantum density tensor archives.

Data-native program search: sparse temporal reconstruction of density matrices.
Validation selects interpolator, test used once after selection. Exact source
hashes are checked; no raw tensor modification, quantum-dynamics theorem claim,
or self-admission. Optional numpy, scipy not needed.
"""
from __future__ import annotations
import hashlib
import json
import math
import sqlite3
from pathlib import Path
from collections import Counter
import numpy as np
from agents.alphaevolve_corpus_wide_v1 import validate_source,json_bytes

SCHEMA='AEGIS_QUANTUM_TENSOR_EVOLUTION_V1'
REQUIRED={'time_fs','rho_qdna','rho_independent'}


def _decode(path:Path):
    with np.load(path,allow_pickle=False) as z:
        if not REQUIRED.issubset(set(z.files)):
            raise ValueError('UNSUPPORTED_QUANTUM_SCHEMA')
        times=np.asarray(z['time_fs'],dtype=np.float64)
        rhos=[np.asarray(z[k]) for k in ('rho_qdna','rho_independent')]
        h_name='H_eV' if 'H_eV' in z.files else 'H_rad_ps' if 'H_rad_ps' in z.files else None
        if h_name is None:raise ValueError('MISSING_HAMILTONIAN')
        H=np.asarray(z[h_name])
    if len(times)<100 or not np.all(np.isfinite(times)) or not np.all(np.diff(times)>0):
        raise ValueError('INVALID_TIME_AXIS')
    dim=rhos[0].shape[-1]
    if H.shape!=(dim,dim) or not np.all(np.isfinite(H)):
        raise ValueError('HAMILTONIAN_SHAPE_OR_NONFINITE')
    for a in rhos:
        if a.shape!=(len(times),dim,dim) or dim>64 or not np.all(np.isfinite(a)):
            raise ValueError('RHO_SHAPE_OR_NONFINITE')
    return times,rhos,H


def _invariants(rho:np.ndarray,checks:int=48)->dict:
    idx=np.linspace(0,len(rho)-1,min(checks,len(rho)),dtype=int)
    samples=rho[idx]
    herm=float(np.max(np.abs(samples-np.swapaxes(samples.conj(),-2,-1))))
    trace=float(np.max(np.abs(np.trace(samples,axis1=-2,axis2=-1)-1)))
    evals=np.linalg.eigvalsh((samples+np.swapaxes(samples.conj(),-2,-1))/2)
    eigen=float(np.min(evals))
    return {'frames_checked':len(idx),'max_hermiticity_residual':herm,
            'max_trace_residual':trace,'minimum_eigenvalue':eigen,
            'sampled_state_physically_valid':herm<=1e-8 and trace<=1e-8 and eigen>=-1e-8}


def _loss(rho:np.ndarray,start:int,end:int,stride:int,method:str)->float:
    """Only coarse grid anchors are used by candidate; interior true frames are hidden."""
    if end-start<2*stride:raise ValueError('TEMPORAL_WINDOW_TOO_SHORT')
    errs=[]
    for anchor in range(start,end-stride,stride):
        left=rho[anchor]
        right=rho[anchor+stride]
        for j in range(1,stride):
            if anchor+j>=end:break
            w=j/stride
            if method=='LEFT':pred=left
            elif method=='LINEAR':pred=(1-w)*left+w*right
            elif method=='RIGHT':pred=right
            else:raise ValueError('CANDIDATE_UNKNOWN')
            diff=pred-rho[anchor+j]
            errs.append(float(np.real(np.vdot(diff,diff)))/diff.size)
    if not errs:raise ValueError('NO_HIDDEN_FRAMES')
    return float(sum(errs)/len(errs))


def evolve_tensor(path:Path, *, stride:int=16)->dict:
    if type(stride) is not int or not 4<=stride<=64:
        raise ValueError('STRIDE_BOUNDS')
    times,rhos,H=_decode(path)
    observed=[]
    for key,rho in zip(('rho_qdna','rho_independent'),rhos):
        phys=_invariants(rho)
        if not phys['sampled_state_physically_valid']:
            return {'state':'PHYSICAL_INVARIANT_VETO','array':key,'invariants':phys,
                    'admission':'DENIED'}
        n=len(rho);train=int(n*.6);valid=int(n*.8)
        # Block-scope anchors at start/end; candidate never sees hidden interiors.
        scores={m:_loss(rho,train,valid,stride,m) for m in ('LEFT','LINEAR','RIGHT')}
        champion=min(scores,key=lambda k:(scores[k],k))
        baseline=_loss(rho,valid,n,stride,'LEFT')
        trial=_loss(rho,valid,n,stride,champion)
        observed.append({'tensor':key,'invariants':phys,'stride':stride,
             'validation_mse':scores,'winner':champion,
             'holdout_baseline_mse':baseline,'holdout_candidate_mse':trial,
             'holdout_improvement':baseline-trial,
             'holdout_semantics':'LATER_TIME_BLOCK_WITH_OBSERVED_COARSE_ANCHORS'})
    return {'state':'QUANTUM_TENSOR_INTERPOLATION_EVOLUTION','arrays':observed,
            'heldout_not_independent_gamma_groups':True,
            'candidate_count_per_array':3,'scientific_admission':'DENIED',
            'source_modified':False}


def replay_db(*,catalog:Path,root:Path,evolution_db:Path,stride:int=16)->dict:
    con=sqlite3.connect(evolution_db)
    con.execute('''CREATE TABLE IF NOT EXISTS quantum_evaluation(
         digest TEXT PRIMARY KEY,report TEXT NOT NULL,source_verified INTEGER NOT NULL)''')
    con.execute('''CREATE TABLE IF NOT EXISTS science_revisions(
        digest TEXT NOT NULL,revision TEXT NOT NULL,previous_json TEXT NOT NULL,
        current_json TEXT NOT NULL,PRIMARY KEY(digest,revision))''')
    try:
        rows=con.execute("SELECT digest,relpath,bytes,science_json FROM assets WHERE format='.npz'").fetchall()
        status=Counter()
        for digest,rel,size,old in rows:
            try:
                path=validate_source(root,rel,digest,size)
                if hashlib.sha256(path.read_bytes()).hexdigest()!=digest:
                    raise ValueError('DIGEST_MISMATCH')
                result=evolve_tensor(path,stride=stride)
                verified=True
            except (OSError,ValueError,OverflowError,KeyError) as e:
                result={'state':'TENSOR_EVALUATION_BLOCKED','reason':type(e).__name__,
                        'scientific_admission':'DENIED'}
                verified=False
            data=json_bytes(result).decode('ascii')
            with con:
                con.execute('INSERT OR REPLACE INTO quantum_evaluation VALUES(?,?,?)',
                            (digest,data,int(verified)))
                con.execute('INSERT OR REPLACE INTO science_revisions VALUES(?,?,?,?)',
                            (digest,'NPZ_PHYSICAL_DENSITY_V1',old,data))
                con.execute('UPDATE assets SET science_state=?,science_json=? WHERE digest=?',
                            (result['state'],data,digest))
            status[result['state']]+=1
        return {'schema':SCHEMA,'npz_assets_checked':len(rows),'states':dict(status),
            'source_bytes_rehashed':len(rows),'scientific_admission':'DENIED',
            'not_formal_quantum_proof':True}
    finally:con.close()


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--catalog',type=Path,required=True)
    p.add_argument('--root',type=Path,required=True);p.add_argument('--db',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True);a=p.parse_args()
    result=replay_db(catalog=a.catalog,root=a.root,evolution_db=a.db)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_bytes(json_bytes(result)+b'\n')
    print(json.dumps(result,indent=2))

if __name__=='__main__':main()
