"""AEGIS #758: digital diploid recombination on the EXISTING bounded program DSL.

Biology-inspired autosomal crossover, quantitative dominance and XX/XY-style
sex-chromosome inheritance. This is a search heuristic, NOT a model of humans.
No executable genetic payload, external data write, or independent admission.
"""
from __future__ import annotations

import hashlib
import json
import math
import random

SCHEMA = 'AEGIS_DIGITAL_DIPLOID_GENOME_V1'
LOCUS = ('alpha', 'beta', 'shrink')
BOUNDS = ((-8.,16.),(-40.,80.),(0.,1.))
REGULATOR_RANGE = (-1.,1.)
MUTATION_STEP = ((0.01,0.05,0.2,1.,2.),(0.01,0.1,0.5,2.,4.),(0.001,0.01,0.05,0.1))


def _float(x,lo,hi):
    if type(x) not in (float,int) or not math.isfinite(x) or not lo <= x <= hi:
        raise ValueError('GENOME_ALLELE_INVALID')
    return float(x)


def _norm(x):
    return round(float(x),6)


def validate(g):
    if not isinstance(g,dict) or set(g)!={'schema','autosomes','sex_chromosomes'} or g['schema']!=SCHEMA:
        raise ValueError('GENOME_SCHEMA_INVALID')
    hom=g['autosomes']
    if type(hom) is not list or len(hom)!=2 or any(type(h) is not list or len(h)!=3 for h in hom):
        raise ValueError('GENOME_DIPLOID_CHROMOSOMES_INVALID')
    for h in hom:
        for i,allele in enumerate(h):
            if type(allele) is not list or len(allele)!=2:
                raise ValueError('GENOME_DIPLOID_ALLELE_INVALID')
            _float(allele[0],*BOUNDS[i]);_float(allele[1],0,1)
    xy=g['sex_chromosomes']
    if type(xy) is not list or len(xy)!=2 or not all(type(c) is dict and set(c)=={'kind','regulator'} for c in xy):
        raise ValueError('GENOME_SEX_CHROMOSOMES_INVALID')
    if xy[0]['kind']!='X' or xy[1]['kind'] not in ('X','Y'):
        raise ValueError('GENOME_XY_INHERITANCE_INVALID')
    for c in xy:_float(c['regulator'],*REGULATOR_RANGE)
    return True


def founder(p,*,sex='XX'):
    if set(p)!={'schema','alpha','beta','shrink'} or p['schema']!='AEGIS_SAFE_SIMPLEX_DSL_V1':
        raise ValueError('GENOME_FOUNDER_PROGRAM_INVALID')
    values=[_float(p[k],*BOUNDS[i]) for i,k in enumerate(LOCUS)]
    if sex not in ('XX','XY'):raise ValueError('GENOME_FOUNDER_SEX_INVALID')
    g={'schema':SCHEMA,
       'autosomes':[[[_norm(v),0.5] for v in values] for _ in range(2)],
       'sex_chromosomes':[{'kind':'X','regulator':0.},
                          {'kind':sex[-1],'regulator':0.}]}
    validate(g);return g


def phenotype(g):
    validate(g)
    genes=[]
    for i in range(3):
        a,d1=g['autosomes'][0][i]
        b,d2=g['autosomes'][1][i]
        genes.append((a*d1+b*d2)/(d1+d2) if d1+d2 else (a+b)/2)
    # X/Y marker is inherited and auditable. Its bounded regulator affects
    # expression of the shrink locus, never gives authority or tool access.
    regulatory=sum(c['regulator'] for c in g['sex_chromosomes'])/2
    genes[2]+=regulatory*0.05
    genes=[_norm(min(hi,max(lo,v))) for v,(lo,hi) in zip(genes,BOUNDS)]
    return {'schema':'AEGIS_SAFE_SIMPLEX_DSL_V1',**dict(zip(LOCUS,genes))}


def _autosomal_gamete(g,rng):
    # One crossover between three linked loci; no whole-module replacement.
    cut=rng.choice((0,1,2,3))
    first=rng.randrange(2)
    return [g['autosomes'][first if i<cut else 1-first][i][:] for i in range(3)],{'start_homolog':first,'crossover_after':cut}


def reproduce(mother,father,*,seed):
    """Mendelian-style gametes; maternal X + paternal X/Y, bounded mutation."""
    validate(mother);validate(father)
    if mother['sex_chromosomes'][1]['kind']!='X' or father['sex_chromosomes'][1]['kind']!='Y':
        raise ValueError('GENOME_PARENTAL_KARYOTYPE_INVALID')
    if type(seed) is not int or seed<0 or seed>=2**64:raise ValueError('GENOME_SEED_INVALID')
    rng=random.Random(seed)
    m,mcross=_autosomal_gamete(mother,rng)
    f,fcross=_autosomal_gamete(father,rng)
    x=rng.choice(mother['sex_chromosomes']).copy()
    paternal=rng.choice(father['sex_chromosomes']).copy()
    child={'schema':SCHEMA,'autosomes':[m,f],'sex_chromosomes':[x,paternal]}
    # Gene-specific bounded mutation can alter a recessive allele without
    # instantly changing the expressed phenotype (latent diversity).
    chromosome=rng.randrange(2);locus=rng.randrange(3)
    mutation_type='dominance' if rng.random()<0.12 else 'allele_value'
    if mutation_type=='dominance':
        d=child['autosomes'][chromosome][locus][1]
        child['autosomes'][chromosome][locus][1]=_norm(min(1.,max(0.,d+rng.choice((-.1,-.025,.025,.1)))))
    else:
        v=child['autosomes'][chromosome][locus][0]
        lo,hi=BOUNDS[locus]
        child['autosomes'][chromosome][locus][0]=_norm(min(hi,max(lo,v+rng.choice(MUTATION_STEP[locus])*rng.choice((-1,1)))))
    if rng.random()<0.08:
        chrom=rng.randrange(2); reg=child['sex_chromosomes'][chrom]['regulator']
        child['sex_chromosomes'][chrom]['regulator']=_norm(min(1.,max(-1.,reg+rng.choice((-.1,-.02,.02,.1)))))
    validate(child)
    info={'maternal_crossover':mcross,'paternal_crossover':fcross,
          'sex_chromosomes':[s['kind'] for s in child['sex_chromosomes']],
          'mutated_homolog':chromosome,'mutated_locus':LOCUS[locus],
          'mutation_type':mutation_type,'seed':seed}
    return child,info


def genome_digest(g):
    validate(g)
    return hashlib.sha256(json.dumps(g,sort_keys=True,separators=(',',':'),allow_nan=False).encode()).hexdigest()
