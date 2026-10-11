#!/usr/bin/env python3
"""AEGIS cross-modal experience evaluation: pure, zero-authority receipt reducer.

Receipts contain DECLARED measurements, not authenticated outcomes. This
validator never reads a source, judges artistic quality, or certifies SOTA.
"""
import argparse
import hashlib
import json
import math
import re
import sys

SCHEMA = 'aegis.experience-evaluation/1'
AXES = ('visual', 'typography', 'motion', 'sonic', 'narrative', 'product_utility',
        'usability', 'accessibility', 'performance', 'reliability',
        'privacy_safety', 'originality_rights', 'business_value')
HEX64 = re.compile(r'[0-9a-f]{64}\Z')
GIT_HEAD = re.compile(r'(?:[0-9a-f]{40}|[0-9a-f]{64})\Z')
IDENT = re.compile(r'[a-zA-Z][a-zA-Z0-9_.:-]{2,119}\Z')


def _assert(ok, message):
    if not ok:
        raise ValueError(message)


def _keys(obj, expected, label):
    _assert(type(obj) is dict, label + ' must be object')
    _assert(set(obj) == set(expected), label + ' keys mismatch: ' + str(sorted(set(obj) ^ set(expected))))


def _nonempty(value, label, maximum=1000):
    _assert(type(value) is str and 0 < len(value.strip()) <= maximum, label + ' invalid')


def _digest(value, label):
    _assert(type(value) is str and bool(HEX64.fullmatch(value)), label + ' must be sha256')


def evaluate(doc):
    _keys(doc, ('schema', 'task_id', 'candidate_sha256', 'baseline_sha256', 'source_head', 'axes',
                'comparison_scope', 'reviewer', 'authority_effect'), 'document')
    _assert(doc['schema'] == SCHEMA, 'unrecognized schema')
    _nonempty(doc['task_id'], 'task_id', 120)
    _digest(doc['candidate_sha256'], 'candidate')
    _digest(doc['baseline_sha256'], 'baseline')
    _assert(type(doc['source_head']) is str and GIT_HEAD.fullmatch(doc['source_head']),
            'exact source_head is required')
    _assert(doc['candidate_sha256'] != doc['baseline_sha256'], 'same candidate and baseline')
    _nonempty(doc['comparison_scope'], 'comparison_scope')
    _assert(doc['authority_effect'] == 'NONE', 'authority must remain NONE')
    _keys(doc['reviewer'], ('identity', 'relation', 'evidence'), 'reviewer')
    _nonempty(doc['reviewer']['identity'], 'reviewer identity', 160)
    _assert(doc['reviewer']['relation'] in ('SELF', 'INDEPENDENT_CLAIMED', 'UNKNOWN'),
            'review relation invalid')
    _assert(doc['reviewer']['evidence'] is None or
            (type(doc['reviewer']['evidence']) is str and HEX64.fullmatch(doc['reviewer']['evidence'])),
            'review evidence digest invalid')
    arr = doc['axes']
    _assert(type(arr) is list and len(arr) == len(AXES), 'all axes required exactly once')
    ids = [x.get('id') if type(x) is dict else None for x in arr]
    _assert(len(ids) == len(set(ids)) and set(ids) == set(AXES), 'axes missing, unknown or duplicate')
    results = []
    for axis in sorted(arr, key=lambda v: v['id']):
        name = axis['id']
        _keys(axis, ('id', 'state', 'rationale', 'metric', 'unit', 'direction',
                     'baseline', 'candidate', 'tolerance', 'evidence_sha256', 'standard_ref'),
              name)
        _assert(axis['state'] in ('MEASURED', 'UNMEASURED', 'NOT_APPLICABLE'), name + ' state')
        _nonempty(axis['rationale'], name + ' rationale')
        _nonempty(axis['standard_ref'], name + ' standard/source ref')
        if axis['state'] != 'MEASURED':
            _assert(all(axis[k] is None for k in
                        ('metric', 'unit', 'direction', 'baseline', 'candidate',
                         'tolerance', 'evidence_sha256')),
                    name + ': non-measured axis cannot carry fabricated measurement')
            results.append({'id': name, 'finding': axis['state']})
            continue
        _nonempty(axis['metric'], name + ' metric', 160)
        _nonempty(axis['unit'], name + ' unit', 80)
        _assert(axis['direction'] in ('HIGHER', 'LOWER'), name + ' direction')
        for key in ('baseline', 'candidate', 'tolerance'):
            n = axis[key]
            _assert(type(n) in (float, int) and math.isfinite(n), name + ' ' + key + ' not finite')
        _assert(axis['tolerance'] >= 0, name + ' negative tolerance')
        _digest(axis['evidence_sha256'], name + ' evidence')
        delta = axis['candidate'] - axis['baseline']
        advantage = delta if axis['direction'] == 'HIGHER' else -delta
        finding = 'IMPROVED' if advantage > axis['tolerance'] else (
            'REGRESSED' if advantage < -axis['tolerance'] else 'NO_DEMONSTRATED_GAIN')
        results.append({'id': name, 'finding': finding, 'advantage_in_metric_units': advantage})
    issues = [r for r in results if r['finding'] != 'IMPROVED']
    body = json.dumps(doc, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode('utf8')
    return {'schema': 'aegis.experience-structural-receipt/1',
            'manifest_sha256': hashlib.sha256(body).hexdigest(),
            'status': 'STRUCTURAL_VALIDATION_ONLY',
            'all_applicable_improved_on_declared_values': (
                any(r['finding'] == 'IMPROVED' for r in results) and
                not any(r['finding'] in ('REGRESSED', 'NO_DEMONSTRATED_GAIN', 'UNMEASURED')
                        for r in results)),
            'unresolved_or_regressed_axes': [r['id'] for r in issues],
            'axes': results, 'independent_measurements_authenticated': False,
            'standards_conformance_verified': False, 'world_best': 'NOT_ESTABLISHED',
            'authority_effect': 'NONE'}


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('manifest', nargs='?', default='-', help='JSON file or - for stdin')
    args = p.parse_args()
    try:
        with (sys.stdin if args.manifest == '-' else open(args.manifest, encoding='utf8')) as f:
            data = json.load(f)
        out = evaluate(data)
        print(json.dumps(out, sort_keys=True, indent=2))
        return 0
    except (ValueError, OSError, json.JSONDecodeError, TypeError) as e:
        print(json.dumps({'schema': 'aegis.experience-structural-receipt/1',
                          'status': 'REJECTED', 'reason': str(e),
                          'authority_effect': 'NONE', 'world_best': 'NOT_ESTABLISHED'}))
        return 2


if __name__ == '__main__':
    sys.exit(main())
