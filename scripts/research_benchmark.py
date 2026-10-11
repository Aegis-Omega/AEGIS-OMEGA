#!/usr/bin/env python3
"""Offline, deterministic evaluation of research intake *structure*, not AI skill.

Compares the production scout against a documented 2-URL baseline on
100 generated, labelled synthetic packets. No network or model inference.
The labels are specified before either scorer runs. Never market these numbers
as general-task accuracy, real publisher authentication, or SOTA capability.
"""
from __future__ import annotations

import hashlib
import json
import math
from collections import Counter
from pathlib import Path
import importlib.util
import argparse

from research_intelligence import evaluate, ResearchError
from research_attestation import sign_capture

FIXTURE_VERSION = 'aegis.research.benchmark.v1'
PRIOR_SOURCE_BLOB = '595cd180aa4c1e8c73f7dd73d2496350923aeb81'
CLOCK = '2026-10-11T12:00:00Z'
BASE_SHA = '495bfd85d79abcb2b4f6898fe9c156488492426a'
TEST_KEY = bytes(range(32))  # Development-only reproducibility. NEVER use for real trust.
TRUST = {'synthetic.test': TEST_KEY}
import datetime as dt
TEST_NOW = dt.datetime(2026,10,11,12,tzinfo=dt.timezone.utc)


def source(sid: str, host: str, *, method: str = 'connector_capture',
           stamp: str = '2026-10-10T12:00:00Z', words: str | None = None) -> dict:
    content = words if words is not None else 'Documented capability claim for ' + sid
    return {'id': sid, 'url': f'https://{host}/doc', 'captured_at': stamp,
            'content': content, 'sha256': hashlib.sha256(content.encode()).hexdigest(),
            'acquisition': method}


def make_packet(case: str, index: int) -> dict:
    s = [source('one', 'developers.openai.com'), source('two', 'docs.langchain.com')]
    o = {'schema': 'aegis.research.packet.v1', 'task_id': f'bench_{index:03d}',
         'as_of_utc': CLOCK, 'repo_head': BASE_SHA, 'sources': s,
         'proposals': [{'id': 'change', 'local_component': 'agents/cognitive_pipeline.py',
                        'candidate': 'Evaluate trace-linked source research',
                        'mechanism': 'Ground study inputs in recorded captures',
                        'test_metric': 'Invalid ready classifications per hundred fixtures',
                        'falsifier': 'One invalid study becomes ready for independent testing',
                        'source_ids': ['one', 'two']}]}
    p = o['proposals'][0]
    if case == 'valid_openai_langchain':
        pass
    elif case == 'valid_openai_anthropic':
        s[1]['url'] = 'https://docs.anthropic.com/doc'
    elif case == 'valid_langchain_anthropic':
        s[0]['url'] = 'https://docs.langchain.com/doc'; s[1]['url'] = 'https://docs.anthropic.com/doc'
    elif case == 'valid_three_distinct':
        s.append(source('three', 'docs.anthropic.com')); p['source_ids'].append('three')
    elif case == 'valid_with_extra_manual':
        s.append(source('note', 'notes.example.net', method='manual_note')); p['source_ids'].append('note')
    elif case == 'two_manual_notes':
        s[0]['acquisition'] = s[1]['acquisition'] = 'manual_note'
    elif case == 'one_manual_note':
        s[1]['acquisition'] = 'manual_note'
    elif case == 'one_source':
        p['source_ids'] = ['one']
    elif case == 'same_publisher':
        s[1]['url'] = 'https://platform.openai.com/docs'
    elif case == 'mirrored_content':
        s[1]['content'] = s[0]['content']; s[1]['sha256'] = s[0]['sha256']
    elif case == 'old_source':
        s[1]['captured_at'] = '2025-01-01T00:00:00Z'
    elif case == 'future_source':
        s[1]['captured_at'] = '2026-11-01T00:00:00Z'
    elif case == 'unknown_publisher':
        s[1]['url'] = 'https://another.example.org/doc'
    elif case == 'github_mirror':
        s[1]['url'] = 'https://github.com/docs'
    elif case == 'tampered_source':
        s[1]['content'] += ' tampered'
    elif case == 'duplicate_ids':
        s[1]['id'] = s[0]['id']
    elif case == 'duplicate_refs':
        p['source_ids'].append('one')
    elif case == 'unknown_ref':
        p['source_ids'].append('missing')
    elif case == 'missing_falsifier':
        p['falsifier'] = ''
    elif case == 'bad_schema':
        o['schema'] = 'untrusted.version'
    else:
        raise ValueError(f'UNKNOWN_BENCHMARK_CLASS_{case}')
    # A synthetic receiver receipt, made by a TEST signer (not web traffic).
    # Sign only after mutation so the payload is structurally self-consistent;
    # tampered-source remains a negative because source checksum does not match.
    for v in s:
        if v['acquisition'] != 'connector_capture':
            continue
        host=v['url'].split('/')[2]
        snap={'schema':'aegis.research.capture.v1','url':v['url'],
              'hostname':host,'resolved_ip':'93.184.216.34',
              'captured_at':v['captured_at'],'http_status':200,
              'content_type':'text/plain',
              'tls_peer_cert_sha256':'a'*64,
              'full_body_sha256':hashlib.sha256(v['content'].encode()).hexdigest(),
              'excerpt_sha256':hashlib.sha256(v['content'].encode()).hexdigest(),
              'excerpt':v['content'],'full_bytes':len(v['content'].encode()),
              'truncated':False,
              'publisher_identity':'NOT_INDEPENDENTLY_AUTHENTICATED',
              'claim_truth':'NOT_VERIFIED','authority_effect':'NONE'}
        v['capture_receipt']=sign_capture(snap,TEST_KEY,'synthetic.test',
            binding={'task_id':o['task_id'],'repo_head':o['repo_head'],
                     'source_id':v['id']})
    return o


POSITIVE_CLASSES = ('valid_openai_langchain', 'valid_openai_anthropic',
                    'valid_langchain_anthropic', 'valid_three_distinct', 'valid_with_extra_manual')
NEGATIVE_CLASSES = ('two_manual_notes', 'one_manual_note', 'one_source',
                    'same_publisher', 'mirrored_content', 'old_source', 'future_source',
                    'unknown_publisher', 'github_mirror', 'tampered_source',
                    'duplicate_ids', 'duplicate_refs', 'unknown_ref', 'missing_falsifier',
                    'bad_schema')
ALL_CLASSES = POSITIVE_CLASSES + NEGATIVE_CLASSES


def corpus() -> list[tuple[str, str, bool, dict]]:
    # 20 mutation families x 5 repeats = 100. No hidden set or human labels.
    return [(f'{kind}-{rep}', kind, kind in POSITIVE_CLASSES,
             make_packet(kind, rep * len(ALL_CLASSES) + i))
            for rep in range(5) for i, kind in enumerate(ALL_CLASSES)]


def naive_two_urls(packet: dict) -> bool:
    """Explicit intentionally weak baseline: 2 distinct URL strings in source list."""
    return len({s.get('url') for s in packet.get('sources', [])}) >= 2


def scout_ready(packet: dict) -> tuple[bool, str]:
    try:
        response = evaluate(packet, trusted_keys=TRUST, verified_now=TEST_NOW)
        return response['proposals'][0]['status'] == 'READY_FOR_INDEPENDENT_TEST', response['proposals'][0]['reason']
    except ResearchError as error:
        return False, 'REJECTED:' + str(error)


def wilson(k: int, n: int) -> tuple[float, float]:
    if n <= 0:
        raise ValueError('EMPTY_DENOMINATOR')
    z = 1.959963984540054
    p = k / n
    a = 1 + z*z/n
    center = (p + z*z/(2*n))/a
    half = z * math.sqrt(p*(1-p)/n + z*z/(4*n*n))/a
    return round(max(0, center-half), 6), round(min(1, center+half), 6)


def measure(predict, trials) -> dict:
    tp = fp = tn = fn = 0
    reasons: Counter[str] = Counter()
    per_class: dict[str, dict[str, int]] = {}
    outcomes = []
    for caseid, caseclass, expected, packet in trials:
        raw = predict(packet)
        if isinstance(raw, tuple):
            predicted, reason = raw
        else:
            predicted, reason = raw, 'TWO_UNVERIFIED_URL_STRINGS'
        if type(predicted) is not bool:
            raise TypeError('INVALID_PREDICTION')
        key = 'tp' if predicted and expected else 'fp' if predicted else 'fn' if expected else 'tn'
        if key == 'tp': tp += 1
        elif key == 'fp': fp += 1
        elif key == 'fn': fn += 1
        else: tn += 1
        per_class.setdefault(caseclass, {'pass': 0, 'fail': 0})['pass' if predicted else 'fail'] += 1
        reasons[reason] += 1
        outcomes.append({'case': caseid, 'label_ready': expected,
                         'predicted_ready': predicted, 'classification': key, 'reason': reason})
    neg = fp+tn; pos = tp+fn
    return {'total':len(outcomes), 'confusion':{'tp':tp,'fp':fp,'tn':tn,'fn':fn},
            'false_ready_rate_on_negative_fixtures':round(fp/neg,6),
            'false_ready_wilson95':wilson(fp, neg),
            'recall_on_positive_fixtures':round(tp/pos,6),
            'recall_wilson95':wilson(tp,pos), 'per_class':per_class,
            'reason_counts':dict(sorted(reasons.items())), 'outcomes':outcomes}


def pinned_legacy_module(source_path: str):
    """Load the exact prior GitHub source blob; reject unknown comparator code."""
    raw = Path(source_path).read_bytes()
    blob = hashlib.sha1(b'blob ' + str(len(raw)).encode('ascii') + b'\0' + raw).hexdigest()
    if blob != PRIOR_SOURCE_BLOB:
        raise ValueError('LEGACY_BLOB_MISMATCH')
    spec = importlib.util.spec_from_file_location('aegis_previous_scout', source_path)
    if spec is None or spec.loader is None:
        raise ValueError('LEGACY_MODULE_UNLOADABLE')
    old = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(old)

    def previous(packet):
        try:
            # Prior version had no capture-receipt field. Strip only that new
            # schema extension; all historical structural fields remain equal.
            previous_input = dict(packet)
            previous_input['sources'] = [{k:v for k,v in src.items() if k!='capture_receipt'}
                                         for src in packet['sources']]
            answer = old.evaluate(previous_input)
            proposal = answer['proposals'][0]
            return proposal['status'] == 'READY_FOR_INDEPENDENT_TEST', proposal['reason']
        except old.ResearchError as error:
            return False, 'REJECTED:' + str(error)
    return previous


def report(legacy_source: str | None = None) -> dict:
    trials = corpus()
    before = measure(naive_two_urls, trials)
    after = measure(scout_ready, trials)
    output = {'schema':FIXTURE_VERSION, 'dataset':{
        'kind':'synthetic_public_development_corpus', 'cases':len(trials),
        'positive_cases':sum(c[2] for c in trials),
        'negative_cases':sum(not c[2] for c in trials),
        'mutation_families':len(ALL_CLASSES), 'repetitions_per_family':5,
        'held_out':'NO', 'independent_human_labels':'NO',
        'wilson_intervals':'DESCRIPTIVE_ONLY_NONINDEPENDENT_REPEATED_FAMILIES',
        'genuine_external_web_observation':'NO', 'model_or_agent_competitor':'NO',
        'task_completion_measure':'NOT_MEASURED',
        'label_definition':'Synthetically known structural readiness, NOT claim truth'},
        'baseline':before, 'scout':after,
        'false_ready_reduction_count':before['confusion']['fp']-after['confusion']['fp'],
        'benchmark_superiority':'NOT_ESTABLISHED_OUTSIDE_THIS_SYNTHETIC_CORPUS',
        'source_publication':'TEST_DATA_ONLY', 'authority_effect':'NONE',
        'external_research_verification':'NOT_PERFORMED'}
    if legacy_source is not None:
        output['actual_prior_scout'] = measure(pinned_legacy_module(legacy_source), trials)
        output['actual_prior_source_blob'] = PRIOR_SOURCE_BLOB
        output['actual_prior_false_ready_reduction'] = (
            output['actual_prior_scout']['confusion']['fp'] - after['confusion']['fp'])
    output['receipt_sha256'] = hashlib.sha256(json.dumps(output,sort_keys=True,
                                separators=(',',':'),ensure_ascii=False).encode()).hexdigest()
    return output


if __name__ == '__main__':
    cli = argparse.ArgumentParser(description='Synthetic, structural research intake benchmark')
    cli.add_argument('--legacy-source', help='Exact previous source file with pinned Git blob')
    args = cli.parse_args()
    print(json.dumps(report(args.legacy_source), sort_keys=True,indent=2))
