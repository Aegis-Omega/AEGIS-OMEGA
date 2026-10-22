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
    if lens=='QUANTUM_TENSOR_INTERPOLATION_EVOLUTION':
        return ('QUANTUM_TENSOR','EXECUTED_OBSERVATIONAL','CROSS_GAMMA_INDEPENDENT_REPLICATION')
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




def reconcile_import_index(import_db: Path, evolved_db: Path) -> dict:
    """Read-only identity audit of source objects, evolved coverage, and SHA assets.

    This audits the actual mounted catalogs, not a historical 67,445-item claim.
    No discovery, data execution, index rebuild or scientific promotion occurs.
    """
    if (not import_db.is_file() or not evolved_db.is_file()
            or import_db.is_symlink() or evolved_db.is_symlink()
            or import_db.resolve() == evolved_db.resolve()):
        raise ValueError('INDEX_SOURCE_UNAVAILABLE_OR_UNSAFE')
    h = hashlib.sha256()
    with import_db.open('rb') as stream:
        for block in iter(lambda: stream.read(1 << 20), b''):
            h.update(block)
    catalog_sha = h.hexdigest()
    src = sqlite3.connect('file:' + str(import_db.resolve()) + '?mode=ro', uri=True)
    dst = sqlite3.connect('file:' + str(evolved_db.resolve()) + '?mode=ro', uri=True)
    try:
        src.execute('PRAGMA query_only=ON')
        dst.execute('PRAGMA query_only=ON')
        recorded = dst.execute("SELECT value FROM meta WHERE key='last_receipt'").fetchone()
        if recorded is None:
            raise ValueError('MISSING_PINNED_CORPUS_RECEIPT')
        receipt = json.loads(recorded[0])
        if receipt.get('catalog_digest') != catalog_sha:
            raise ValueError('INDEX_CATALOG_SHA256_MISMATCH')
        objects = dict((oid, (digest, status)) for oid, digest, status in
                       src.execute('SELECT id,sha256,status FROM objects'))
        coverage = dict((oid, (digest, state)) for oid, digest, state in
                        dst.execute('SELECT object_id,digest,state FROM coverage'))
        if not objects or set(objects) != set(coverage):
            raise ValueError('INDEX_OBJECT_COVERAGE_MISMATCH')
        verified_assets = dict(dst.execute(
            "SELECT digest,verified FROM assets WHERE state='EVOLVED_ROUNDTRIP_VERIFIED'"))
        if any(v != 1 for v in verified_assets.values()):
            raise ValueError('INDEX_ASSET_NOT_VERIFIED')
        counts = Counter(state for digest, state in coverage.values())
        if counts.get('AWAITING_RUN_BUDGET', 0) or counts.get('EXPERIMENT_BLOCKED', 0):
            raise ValueError('INDEX_COVERAGE_INCOMPLETE_OR_BLOCKED')
        linked = set()
        canonical = set()
        for oid, (digest, state) in coverage.items():
            source_sha, source_state = objects[oid]
            if state in ('UNIQUE_REPRESENTATION_EVOLVED',
                         'DEDUP_LINKED_TO_EVALUATED_CONTENT'):
                if (source_state != 'IMPORTED_BYTES_VERIFIED'
                        or digest != source_sha or digest not in verified_assets):
                    raise ValueError('INDEX_DIGEST_OR_STATE_MISMATCH')
                linked.add(digest)
                if state == 'UNIQUE_REPRESENTATION_EVOLVED':
                    if digest in canonical:
                        raise ValueError('INDEX_DUPLICATE_CANONICAL_ASSET')
                    canonical.add(digest)
            elif state == 'SOURCE_QUARANTINED':
                if digest is not None or source_state == 'IMPORTED_BYTES_VERIFIED':
                    raise ValueError('INDEX_QUARANTINE_STATE_MISMATCH')
            elif state == 'SENSITIVE_METADATA_ONLY':
                if digest is not None or source_state != 'IMPORTED_BYTES_VERIFIED':
                    raise ValueError('INDEX_SENSITIVE_STATE_MISMATCH')
            else:
                raise ValueError('INDEX_UNSUPPORTED_COVERAGE_STATE')
        if linked != canonical or canonical != set(verified_assets):
            raise ValueError('INDEX_ASSET_SET_MISMATCH')
        if receipt.get('total_indexed') != len(objects) or receipt.get('objects_accounted_for') != len(coverage):
            raise ValueError('INDEX_RECEIPT_CARDINALITY_MISMATCH')
        return {
            'schema': 'AEGIS_CORPUS_INDEX_RECONCILIATION_V1',
            'catalog_sha256': catalog_sha,
            'objects_accounted': len(objects),
            'unique_verified_assets': len(canonical),
            'alias_records': counts.get('DEDUP_LINKED_TO_EVALUATED_CONTENT', 0),
            'sensitive_metadata_only': counts.get('SENSITIVE_METADATA_ONLY', 0),
            'quarantined': counts.get('SOURCE_QUARANTINED', 0),
            'coverage_state': 'EXACT_READ_ONLY_PASS',
            'scientific_admission': 'DENIED',
            'source_mutated': False,
        }
    finally:
        src.close()
        dst.close()


def route_and_execute_bioreactor(db:Path,root:Path)->dict:
    """Existing read-only frontier plus real pre-existing bioreactor cohort replay.

    Only execute an evaluator with explicit schema/fitness. Retain the original
    membership receipt and include blocked sources; never self-admit.
    """
    from agents.alphaevolve_bioreactor_v1 import run_catalog
    front=router(db)
    observed=run_catalog(db,root)
    if observed['discovered'] != observed['evaluated']+len(observed['blocked']):
        raise ValueError('BIOREACTOR_SILENT_DROP')
    front['bioreactor_cohort']=observed
    front['scientific_admission']='DENIED'
    return front


def main():
    p=argparse.ArgumentParser();p.add_argument('--db',required=True,type=Path)
    p.add_argument('--out',required=True,type=Path)
    p.add_argument('--data-root',type=Path,default=None,
                   help='Opt in to real read-only biological cohort replay')
    args=p.parse_args()
    d=(router(args.db) if args.data_root is None
       else route_and_execute_bioreactor(args.db,args.data_root))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(d,sort_keys=True,indent=2)+'\n')
    print(json.dumps({k:v for k,v in d.items() if k not in ('cohorts','bioreactor_cohort')},indent=2))


# AUTOMATED CORPUS SCIENCE DISPATCH — additive extension of existing frontier.
# All eligible assets are discovered through the indexed corpus, never named
# manually. Unsupported science is reported and cannot be silently admitted.
def autonomous_dispatch(catalog:Path, root:Path, state_db:Path, *, budget:int=256)->dict:
    import csv
    import hashlib
    if type(budget) is not int or not 1<=budget<=2000:
        raise ValueError("INVALID_BATCH_BUDGET")
    if not catalog.is_file() or not root.is_dir():
        raise ValueError("SOURCE_UNAVAILABLE")
    if state_db.resolve()==catalog.resolve() or state_db.is_symlink():
        raise ValueError("INPUT_MUTATION_DENIED")
    h=hashlib.sha256()
    with catalog.open("rb") as f:
        for part in iter(lambda:f.read(1<<20),b""):
            h.update(part)
    pinned=h.hexdigest()
    src=sqlite3.connect("file:"+str(catalog.resolve())+"?mode=ro",uri=True)
    src.execute("PRAGMA query_only=ON")
    state_db.parent.mkdir(parents=True,exist_ok=True)
    dst=sqlite3.connect(state_db)
    try:
        dst.executescript("""
          CREATE TABLE IF NOT EXISTS config(key TEXT PRIMARY KEY,value TEXT NOT NULL);
          CREATE TABLE IF NOT EXISTS scientific_dispatch(
            sha256 TEXT PRIMARY KEY, format TEXT NOT NULL, status TEXT NOT NULL,
            verified INTEGER NOT NULL, trials INTEGER NOT NULL,
            report_json TEXT NOT NULL, report_sha256 TEXT NOT NULL);
        """)
        expected={"schema":"AEGIS_AUTONOMOUS_FRONTIER_DISPATCH_V1",
                  "catalog_sha256":pinned,"root":str(root.resolve()),
                  "admission":"DENIED"}
        bound=dict(dst.execute("SELECT key,value FROM config"))
        if bound and bound!=expected:
            raise ValueError("SOURCE_CATALOG_REBIND_DENIED")
        if not bound:
            dst.executemany("INSERT INTO config VALUES(?,?)",sorted(expected.items()))
        sources=src.execute("SELECT digest,format FROM assets ORDER BY digest").fetchall()
        if not sources or len(set(row[0] for row in sources))!=len(sources):
            raise ValueError("INVALID_CORPUS")
        dst.executemany("INSERT OR IGNORE INTO scientific_dispatch VALUES(?,?,?,?,?,?,?)",
            ((sha,fmt,"PENDING" if fmt in (".npz",".csv") else
              "SCIENCE_EVALUATOR_UNAVAILABLE",0,0,"{}","") for sha,fmt in sources))
        dst.commit()
        tasks=dst.execute("""SELECT sha256,format FROM scientific_dispatch
          WHERE status='PENDING' ORDER BY
          CASE WHEN format='.npz' THEN 0 ELSE 1 END,sha256 LIMIT ?""",(budget,)).fetchall()
        done=0;trials=0
        for sha,fmt in tasks:
            source=src.execute("SELECT relpath,bytes,format FROM assets WHERE digest=?",(sha,)).fetchone()
            if source is None:raise ValueError("CATALOG_REBIND")
            rel,size,actual_fmt=source
            try:
                if not isinstance(rel,str) or not rel or "\\" in rel or "\x00" in rel:
                    raise ValueError("UNSAFE_PATH")
                relative=Path(rel)
                if relative.is_absolute() or any(part in (".","..") for part in relative.parts):
                    raise ValueError("UNSAFE_PATH")
                base=root.resolve(strict=True);p=base
                for part in relative.parts:
                    p=p/part
                    if p.is_symlink():raise ValueError("SYMLINK_REJECTED")
                if not p.is_file() or not p.resolve().is_relative_to(base) or p.stat().st_size!=size:
                    raise ValueError("SOURCE_MISSING_OR_LENGTH_MISMATCH")
                hh=hashlib.sha256()
                with p.open("rb") as f:
                    for block in iter(lambda:f.read(1<<20),b""):hh.update(block)
                if hh.hexdigest()!=sha or fmt!=actual_fmt:
                    raise ValueError("SOURCE_SHA256_MISMATCH")
                if fmt==".npz":
                    from agents.alphaevolve_quantum_tensor_v1 import evolve_tensor
                    raw=evolve_tensor(p)
                    if raw.get("state")=="QUANTUM_TENSOR_INTERPOLATION_EVOLUTION":
                        result={"state":"EVALUATED_OBSERVATIONAL",
                                "evaluator":"QUANTUM_DENSITY_INTERPOLATION",
                                "candidate_count":raw["candidate_count_per_array"]*len(raw["arrays"]),
                                "measurement":raw}
                    else:
                        result={"state":"SCHEMA_UNSUPPORTED","reason":raw.get("state")}
                elif fmt==".csv":
                    from agents.alphaevolve_bioreactor_v1 import evolve as evolve_bioreactor
                    from agents import alphaevolve_corpus_wide_v1 as cw
                    if size>5_000_000:
                        result={"state":"SCHEMA_UNSUPPORTED","reason":"BYTE_BOUND"}
                    else:
                        with p.open("r",encoding="utf-8-sig",newline="") as f:
                            first=f.readline()[:16384]
                        sep=";" if first.count(";")>first.count(",") else ","
                        header=next(csv.reader([first],delimiter=sep)) if first else []
                        time_tokens={"time","time_fs","time_ps","time_s","timestamp",
                                     "elapsed_time","t_fs","t_ps"}
                        has_header=any(any(ch.isalpha() for ch in cell) for cell in header)
                        result={"state":"SCHEMA_UNSUPPORTED","reason":"NO_VALID_SCIENCE_OBJECTIVE"}
                        if sep=="," and set(x.strip().lower() for x in header)&time_tokens:
                            candidate=cw.evolve_numeric_csv(p)
                            if candidate.get("state")=="OBSERVATIONAL_EVALUATED_NOT_ADMITTED":
                                result={"state":"EVALUATED_OBSERVATIONAL","evaluator":"TIME_SERIES",
                                        "candidate_count":3,"measurement":candidate}
                        if result["state"]!="EVALUATED_OBSERVATIONAL" and not has_header:
                            try:
                                candidate=evolve_bioreactor(p,sha)
                                result={"state":"EVALUATED_OBSERVATIONAL","evaluator":"UNLABELED_BIOREACTOR",
                                        "candidate_count":sum(z["candidate_count"] for z in candidate["observational_results"]),
                                        "measurement":candidate}
                            except ValueError:
                                pass
                        if (result["state"]!="EVALUATED_OBSERVATIONAL" and has_header
                            and sep=="," and hasattr(cw,"evolve_tabular_relations")):
                            candidate=cw.evolve_tabular_relations(p)
                            if candidate.get("state")=="OBSERVATIONAL_TABULAR_EVALUATED_NOT_ADMITTED":
                                result={"state":"EVALUATED_OBSERVATIONAL","evaluator":"NUMERIC_TABULAR",
                                        "candidate_count":candidate["candidate_count"],"measurement":candidate}
                else:
                    raise ValueError("UNREGISTERED_FORMAT")
                verified=1
            except (ValueError,OSError,UnicodeError,csv.Error) as exc:
                result={"state":"BLOCKED_SOURCE_OR_SCHEMA","reason":str(exc)[:140]}
                verified=0
            report=json.dumps(result,sort_keys=True,separators=(",",":"),allow_nan=False)
            n=result.get("candidate_count",0)
            if type(n) is not int or n<0:raise ValueError("INVALID_TRIAL_COUNT")
            dst.execute("""UPDATE scientific_dispatch SET status=?,verified=?,trials=?,
              report_json=?,report_sha256=? WHERE sha256=? AND status='PENDING'""",
              (result["state"],verified,n,report,hashlib.sha256(report.encode()).hexdigest(),sha))
            dst.commit()
            done+=1;trials+=n
        states=dict(dst.execute("SELECT status,COUNT(*) FROM scientific_dispatch GROUP BY status"))
        count=dst.execute("SELECT COUNT(*) FROM scientific_dispatch").fetchone()[0]
        if count!=len(sources):raise ValueError("SILENT_DROP")
        return {"schema":"AEGIS_AUTONOMOUS_FRONTIER_DISPATCH_V1",
                "catalog_sha256":pinned,"unique_assets_accounted":count,
                "new_evaluation_attempts":done,"new_scientific_candidate_trials":trials,
                "total_program_trials":dst.execute("SELECT COALESCE(SUM(trials),0) FROM scientific_dispatch").fetchone()[0],
                "pending":states.get("PENDING",0),"science_states":states,
                "admission":"DENIED","source_mutated":False,
                "limitations":"NO_SCIENTIFIC_PROOF_OR_UNREGISTERED_EVALUATOR_PROMOTION"}
    finally:
        dst.close();src.close()


def autonomous_main():
    import argparse
    a=argparse.ArgumentParser()
    for param in ("catalog","root","state-db"):
        a.add_argument("--"+param,type=Path,required=True)
    a.add_argument("--budget",type=int,default=256)
    a.add_argument("--drain",action="store_true")
    a.add_argument("--out",type=Path)
    args=a.parse_args()
    while True:
        result=autonomous_dispatch(args.catalog,args.root,args.state_db,budget=args.budget)
        if not args.drain or result["pending"]==0:break
    if args.out:
        args.out.parent.mkdir(parents=True,exist_ok=True)
        args.out.write_text(json.dumps(result,sort_keys=True,indent=2)+"\n")
    print(json.dumps(result,sort_keys=True,indent=2))

if __name__=='__main__':
    import sys
    if '--state-db' in sys.argv:autonomous_main()
    else:main()
