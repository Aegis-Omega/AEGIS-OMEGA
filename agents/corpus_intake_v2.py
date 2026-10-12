"""AEGIS Ω corpus discovery and QuantumDNA invariant preflight.

Read-only. Reports discovery and reproducible structural/physical checks, NEVER
scientific proof, capability authorization or admitted AlphaEvolve gains.
No extraction, pickle, code execution, model loading or external networking.

Usage:
 python -m agents.corpus_intake_v2 --archives source_archives/*.zip --output reports
"""
from __future__ import annotations
import argparse
import collections
import csv
import gzip
import hashlib
import io
import json
import math
import os
from pathlib import Path, PurePosixPath
import re
import stat
import zipfile
from typing import Iterable

EXT_DATA = {
    '.csv','.tsv','.txtdata','.parquet','.arrow','.feather','.orc','.avro',
    '.npy','.npz','.h5','.hdf5','.hdf','.zarr','.nc','.netcdf','.grib',
    '.fits','.fit','.fts','.tif','.tiff','.nii','.nrrd','.dcm','.dicom',
    '.pdb','.cif','.mmcif','.sdf','.mol2','.pqr','.xyz','.gro','.xtc','.dcd',
    '.fasta','.fa','.fna','.faa','.fastq','.fq','.vcf','.bcf','.bam','.cram',
    '.sam','.bed','.gff','.gtf','.gff3','.bigwig','.bw','.bigbed','.2bit',
    '.h5ad','.h5mu','.loom','.mtx','.rds','.rdata','.qs','.fst',
    '.sqlite','.sqlite3','.db','.duckdb','.mdb','.accdb','.xls','.xlsx','.xlsb','.ods',
    '.jsonl','.ndjson','.geojson','.shp','.gpkg','.las','.laz','.ply','.obj',
    '.pt','.pth','.safetensors','.onnx','.gguf','.tfrecord','.record','.pkl',
}
EXT_FORMAL={'.lean','.v','.thy','.agda','.coq','.rocq','.smt2','.p','.tptp'}
EXT_CODE={'.py','.js','.mjs','.cjs','.ts','.tsx','.rs','.go','.c','.cpp','.h','.hpp','.sh','.bat','.ps1','.sql','.jl','.r','.ipynb.py'}
EXT_DOC={'.md','.pdf','.doc','.docx','.html','.htm','.rst','.tex','.pages','.png','.jpg','.jpeg','.webp','.svg'}
EXT_NB={'.ipynb','.rmd','.qmd','.jlnb'}
EXT_MODEL={'.bin','.ckpt','.pt','.pth','.safetensors','.onnx','.gguf','.whl'}
EXT_ARCH={'.zip','.tar','.7z','.rar','.gz','.tgz','.bz2','.xz','.zst','.bundle'}
DEPENDENCY_PREFIXES={'node_modules','.git','.venv','venv','dist','build','target','.lake','__pycache__'}
KNOWN_MULTISUFFIX=('.nii.gz','.vcf.gz','.fastq.gz','.fq.gz','.fasta.gz','.fa.gz','.tar.gz','.csv.gz','.tsv.gz','.jsonl.gz','.ndjson.gz','.bed.gz','.gff.gz','.gff3.gz','.mtx.gz')


def canonical(x):return json.dumps(x,sort_keys=True,ensure_ascii=True,separators=(',',':'),allow_nan=False)
def sha_file(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()

def format_name(path):
    s=path.lower()
    for ending in KNOWN_MULTISUFFIX:
        if s.endswith(ending):return ending
    return Path(s).suffix or '(none)'

def kind(path):
    parts={p.lower() for p in PurePosixPath(path.replace('\\','/')).parts}
    suffix=format_name(path)
    if DEPENDENCY_PREFIXES & parts:return 'DEPENDENCY_OR_GENERATED'
    if suffix in {'.pkl','.pickle','.joblib'}:return 'UNSAFE_SERIALIZATION_NOT_EVALUATED'
    if suffix in EXT_NB:return 'EXECUTABLE_NOTEBOOK_UNTRUSTED'
    if suffix in EXT_FORMAL:return 'FORMAL_SOURCE_NOT_PROOF'
    if suffix in EXT_ARCH:return 'NESTED_ARCHIVE_UNOPENED'
    if suffix in EXT_MODEL:return 'MODEL_OR_BINARY_UNTRUSTED'
    if suffix in EXT_CODE:return 'CODE_NOT_DATASET'
    if suffix in EXT_DATA or any(suffix.startswith(x) for x in ('.csv.','.tsv.','.jsonl.','.vcf.','.fasta.','.fastq.','.nii.')):
        return 'DATASET_CANDIDATE_NOT_EVALUATED'
    if suffix in ('.json','.yaml','.yml','.xml','.toml','.ini','.config'):
        return 'STRUCTURED_POTENTIAL_DATA_OR_RECEIPT'
    if suffix in EXT_DOC:return 'DOCUMENT_OR_MEDIA_NOT_NUMERIC_DATASET'
    return 'UNKNOWN_RETAIN_FOR_REVIEW'

def safe_member(name, info):
    p=PurePosixPath(name)
    if ('\\' in name or name.startswith('/') or '\x00' in name or not p.parts or ':' in p.parts[0]
            or '..' in p.parts or not name):return False,'UNSAFE_PATH'
    if stat.S_ISLNK(info.external_attr >> 16):return False,'SYMLINK'
    if info.flag_bits & 1:return False,'ENCRYPTED'
    if info.file_size>5*1024**3:return False,'HUGE_MEMBER'
    if info.compress_size and info.file_size>2000*info.compress_size and info.file_size>10*1024**2:
        return False,'HIGH_COMPRESSION_RATIO'
    return True,'INDEX_ONLY'

def inspect_archive(path:Path, archive_sha:str|None=None, max_entries:int=150000):
    if not zipfile.is_zipfile(path):raise ValueError('NOT_ZIP')
    archive_sha=archive_sha or sha_file(path)
    with zipfile.ZipFile(path) as f:
        infos=f.infolist()
        if len(infos)>max_entries:raise ValueError('ARCHIVE_ENTRY_LIMIT')
        entries=[]
        for item in infos:
            if item.is_dir():continue
            safe,reason=safe_member(item.filename,item)
            entries.append({'archive':path.name,'archive_sha256':archive_sha,
                  'member':item.filename,'bytes':item.file_size,
                  'compressed_bytes':item.compress_size,'crc32':f'{item.CRC:08x}',
                  'format':format_name(item.filename),'kind':kind(item.filename),
                  'safe_to_consider':safe,'index_status':reason,
                  'validation':'NOT_EVALUATED','member_sha256':'NOT_COMPUTED'})
    return entries

def _quantum_member_names(z):
    prefix='AEGIS_QuantumDNA_v1/results/'
    names={x.filename for x in z.infolist() if not x.is_dir()}
    csvs=sorted(x for x in names if x.startswith(prefix) and x.endswith('.csv'))
    npzs=sorted(x for x in names if x.startswith(prefix) and x.endswith('.npz'))
    pairs=[]
    for n in csvs:
        if n.endswith('sweep_summary.csv'):continue
        stem=n[:-4]
        paired=stem+'_states.npz'
        pairs.append({'csv':n,'tensor':paired if paired in names else None})
    return pairs,csvs,npzs

def quantumdna_preflight(zip_path:Path, max_csv_bytes=5_000_000):
    """Safely inspect *all* trajectories and NPZ structures; no pickle or numerical model execution.

    Invariants: consistent fields, finite time/populations, monotonic time,
    nonnegative populations, probability normalization and coherence >=0.
    Does not establish quantum dynamics, physical truth or holdout independence.
    """
    defects=[]; summary=[]; npz_checks=[]; availability_warnings=[]
    with zipfile.ZipFile(zip_path) as z:
        pairs,csvs,npzs=_quantum_member_names(z)
        for pair in pairs:
            info=z.getinfo(pair['csv'])
            if info.file_size>max_csv_bytes:
                defects.append({'file':pair['csv'],'reason':'CSV_BUDGET_EXCEEDED'});continue
            if pair['tensor'] is None:
                defects.append({'file':pair['csv'],'reason':'NPZ_PAIR_MISSING'})
            with z.open(pair['csv']) as f:
                reader=csv.DictReader(io.TextIOWrapper(f,encoding='utf-8-sig',newline=''))
                cols=reader.fieldnames or []
                is_sweep=all(f'P_{i}' in cols for i in range(6))
                is_reference='time_fs' in cols and 'ground_population' in cols
                if not(is_sweep or is_reference):
                    defects.append({'file':pair['csv'],'reason':'UNKNOWN_TIME_SERIES_SCHEMA'});continue
                prev=-math.inf;rows=0;max_dev=0.;min_pop=math.inf;negative_coherence=0;classical_unavailable_rows=0
                for row in reader:
                    rows+=1
                    try:
                        t=float(row['time_fs'])
                        if not math.isfinite(t) or t<=prev:raise ValueError('TIME_NOT_INCREASING')
                        prev=t
                        if is_sweep:
                            p=[float(row[f'P_{i}']) for i in range(6)]
                            q=[float(row[f'classical_P_{i}']) for i in range(6)]
                            coh=float(row['coherence_l1'])
                            if not all(math.isfinite(v) for v in p+[coh]):raise ValueError('NONFINITE_QUANTUM')
                            classical_valid=all(math.isfinite(v) for v in q)
                            classical_missing=all(math.isnan(v) for v in q)
                            # gamma=0 produces a quantum-only reference: classical columns
                            # intentionally encode unavailable data as NaN, not zeroes.
                            if classical_missing and pair['csv'].endswith('_gamma_0.csv'):
                                classical_unavailable_rows+=1
                            elif not classical_valid:
                                raise ValueError('INVALID_CLASSICAL_REFERENCE')
                            min_pop=min(min_pop,*p)
                            max_dev=max(max_dev,abs(sum(p)-1))
                            if classical_valid:
                                min_pop=min(min_pop,*q)
                                max_dev=max(max_dev,abs(sum(q)-1))
                            if coh< -1e-10:negative_coherence+=1
                        elif is_reference:
                            g=float(row['ground_population'])
                            if not math.isfinite(g):raise ValueError('NONFINITE')
                    except (KeyError,TypeError,ValueError) as e:
                        defects.append({'file':pair['csv'],'row':rows,'reason':str(e)});break
                if is_sweep:
                    if min_pop< -1e-10: defects.append({'file':pair['csv'],'reason':'NEGATIVE_POPULATION'})
                    if max_dev>1e-8: defects.append({'file':pair['csv'],'reason':'NORMALIZATION_REGRESSION','max_dev':max_dev})
                    if negative_coherence:defects.append({'file':pair['csv'],'reason':'NEGATIVE_COHERENCE'})
                if classical_unavailable_rows:
                    availability_warnings.append({'file':pair['csv'],
                        'status':'CLASSICAL_REFERENCE_NOT_DEFINED',
                        'unavailable_rows':classical_unavailable_rows})
                summary.append({'file':pair['csv'],'rows':rows,'schema':'SWEEP' if is_sweep else 'REFERENCE',
                         'max_population_sum_residual':max_dev if is_sweep else None,
                         'classical_reference_unavailable_rows':classical_unavailable_rows,
                         'tensor_pair':pair['tensor'],'check':'STRUCTURAL_AND_NUMERIC_PREFLIGHT_ONLY'})
        for name in npzs:
            info=z.getinfo(name)
            if info.file_size>25_000_000:
                defects.append({'file':name,'reason':'NPZ_MEMBER_TOO_LARGE'});continue
            raw=z.read(name)
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                    infos=inner.infolist()
                    if not infos or len(infos)>64 or any(not x.filename.endswith('.npy') for x in infos):
                        raise ValueError('NPZ_UNEXPECTED_MEMBERS')
                    npz_checks.append({'file':name,'arrays':sorted(x.filename for x in infos),
                      'array_count':len(infos),'check':'ZIP_STRUCTURE_ONLY_ARRAY_VALUES_NOT_LOADED'})
            except (zipfile.BadZipFile,ValueError) as e:
                defects.append({'file':name,'reason':str(e)})
    return {'schema':'AEGIS_QUANTUMDNA_PREFLIGHT_V1','csv_count':len(csvs),
            'npz_count':len(npzs),'paired_trajectories':sum(p['tensor'] is not None for p in pairs),
            'trajectories_checked':len(summary),'npz_structures_checked':len(npz_checks),
            'rows_checked':sum(x['rows'] for x in summary),'defects':defects,
            'availability_warnings':availability_warnings,
            'trajectory_summary':summary,'tensor_structure_summary':npz_checks,
            'scientific_admission':'NOT_EVALUATED','independent_holdout':'NOT_ESTABLISHED'}

def build_catalog(archives:Iterable[Path],outdir:Path,quantumdna:Path|None=None):
    outdir.mkdir(parents=True,exist_ok=True)
    per=[];full=[]
    for path in sorted(map(Path,archives)):
        digest=sha_file(path);rows=inspect_archive(path,digest)
        counts=collections.Counter(r['kind'] for r in rows)
        formats=collections.Counter(r['format'] for r in rows)
        per.append({'archive':path.name,'sha256':digest,'bytes':path.stat().st_size,
                    'file_entries':len(rows),'kind_counts':dict(sorted(counts.items())),
                    'format_counts':dict(sorted(formats.items())),
                    'unsafe_entries':sum(not r['safe_to_consider'] for r in rows)})
        full.extend(rows)
    with gzip.open(outdir/'entries.jsonl.gz','wt',encoding='utf8') as f:
        for row in full:f.write(canonical(row)+'\n')
    result={'schema':'AEGIS_UNIVERSAL_CORPUS_INDEX_V2',
       'archives':per,'archive_members_indexed':len(full),
       'scope':'ONLY_ARCHIVES_LISTED_IN_THIS_RECEIPT_NOT_ALL_CONNECTED_ACCOUNTS',
       'entry_validation':'ZIP_CENTRAL_DIRECTORY_METADATA_NOT_CONTENT_PROOF',
       'evolution_status':'NOT_EVALUATED_UNTIL_DOMAIN_FALSIFIER_AND_HELDOUT_EXIST',
       'scientific_authority':'NONE','model_execution':'NONE','side_effects':'LOCAL_REPORTS_ONLY',
       'unsafe_members':sum(not r['safe_to_consider'] for r in full)}
    if quantumdna is not None:
        result['quantumdna']=quantumdna_preflight(quantumdna)
    (outdir/'inventory.json').write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding='utf8')
    return result

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--archives',nargs='+',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--quantumdna',type=Path)
    a=p.parse_args()
    result=build_catalog(a.archives,a.output,a.quantumdna)
    print(canonical({'archives':len(result['archives']),'members':result['archive_members_indexed'],
      'unsafe':result['unsafe_members'], 'quantumdna':{k:v for k,v in result.get('quantumdna',{}).items() if k in ('rows_checked','defects','paired_trajectories')}}))
if __name__=='__main__':main()