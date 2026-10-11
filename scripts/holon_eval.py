#!/usr/bin/env python3
"""AEGIS Ω paired outcome comparator. Read-only, no agency or admission authority.

Compare identical task IDs under baseline and candidate at exact source revisions.
Artifact SHA-256 is local integrity evidence, NOT proof that results are true.
"""
import argparse
import json
import math
import re
from pathlib import Path
from holon_gate import unique_json_object, reject_json_constant, verify_local_file

SHA = re.compile(r'^[a-f0-9]{40}$')
METRICS = {'success', 'unsafe_actions', 'model_calls', 'latency_ms'}
ARMS = {'baseline', 'candidate'}
MAX = 512


class InvalidEvaluation(ValueError):
    pass


def need(ok, error):
    if not ok:
        raise InvalidEvaluation(error)


def check_number(v, key, integer=False):
    need(type(v) in (int, float), f'{key}: number required, not boolean')
    need(math.isfinite(v) and v >= 0, f'{key}: nonnegative finite value required')
    if integer:
        need(type(v) is int, f'{key}: integer required')


def parse_case(case, root):
    need(isinstance(case, dict) and set(case) == {'id', 'baseline', 'candidate'}, 'bad case fields')
    case_id = case['id']
    need(isinstance(case_id, str) and 1 <= len(case_id) <= 96, 'invalid case id')
    result = {'id': case_id}
    for arm in ('baseline', 'candidate'):
        item = case[arm]
        need(isinstance(item, dict) and set(item) == METRICS | {'artifact_file', 'artifact_sha256'}, f'{arm}: bad fields')
        need(type(item['success']) is bool, f'{arm}: success must be boolean')
        for key in ('unsafe_actions', 'model_calls', 'latency_ms'):
            check_number(item[key], key, integer=key != 'latency_ms')
        status = verify_local_file(root, item['artifact_file'], item['artifact_sha256'])
        need(status == 'HASH_MATCH', f'{case_id}/{arm}: evidence {status}')
        result[arm] = item
    return result


def compare(payload, root):
    need(isinstance(payload, dict) and set(payload) == {'schema', 'evaluation_id', 'goal', 'benchmark', 'baseline_sha', 'candidate_sha', 'cases'}, 'unexpected evaluation fields')
    need(payload['schema'] == 'aegis.holon.eval/1', 'unsupported schema')
    for field in ('evaluation_id', 'goal'):
        need(isinstance(payload[field], str) and payload[field].strip() and len(payload[field]) <= 512, f'{field}: missing/invalid')
    for arm in ('baseline_sha', 'candidate_sha'):
        need(isinstance(payload[arm], str) and SHA.fullmatch(payload[arm]), f'{arm}: invalid exact commit')
    need(payload['baseline_sha'] != payload['candidate_sha'], 'same source revision is not a comparison')
    bench = payload['benchmark']
    need(isinstance(bench, dict) and set(bench) == {'file', 'sha256', 'population'}, 'benchmark manifest fields')
    check_number(bench['population'], 'population', integer=True)
    need(1 <= bench['population'] <= 100000, 'invalid population')
    need(verify_local_file(root, bench['file'], bench['sha256']) == 'HASH_MATCH', 'benchmark manifest not hash-verified')
    rows = payload['cases']
    need(isinstance(rows, list) and 0 < len(rows) <= MAX, 'need 1..512 paired cases')
    need(len(rows) <= bench['population'], 'more cases than benchmark population')
    parsed = [parse_case(r, root) for r in rows]
    ids = [r['id'] for r in parsed]
    need(len(ids) == len(set(ids)), 'duplicate case ID')
    # Binding all cases to a separately hashed benchmark manifest prevents
    # silently changing the reference population, but does not prove sampling.
    manifest = json.loads((root / bench['file']).read_text(encoding='utf-8'),
                          object_pairs_hook=unique_json_object, parse_constant=reject_json_constant)
    need(isinstance(manifest, dict) and set(manifest) == {'case_ids'}, 'invalid benchmark manifest')
    all_ids = manifest['case_ids']
    need(isinstance(all_ids, list) and len(all_ids) == bench['population'] and
         all(isinstance(i, str) for i in all_ids) and len(set(all_ids)) == len(all_ids),
         'benchmark population mismatch')
    need(set(ids).issubset(all_ids), 'case not registered in benchmark')

    def aggregate(arm):
        obs = [r[arm] for r in parsed]
        return {'successes': sum(r['success'] for r in obs),
                'unsafe_actions': sum(r['unsafe_actions'] for r in obs),
                'model_calls': sum(r['model_calls'] for r in obs),
                'latency_ms': sum(r['latency_ms'] for r in obs)}
    a, b = aggregate('baseline'), aggregate('candidate')
    wins = sum(not r['baseline']['success'] and r['candidate']['success'] for r in parsed)
    losses = sum(r['baseline']['success'] and not r['candidate']['success'] for r in parsed)
    safety_regressions = sorted(r['id'] for r in parsed
        if r['candidate']['unsafe_actions'] > r['baseline']['unsafe_actions'])
    success_regressions = sorted(r['id'] for r in parsed
        if r['baseline']['success'] and not r['candidate']['success'])
    full = len(rows) == bench['population']
    pareto = (not safety_regressions and not success_regressions
              and b['model_calls'] <= a['model_calls'] and b['latency_ms'] <= a['latency_ms']
              and (wins > 0 or b['model_calls'] < a['model_calls'] or b['latency_ms'] < a['latency_ms']))
    if safety_regressions or success_regressions:
        judgement = 'REGRESSION_OBSERVED'
    elif not full:
        judgement = 'PARTIAL_BENCHMARK_NO_PROMOTION'
    elif pareto:
        judgement = 'PARETO_GAIN_REPORTED_UNATTESTED'
    elif wins > losses:
        judgement = 'TRADEOFF_REQUIRES_REVIEW'
    else:
        judgement = 'NO_VERIFIED_IMPROVEMENT'
    return {'schema': 'aegis.holon.eval.receipt/1',
            'evaluation_id': payload['evaluation_id'], 'goal': payload['goal'],
            'baseline_sha': payload['baseline_sha'], 'candidate_sha': payload['candidate_sha'],
            'benchmark_sha256': bench['sha256'], 'population': bench['population'],
            'paired_cases': len(parsed), 'coverage': len(parsed) / bench['population'],
            'baseline': a, 'candidate': b, 'wins': wins, 'losses': losses,
            'delta_success_percentage_points': 100 * (b['successes']-a['successes'])/len(parsed),
            'delta_model_calls': b['model_calls']-a['model_calls'],
            'delta_latency_ms': b['latency_ms']-a['latency_ms'],
            'safety_regression_cases': safety_regressions, 'success_regression_cases': success_regressions,
            'disposition': judgement, 'authority_effect': 'NONE',
            'independent_attestation': 'NOT_VERIFIED',
            'limitations': 'Caller-supplied measurements and SHA-256 artifacts are not independently authenticated; no blind holdout or statistical significance inferred.'}


def main(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--input', required=True)
    p.add_argument('--root', default='.')
    args = p.parse_args(argv)
    try:
        source = Path(args.input)
        need(source.stat().st_size <= 1024 * 1024, 'input exceeds 1 MiB')
        data = json.loads(source.read_text(encoding='utf-8'), object_pairs_hook=unique_json_object,
                          parse_constant=reject_json_constant)
        result = compare(data, Path(args.root).resolve())
        print(json.dumps(result, sort_keys=True, indent=2))
        return 0
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(json.dumps({'schema':'aegis.holon.eval.receipt/1','disposition':'INVALID_INPUT',
                          'error':str(exc),'authority_effect':'NONE'},sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
