#!/usr/bin/env python3
"""AEGIS Ω frontier comparison receipt: source-bounded, offline, fail-closed.

This is an advisory *evidence review*, not web browsing, attestation, agent
identity, a scientific proof, or permission to execute consequential actions.
It REUSES scripts/holon_eval.py for same-task paired outcomes and
scripts/holon_gate.py for safe artifact integrity checking.

Usage: python3 scripts/frontier_review.py --input review.json --root .
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import ipaddress
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from holon_gate import unique_json_object, reject_json_constant, verify_local_file
from holon_eval import compare, InvalidEvaluation

SCHEMA = 'aegis.holon.frontier/1'
SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
IDENT = re.compile(r'^[a-z][a-z0-9_-]{0,63}$')
DECISIONS = frozenset({'ADOPT', 'ADAPT', 'REJECT', 'INVESTIGATE'})
MAX_INPUT = 1024 * 1024


class InvalidFrontier(ValueError):
    pass


def require(ok: bool, reason: str) -> None:
    if not ok:
        raise InvalidFrontier(reason)


def fields(value, names: set[str], where: str) -> None:
    require(isinstance(value, dict) and set(value) == names, f'{where}: schema mismatch')


def bounded(value, field: str, maximum: int = 2000) -> str:
    require(isinstance(value, str) and 0 < len(value.strip()) <= maximum,
            f'{field}: bounded nonempty text required')
    return value


def day(value, field: str) -> date:
    require(isinstance(value, str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}', value) is not None,
            f'{field}: ISO calendar day required')
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise InvalidFrontier(f'{field}: invalid calendar date') from exc


def public_https(url: str) -> str:
    require(isinstance(url, str) and 12 <= len(url) <= 2048, 'source URL invalid')
    try:
        p = urlsplit(url)
        host = p.hostname
        require(p.scheme == 'https' and bool(host) and not p.username and not p.password
                and p.port in (None, 443) and not p.fragment, 'source must be public HTTPS URL')
        name = host.rstrip('.').lower()
        # IANA Special-Use Domain Names registry / RFC 6761, RFC 8375.
        # Syntactically valid HTTPS links into special-use namespaces are not
        # independently reachable public evidence, even with subdomains.
        reserved = ('localhost', 'localhost.localdomain', 'local', 'internal',
                    'example', 'example.com', 'example.net', 'example.org',
                    'invalid', 'test', 'onion', 'alt', 'home.arpa')
        require(not any(name == suffix or name.endswith('.' + suffix)
                        for suffix in reserved),
                'special-use source hostname is not public research evidence')
        try:
            ip = ipaddress.ip_address(name.strip('[]'))
        except ValueError:
            require('.' in name, 'source hostname needs a public DNS domain')
        else:
            require(ip.is_global, 'private or reserved IP is not external evidence')
        return name
    except (ValueError, AttributeError) as exc:
        raise InvalidFrontier('invalid HTTPS source URL') from exc


def assess(review: dict, root: Path, as_of: date | None = None) -> dict:
    """Strict advisory validation. Neither URL claims nor test results are authenticated."""
    names = {'schema', 'issue', 'operator_goal', 'baseline_sha', 'candidate_sha',
             'recorded_on', 'sources', 'decision', 'challenge', 'paired_eval'}
    fields(review, names, 'review')
    require(review['schema'] == SCHEMA, 'unsupported frontier schema')
    require(type(review['issue']) is int and review['issue'] > 0, 'positive GitHub issue required')
    bounded(review['operator_goal'], 'operator_goal', 4000)
    base, candidate = review['baseline_sha'], review['candidate_sha']
    require(isinstance(base, str) and SHA.fullmatch(base) is not None, 'baseline SHA invalid')
    require(isinstance(candidate, str) and SHA.fullmatch(candidate) is not None and base != candidate,
            'candidate SHA must be distinct 40-hex revision')
    recorded = day(review['recorded_on'], 'recorded_on')
    now = as_of if as_of is not None else datetime.now(timezone.utc).date()
    require(recorded <= now, 'receipt date in the future')
    sources = review['sources']
    require(isinstance(sources, list) and 2 <= len(sources) <= 12,
            '2..12 independent source entries required')
    seen_ids, domains = set(), set()
    stale = False
    inspected = 0
    for item in sources:
        fields(item, {'id', 'url', 'retrieved_on', 'inspection', 'capability', 'relevance'}, 'source')
        ident = item['id']
        require(isinstance(ident, str) and IDENT.fullmatch(ident) is not None
                and ident not in seen_ids, 'source identifier invalid or duplicate')
        seen_ids.add(ident)
        domains.add(public_https(item['url']))
        d = day(item['retrieved_on'], 'retrieved_on')
        require(d <= recorded, 'source retrieval date after comparison date')
        stale |= (now - d).days > 90
        require(item['inspection'] in ('inspected', 'identified'), 'source inspection state invalid')
        inspected += item['inspection'] == 'inspected'
        bounded(item['capability'], 'source.capability')
        bounded(item['relevance'], 'source.relevance')
    require(len(domains) >= 2, 'two distinct source hostnames required')
    decision = review['decision']
    fields(decision, {'kind', 'rationale', 'operator_value', 'risks'}, 'decision')
    require(decision['kind'] in DECISIONS, 'invalid transfer decision')
    for field in ('rationale', 'operator_value', 'risks'):
        bounded(decision[field], f'decision.{field}')
    challenge = review['challenge']
    fields(challenge, {'falsifier', 'replay_command', 'review_status'}, 'challenge')
    bounded(challenge['falsifier'], 'challenge.falsifier')
    bounded(challenge['replay_command'], 'challenge.replay_command', 1000)
    require(challenge['review_status'] == 'PENDING',
            'self-reported cross-model approval cannot authenticate a reviewer')
    paired = review['paired_eval']
    require(paired is None or isinstance(paired, dict), 'paired_eval must be object or null')
    result = None
    if paired is not None:
        fields(paired, {'file', 'sha256'}, 'paired_eval')
        require(isinstance(paired['file'], str) and isinstance(paired['sha256'], str)
                and DIGEST.fullmatch(paired['sha256']) is not None,
                'paired evaluation file/hash missing')
        status = verify_local_file(root, paired['file'], paired['sha256'])
        require(status == 'HASH_MATCH', f'paired evaluation integrity: {status}')
        # The local hash is an integrity check, not a signature or proof of truth.
        try:
            raw = (root / paired['file']).read_bytes()
            require(len(raw) <= MAX_INPUT, 'paired evaluation too large')
            evaluation = json.loads(raw.decode('utf-8'), object_pairs_hook=unique_json_object,
                                    parse_constant=reject_json_constant)
            require(isinstance(evaluation, dict), 'paired outcome is not a JSON object')
            require(evaluation.get('baseline_sha') == base
                    and evaluation.get('candidate_sha') == candidate,
                    'paired outcome revisions differ from research revisions')
            result = compare(evaluation, root)
        except (OSError, UnicodeError, ValueError, InvalidEvaluation) as exc:
            raise InvalidFrontier(f'paired evaluation replay rejected: {exc}') from exc
    blockers = []
    if stale:
        blockers.append('STALE_EXTERNAL_RESEARCH')
    if inspected < 2:
        blockers.append('TWO_SOURCES_NOT_INSPECTED')
    if paired is None and decision['kind'] in ('ADOPT', 'ADAPT'):
        blockers.append('MISSING_PAIRED_OUTCOME_EVALUATION')
    if (result is not None and decision['kind'] in ('ADOPT', 'ADAPT')
            and result['disposition'] not in (
            'PARETO_GAIN_REPORTED_UNATTESTED', 'TRADEOFF_REQUIRES_REVIEW')):
        blockers.append('MEASURED_OUTCOME_NOT_IMPROVED_OR_NOT_COMPLETE')
    # Non-adopting decisions can record useful falsifications without inventing gain.
    if blockers:
        disposition = 'HOLD_FOR_RESEARCH_OR_EVALUATION'
    elif decision['kind'] in ('REJECT', 'INVESTIGATE'):
        disposition = 'RESEARCH_ONLY_NO_ADOPTION'
    else:
        disposition = 'CANDIDATE_FOR_INDEPENDENT_REPLAY'
    return {'schema': 'aegis.holon.frontier.receipt/1', 'issue': review['issue'],
            'baseline_sha': base, 'candidate_sha': candidate,
            'decision': decision['kind'], 'sources_recorded': len(sources),
            'source_hostnames': sorted(domains), 'inspected_claims': inspected,
            'blockers': blockers, 'disposition': disposition,
            'paired_evaluation_disposition': result['disposition'] if result else None,
            'paired_cases': result['paired_cases'] if result else 0,
            'external_sources_authenticated': False,
            'source_inspection_independently_verified': False,
            'independent_replay': 'NOT_VERIFIED',
            'operator_authorization': 'NOT_VERIFIED', 'admission': 'NOT_ADMITTED',
            'method': 'read-only structured review; paired outcome replay delegates to existing holon_eval'}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', required=True)
    parser.add_argument('--root', default='.')
    args = parser.parse_args(argv)
    try:
        path = Path(args.input)
        require(path.stat().st_size <= MAX_INPUT, 'review input too large')
        payload = json.loads(path.read_text(encoding='utf-8'),
                             object_pairs_hook=unique_json_object,
                             parse_constant=reject_json_constant)
        output = assess(payload, Path(args.root).resolve())
        print(json.dumps(output, sort_keys=True, indent=2))
        return 0 if output['disposition'] in ('CANDIDATE_FOR_INDEPENDENT_REPLAY',
                                             'RESEARCH_ONLY_NO_ADOPTION') else 2
    except (OSError, ValueError, UnicodeError, AttributeError) as exc:
        print(json.dumps({'schema': 'aegis.holon.frontier.receipt/1',
                          'disposition': 'INVALID_INPUT', 'error': str(exc),
                          'operator_authorization': 'NOT_VERIFIED',
                          'admission': 'NOT_ADMITTED'}, sort_keys=True))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())