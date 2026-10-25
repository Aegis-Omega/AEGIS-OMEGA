"""Bounded autonomous search over *informational* TTL strategy genomes.

This actually generates/evaluates alternatives against the existing 19-role
mesh, retains every score and counterexample, and proposes an improvement.
It NEVER changes active routes or agent authority; it is not a hidden holdout.
"""
from __future__ import annotations
from typing import Any, Mapping
from agents.dendrite_mesh import DendriteEvent, digest
from agents.dendrite_system import system_mesh

SCHEMA='AEGIS_DENDRITE_ROUTE_SEARCH_V1'
# Explicit task objectives; these are fixtures and not independently measured user outcomes.
REQUIRED={
    'research': ('corpus_ingestor','ai_research','strategy'),
    'formal': ('applied_science','engineering','ai_safety'),
    'engineering': ('engineering','devex','product_management'),
    'security': ('cybersecurity','ai_safety','compliance'),
    'commerce': ('strategy','finance','sales'),
    'operations': ('platform_engineering','chronologist'),
}
ORIGINS={
    'research':'corpus_ingestor', 'formal':'applied_science',
    'engineering':'engineering', 'security':'cybersecurity',
    'commerce':'strategy','operations':'platform_engineering',
}

def search_routes(*, head: str, baseline_ttl: int=5) -> dict[str,Any]:
    """Enumerate TTL 0..8 by topic; reduce fanout without dropping objectives.

    Deterministic pure offline search, with a safety-isolated quarantine probe.
    Selection is an UNVERIFIED proposal and is not installed automatically.
    """
    mesh=system_mesh()
    if type(baseline_ttl) is not int or not 0<=baseline_ttl<=8:
        raise ValueError('ROUTE_BASELINE_INVALID')
    results=[]
    for topic, required in REQUIRED.items():
        event=DendriteEvent.create(origin=ORIGINS[topic],topic=topic,
                                  channel='CANDIDATE',source_head=head,
                                  source_record=digest({'topic':topic,'objective':required}),
                                  sequence=0,text='Synthetic routing objective, not research evidence')
        traces=[]
        for ttl in range(9):
            route=mesh.propagate(event,ttl=ttl)
            reached=set(route['delivered_roles'])
            missing=sorted(set(required)-reached)
            # Units here are message deliveries, not measured latency/dollars.
            traces.append({'ttl':ttl,'eligible':not missing,'missing':missing,
                           'deliveries':len(reached),'routing_receipt_hash':route['receipt_hash']})
        baseline=traces[baseline_ttl]
        passing=[x for x in traces if x['eligible']]
        chosen=min(passing,key=lambda x:(x['deliveries'],x['ttl'])) if passing else None
        proposals=({'from_ttl':baseline_ttl,'to_ttl':chosen['ttl'],
                    'delivery_delta':chosen['deliveries']-baseline['deliveries'],
                    'status':'NOT_ADMITTED'} if chosen and baseline['eligible'] and
                    chosen['deliveries']<baseline['deliveries'] else None)
        # Verify no quarantine leakage at ANY TTL. Topic owners may be ordinary
        # roles, so quarantine must instead originate from the existing
        # cybersecurity oversight role (except research, which starts in corpus).
        quarantine_origin='corpus_ingestor' if topic=='research' else 'cybersecurity'
        q=DendriteEvent.create(origin=quarantine_origin,topic=topic,
                              channel='QUARANTINE',source_head=head,
                              source_record=digest({'topic':topic,'quarantine':True}),
                              sequence=1,text='Quarantine routing invariant')
        allowed={name for name,node in mesh.nodes.items() if 'QUARANTINE' in node.channels}
        for ttl in range(9):
            qr=mesh.propagate(q,ttl=ttl)
            if set(qr['delivered_roles'])-allowed:
                raise ValueError('QUARANTINE_ROUTE_LEAK')
        results.append({'topic':topic,'required_roles':required,
                        'baseline':baseline,'search_trace':traces,
                        'candidate':proposals,'quarantine_invariant':'PASS',
                        'benchmark_authenticity':'SYNTHETIC_OBJECTIVES_ONLY'})
    body={'schema':SCHEMA,'baseline_ttl':baseline_ttl,'topics':results,
          'search_kind':'EXHAUSTIVE_TTL_ENUMERATION_NOT_MODEL_DISCOVERY',
          'authority_effect':'NONE','execution_effect':'NONE',
          'promotion':'DENIED','external_benchmark':'NOT_PERFORMED'}
    return {**body,'receipt_hash':digest(body)}
