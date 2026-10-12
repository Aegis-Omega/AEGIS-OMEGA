"""AEGIS #758 / PR #773 — resumable corpus-native evolutionary program search.

Design inspired by publicly described Google DeepMind AlphaEvolve primitives:
program archive, island populations, parent sampling, executable evaluators,
recorded failures, budget and checkpoint. THIS IS NOT GOOGLE ALPHAEVOLVE.

Only a constrained, fixed interpreter for an audited probabilistic-series DSL is
supported. No user/LLM-proposed Python is executed, and no process/economic/
formal authority is granted. Optional future program proposer is out of scope.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import random
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
from agents.alphaevolve_generation_ledger_v1 import (
    prepare as prepare_generation_ledger,
    verify as verify_generation_ledger,
    append_evaluated as append_generation,
)
from agents.alphaevolve_genetic_inheritance_v1 import (
    founder, phenotype, reproduce, validate as validate_genome, genome_digest,
)
from agents.alphaevolve_corpus_discovery_v1 import (
    canon, dig, inspect_index, _extract_simplex, _group_tag, _split,
    _physical_project, _series_loss,
)

KIND="AEGIS_ALPHAEVOLVE_ISLANDS_CAMPAIGN_V1"
MAX_TICKS=1_000_000  # per-call safety cap, NOT lifetime generations
MAX_ISLANDS=32
MAX_ROWS_SAMPLE=96
PROPOSAL_STEPS=(0.02,0.05,0.1,0.25,0.5,1,2,4,8)
CANDIDATES_SCHEMA="AEGIS_SAFE_SIMPLEX_DSL_V1"


def _digest_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _validate_program(program: dict) -> tuple[float,float,float]:
    if type(program) is not dict or set(program)!={"schema","alpha","beta","shrink"}:
        raise ValueError("DSL_PROGRAM_SCHEMA_INVALID")
    if program["schema"]!=CANDIDATES_SCHEMA:
        raise ValueError("DSL_UNKNOWN_SCHEMA")
    bounds={"alpha":(-8,16),"beta":(-40,80),"shrink":(0,1)}
    for k,(lo,hi) in bounds.items():
        x=program[k]
        if type(x) not in (int,float) or not math.isfinite(x) or not lo <= x <= hi:
            raise ValueError("DSL_PARAMETER_BOUNDS_INVALID")
    return tuple(float(program[k]) for k in ("alpha","beta","shrink"))


def program(alpha:float,beta:float,shrink:float=0.0)->dict:
    p={"schema":CANDIDATES_SCHEMA,"alpha":round(float(alpha),4),
       "beta":round(float(beta),4),"shrink":round(float(shrink),4)}
    _validate_program(p)
    return p


def _dataset(family:dict)->tuple[dict,list[dict]]:
    data={}; sources=[]
    for item in family["sources"]:
        arr=_extract_simplex(tuple(family["names"]),item)
        label=_group_tag(item["member"],item["source_sha256"])
        data.setdefault(label,[]).append(arr)
        sources.append({"digest":item["source_sha256"],"group":label})
    return data,sources


def _design(arr:np.ndarray, *, sample:int|None)->tuple[np.ndarray,np.ndarray,np.ndarray,np.ndarray]:
    h=8
    x=arr.astype(np.float64,copy=False)
    if len(x)<h+20: raise ValueError("SERIES_TOO_SHORT")
    t=x[2:-h]
    d=t-x[1:-h-1]
    d2=t-2*x[1:-h-1]+x[:-h-2]
    y=x[2+h:]
    if sample is not None and len(t)>sample:
        idx=np.linspace(0,len(t)-1,sample,dtype=int)
        t,d,d2,y=t[idx],d[idx],d2[idx],y[idx]
    return t,d,d2,y


@dataclass
class Evaluator:
    train:dict
    validation:dict
    groups:dict
    sources:list
    source_root:str

    @classmethod
    def discover(cls, catalog:Path,root:Path, *, csv_budget:int=256):
        index=inspect_index(catalog,root,max_csv=csv_budget)
        families=[x for x in index["families"] if x["candidate_kind"]=="SIMPLEX_DYNAMICS_FORECAST"]
        if not families:raise ValueError("NO_SUPPORTED_RESEARCH_FAMILY")
        family=families[0]  # objective selector pre-defined; never based on holdout outcomes
        data,sources=_dataset(family)
        split=_split(list(data))
        def build(names,sample):
            return {name:[_design(x,sample=sample) for x in data[name]] for name in names}
        return cls(train=build(split["train"],MAX_ROWS_SAMPLE),
                   validation=build(split["validation"],MAX_ROWS_SAMPLE),
                   groups=split,sources=sources,source_root=family["schema_sha256"]),index

    @staticmethod
    def group_loss(rows:list, parameters:tuple)->float:
        a,b,shrink=parameters
        values=[]
        for t,d,d2,y in rows:
            forecast=_physical_project(t+a*d+b*d2+shrink*(1/t.shape[1]-t))
            values.append(float(np.mean((forecast-y)**2)))
        return float(np.mean(values))

    @classmethod
    def score(cls,part:dict,parameters:tuple)->tuple[float,dict]:
        by_group={}
        for group,series in part.items():
            new=cls.group_loss(series,parameters)
            base=cls.group_loss(series,(0.,0.,0.))
            if not (math.isfinite(new) and math.isfinite(base)):
                raise ValueError("NONFINITE_EVALUATION")
            by_group[group] = new/max(base,1e-20)
        return float(np.mean(list(by_group.values()))),by_group


def _database(path:Path, *, create:bool=True)->sqlite3.Connection:
    if path.is_symlink():raise ValueError("EVOLUTION_DATABASE_SYMLINK")
    if not create and not path.is_file():raise ValueError("EVOLUTION_DATABASE_MISSING")
    path.parent.mkdir(parents=True,exist_ok=True)
    conn=sqlite3.connect(path)
    conn.execute("PRAGMA busy_timeout=5000")
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
      CREATE TABLE IF NOT EXISTS campaign (key TEXT PRIMARY KEY,value TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS candidates (
        id TEXT PRIMARY KEY, island INTEGER NOT NULL, tick TEXT NOT NULL,
        parent TEXT, program TEXT NOT NULL, train REAL NOT NULL, validation REAL NOT NULL,
        regression INTEGER NOT NULL, outcome TEXT NOT NULL,
        evaluation_digest TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS ticks (tick TEXT PRIMARY KEY,candidate_id TEXT NOT NULL,status TEXT NOT NULL);
      CREATE TABLE IF NOT EXISTS breeding (
        tick TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
        mother_id TEXT, father_id TEXT, genome TEXT NOT NULL,
        inheritance_trace TEXT NOT NULL, genome_digest TEXT NOT NULL);
      CREATE INDEX IF NOT EXISTS idx_candidates_rank ON candidates(island,regression,validation);
    """)
    return conn


def _get_meta(conn:sqlite3.Connection,name:str)->Any:
    row=conn.execute("SELECT value FROM campaign WHERE key=?",(name,)).fetchone()
    return None if row is None else json.loads(row[0])


def _set_meta(conn,name,value):
    conn.execute("INSERT OR REPLACE INTO campaign VALUES (?,?)",(name,canon(value).decode("ascii")))


def _candidate(conn,island:int,tick:int,seed:int)->tuple[dict,str|None]:
    rng=random.Random((seed<<32)^tick)
    starting=[(0,0,0),(1,0,0),(4,0,0),(8,0,0),(8,28.5,0),
              (0,0,0.5),(8,16,0),(8,40,0),(2,4,0.2)]
    if tick<len(starting):return program(*starting[tick]),None
    ranked=conn.execute("""SELECT id,program FROM candidates WHERE island=? AND regression=0
                    ORDER BY validation ASC,train ASC,id ASC LIMIT 12""",(island,)).fetchall()
    if not ranked or rng.random()<0.10:
        parent=None;old=(rng.uniform(-8,16),rng.uniform(-40,80),rng.uniform(0,1))
    else:
        best_pool=ranked[:min(4,len(ranked))] if rng.random()<0.70 else ranked
        parent,p_json=rng.choice(best_pool)
        old=_validate_program(json.loads(p_json))
    dims=list(old)
    choose=rng.randrange(3)
    step=rng.choice(PROPOSAL_STEPS)
    if choose==2: step=min(0.4,step/10)
    dims[choose] += step * rng.choice((-1,1))
    limits=((-8,16),(-40,80),(0,1))
    dims=[min(hi,max(lo,x)) for x,(lo,hi) in zip(dims,limits)]
    return program(*dims),parent



def _genetic_candidate(conn:sqlite3.Connection, island:int, tick:int, seed:int) -> tuple[dict,dict,dict]:
    """Two-parent reproduction among evaluated candidates; no untrusted code execution.

    Founder fallback is explicit until both karyotypes have verified candidate
    ancestry. Rankings use validation ONLY, not frozen heldout configurations.
    """
    if tick<9:
        p,_=_candidate(conn,island,tick,seed)
        g=founder(p,sex='XX' if tick%2==0 else 'XY')
        return phenotype(g),g,{'generation_kind':'FOUNDER','mother_id':None,
                               'father_id':None,'parent_source':'SEEDED_PROGRAM'}
    rows=conn.execute('''SELECT c.id,c.program,b.genome,c.island FROM candidates AS c
          JOIN breeding AS b ON b.tick=(SELECT b2.tick FROM breeding b2 WHERE b2.candidate_id=c.id ORDER BY b2.rowid LIMIT 1)
          WHERE c.regression=0 ORDER BY c.validation ASC,c.train ASC,c.id ASC LIMIT 80''').fetchall()
    decoded=[]
    for cid,p_text,g_text,parent_island in rows:
        g=json.loads(g_text);validate_genome(g)
        if phenotype(g)!=json.loads(p_text):
            raise ValueError('GENETIC_PARENT_GENOME_PHENOTYPE_MISMATCH')
        decoded.append((cid,g,parent_island))
    rng=random.Random((seed<<32)^tick^0xAE615)
    def choose(karyotype):
        eligible=[x for x in decoded if x[1]['sex_chromosomes'][1]['kind']==karyotype[-1]]
        local=[x for x in eligible if x[2]==island]
        # Migration: sometimes choose from a different island to avoid collapse.
        pool=eligible if rng.random()<0.20 or not local else local
        return rng.choice(pool[:min(len(pool),12)]) if pool else None
    maternal=choose('XX')
    paternal=choose('XY')
    if maternal is None or paternal is None:
        # NOT fabricated ancestry: seed genomes are explicitly unranked founders.
        seedp,_=_candidate(conn,island,tick,seed)
        if maternal is None:maternal=(None,founder(seedp,sex='XX'),island)
        if paternal is None:paternal=(None,founder(seedp,sex='XY'),island)
    child,mechanism=reproduce(maternal[1],paternal[1],seed=rng.randrange(2**64))
    p=phenotype(child)
    trace={'generation_kind':'RECOMBINATION','mother_id':maternal[0],
           'father_id':paternal[0], 'parent_source':(
             'EVALUATED_PARENTS' if maternal[0] and paternal[0]
             else 'FOUNDER_ASSISTED'), 'inheritance':mechanism}
    return p,child,trace


def search(*, catalog:Path,root:Path,database:Path,
           additional_ticks:int=2000,islands:int=4,seed:int=758,
           csv_budget:int=256,inheritance_mode:str='asexual_v1')->dict:
    """Resume strictly from recorded progress. Does not inspect heldout outcomes."""
    if inheritance_mode not in ('asexual_v1','diploid_xy_v1'):
        raise ValueError('INHERITANCE_MODE_INVALID')
    if type(additional_ticks) is not int or not 1<=additional_ticks<=MAX_TICKS:
        raise ValueError("TICK_BUDGET_INVALID")
    if type(islands) is not int or not 1<=islands<=MAX_ISLANDS:
        raise ValueError("ISLAND_COUNT_INVALID")
    if type(seed) is not int or not 0<=seed<=2**31-1:
        raise ValueError("RANDOM_SEED_INVALID")
    ev,index=Evaluator.discover(catalog,root,csv_budget=csv_budget)
    source_binding=dig({"family":ev.source_root,"sources":sorted(ev.sources,key=lambda s:(s["group"],s["digest"])),
                        "split":ev.groups,"dsl":CANDIDATES_SCHEMA})
    conn=_database(database)
    try:
        previous=_get_meta(conn,"binding")
        if previous is None:
            with conn:
                _set_meta(conn,"binding",source_binding)
                _set_meta(conn,"islands",islands)
                _set_meta(conn,"seed",seed)
                _set_meta(conn,"partitions",ev.groups)
                _set_meta(conn,"finalized",False)
                _set_meta(conn,"inheritance_mode",inheritance_mode)
        elif (previous!=source_binding or _get_meta(conn,"islands")!=islands or
              _get_meta(conn,"seed")!=seed or
              (_get_meta(conn,"inheritance_mode") or 'asexual_v1')!=inheritance_mode):
            raise ValueError("CAMPAIGN_SOURCE_OR_CONFIG_DRIFT")
        if _get_meta(conn,"finalized"):
            raise ValueError("CAMPAIGN_ALREADY_FROZEN")
        checkpoint = None
        prepare_generation_ledger(conn,binding=source_binding)
        checkpoint=verify_generation_ledger(conn,binding=source_binding)
        count=int(checkpoint['next_generation'])
        previous_root=checkpoint['chain_root']
        # Use one unique program record globally; still count duplicate proposals.
        for tick in range(count,count+additional_ticks):
            island=tick%islands
            if inheritance_mode=='diploid_xy_v1':
                cand,genome,lineage=_genetic_candidate(conn,island,tick,seed)
                parent=lineage['mother_id']
            else:
                cand,parent=_candidate(conn,island,tick,seed)
            cid=dig(cand)
            old=conn.execute("SELECT id FROM candidates WHERE id=?",(cid,)).fetchone()
            if old:
                outcome_for_tick="DUPLICATE"
                conn.execute("INSERT INTO ticks VALUES(?,?,?)",(str(tick),cid,outcome_for_tick))
            else:
                params=_validate_program(cand)
                train,_=ev.score(ev.train,params)
                validation,by_group=ev.score(ev.validation,params)
                regression=any(x>1+1e-12 for x in by_group.values())
                outcome="EVALUATED_VETO" if regression else "EVALUATED_CANDIDATE"
                proof={"program":cand,"sources":source_binding,
                       "train_relative_mse":train,"validation_relative_mse":validation,
                       "validation_by_group":by_group,"outcome":outcome}
                conn.execute("INSERT INTO candidates VALUES(?,?,?,?,?,?,?,?,?,?)",
                    (cid,island,str(tick),parent,canon(cand).decode(),train,validation,
                     int(regression),outcome,dig(proof)))
                outcome_for_tick=outcome
                conn.execute("INSERT INTO ticks VALUES(?,?,?)",(str(tick),cid,outcome_for_tick))
            if inheritance_mode=='diploid_xy_v1':
                validate_genome(genome)
                if phenotype(genome)!=cand:
                    raise ValueError('OFFSPRING_PHENOTYPE_MISMATCH')
                conn.execute("INSERT INTO breeding VALUES(?,?,?,?,?,?,?)",
                    (str(tick),cid,lineage['mother_id'],lineage['father_id'],
                     canon(genome).decode(),canon(lineage).decode(),genome_digest(genome)))
            previous_root=append_generation(conn,generation=tick,candidate_id=cid,
                                            status=outcome_for_tick,binding=source_binding,
                                            prior_root=previous_root)
            if tick%100==99:conn.commit()
        conn.commit()
        ledger_receipt=verify_generation_ledger(conn,binding=source_binding)
        best=conn.execute("SELECT id,program,train,validation FROM candidates WHERE regression=0 ORDER BY validation ASC,train ASC,id ASC LIMIT 1").fetchone()
        total=conn.execute("SELECT COUNT(*) FROM ticks").fetchone()[0]
        unique=conn.execute("SELECT COUNT(*) FROM candidates").fetchone()[0]
        report={"schema":KIND,"status":"SEARCH_CHECKPOINT","sqlite_catalog_records":index["indexed_records"],
                "corpus_source_digest":source_binding,"programs_evaluated":unique,
                "ticks_proposed":total,"duplicate_ticks":total-unique,"islands":islands,
                "inheritance_mode":inheritance_mode,
                "genetic_offspring":conn.execute("SELECT COUNT(*) FROM breeding WHERE mother_id IS NOT NULL AND father_id IS NOT NULL").fetchone()[0],
                "genetic_trace_count":conn.execute("SELECT COUNT(*) FROM breeding").fetchone()[0],
                "budget_max_ticks_per_invocation":MAX_TICKS,
                "generation_next_decimal":ledger_receipt["next_generation"],
                "generation_ledger_root":ledger_receipt["chain_root"],
                "generation_ledger_verified":ledger_receipt["verified_records"],
                "generation_identifier_representation":"ARBITRARY_PRECISION_DECIMAL_TEXT",
                "executed_generations_claimed":total,
                "holdout_evaluated":False,
                "best_candidate":None if not best else {"digest":best[0],"program":json.loads(best[1]),
                                  "train_relative_mse":best[2],"validation_relative_mse":best[3]},
                "independent_review":"NOT_PERFORMED","scientific_admission":"DENIED",
                "authority_effect":"NONE","production_effect":"NONE"}
        return {**report,"receipt_hash":dig(report)}
    finally:conn.close()


def finalize(*,catalog:Path,root:Path,database:Path,csv_budget:int=256)->dict:
    """One-shot holdout. Finalized campaigns refuse subsequent mutation."""
    ev,index=Evaluator.discover(catalog,root,csv_budget=csv_budget)
    conn=_database(database,create=False)
    try:
        if _get_meta(conn,"finalized"):raise ValueError("HOLDOUT_ALREADY_OPENED")
        expected=dig({"family":ev.source_root,"sources":sorted(ev.sources,key=lambda s:(s["group"],s["digest"])),
                      "split":ev.groups,"dsl":CANDIDATES_SCHEMA})
        if _get_meta(conn,"binding")!=expected:raise ValueError("CAMPAIGN_SOURCE_OR_CONFIG_DRIFT")
        best=conn.execute("SELECT id,program,train,validation FROM candidates WHERE regression=0 ORDER BY validation ASC,train ASC,id ASC LIMIT 1").fetchone()
        if not best:raise ValueError("NO_ELIGIBLE_CHAMPION")
        names=ev.groups["holdout"]
        family=[x for x in index["families"] if x["schema_sha256"]==ev.source_root][0]
        data,_=_dataset(family)
        holdout={n:[_design(x,sample=None) for x in data[n]] for n in names}
        score,by_group=ev.score(holdout,_validate_program(json.loads(best[1])))
        result={"schema":"AEGIS_ALPHAEVOLVE_HOLDOUT_FREEZE_V1",
                "candidate_digest":best[0],"source_binding":expected,
                "holdout_group_count":len(names),"relative_mse":score,"group_ratios":by_group,
                "scenario_regression_veto":any(v>1+1e-12 for v in by_group.values()),
                "issue758_minimum_30_independent_groups_met":len(names)>=30,
                "independent_review":"NOT_PERFORMED","scientific_admission":"DENIED",
                "authority_effect":"NONE","production_effect":"NONE"}
        result={**result,"receipt_hash":dig(result)}
        with conn:
            _set_meta(conn,"holdout_receipt",result)
            _set_meta(conn,"finalized",True)
        return result
    finally:conn.close()


def main():
    p=argparse.ArgumentParser(description="AEGIS offline resumable multi-island candidate search")
    sub=p.add_subparsers(dest="cmd",required=True)
    for cmd in ("search","finalize"):
        x=sub.add_parser(cmd)
        x.add_argument("--catalog",type=Path,required=True)
        x.add_argument("--root",type=Path,required=True)
        x.add_argument("--db",type=Path,required=True)
        x.add_argument("--csv-budget",type=int,default=256)
        if cmd=="search":
            x.add_argument("--ticks",type=int,default=2000)
            x.add_argument("--islands",type=int,default=4)
            x.add_argument("--seed",type=int,default=758)
            x.add_argument("--inheritance",choices=('asexual_v1','diploid_xy_v1'),default='asexual_v1')
    args=p.parse_args()
    kw={"catalog":args.catalog,"root":args.root,"database":args.db,"csv_budget":args.csv_budget}
    if args.cmd=="search":out=search(**kw,additional_ticks=args.ticks,islands=args.islands,seed=args.seed,inheritance_mode=args.inheritance)
    else:out=finalize(**kw)
    print(json.dumps(out,indent=2,sort_keys=True))

if __name__=="__main__":main()
