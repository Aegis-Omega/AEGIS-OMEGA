#!/usr/bin/env python3
"""AEGIS Ω: provider-neutral, read-only work arbitration and evidence admission preflight.

No API tokens, accounts, GitHub, paid models or implicit writes. Inputs are untrusted
claims: independent source authentication and protected-main CI remain external.
Usage: python3 scripts/holon_gate.py --input snapshot.json --actor GPT-6 --root .
"""
import argparse
import hashlib
import json
import re
import os
import stat
from pathlib import Path, PurePosixPath

SHA = re.compile(r'^[0-9a-f]{40}$')
DIGEST = re.compile(r'^[0-9a-f]{64}$')
STATES = {'OPEN', 'CLAIMED', 'IN_PROGRESS', 'REVIEW', 'BLOCKED', 'REPORTED_LANDED'}
PRIORITY = {'p0': 0, 'p1': 1, 'p2': 2, 'p3': 3}
MAX_ARTIFACT = 16 * 1024 * 1024


class InvalidSnapshot(ValueError):
    pass


def unique_json_object(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise InvalidSnapshot('duplicate JSON key: ' + key)
        out[key] = value
    return out


def reject_json_constant(name):
    raise InvalidSnapshot('unsupported JSON constant: ' + name)


def check(condition, msg):
    if not condition:
        raise InvalidSnapshot(msg)


def path_tokens(path):
    check(isinstance(path, str) and bool(path) and len(path) < 512, 'invalid path')
    path = path.replace('\\', '/')
    p = PurePosixPath(path)
    check(not p.is_absolute() and all(t not in ('.', '..') for t in path.split('/'))
          and ':' not in path and not path.startswith('~'), 'unsafe path: ' + path)
    return tuple(p.parts)


def path_overlaps(a, b):
    aa, bb = path_tokens(a), path_tokens(b)
    # Files and directory scopes; exact matching on components prevents false
    # positives such as scripts/agent.py vs scripts/agent.py.bak.
    return aa[:len(bb)] == bb or bb[:len(aa)] == aa


def verify_local_file(root, name, digest):
    if not isinstance(name, str) or not DIGEST.fullmatch(str(digest)):
        return 'NO_HASH_OR_FILE'
    try:
        path_tokens(name)
        target = (root / name).resolve(strict=True)
        if not target.is_relative_to(root.resolve()) or not target.is_file():
            return 'OUTSIDE_WORKSPACE'
        if target.stat().st_size > MAX_ARTIFACT:
            return 'ARTIFACT_TOO_LARGE'
        h = hashlib.sha256()
        with target.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                h.update(chunk)
        return 'HASH_MATCH' if h.hexdigest() == digest else 'HASH_MISMATCH'
    except (OSError, ValueError, InvalidSnapshot):
        return 'UNAVAILABLE_OR_UNSAFE'


def read_verified_local_file(root, name, digest, max_bytes=MAX_ARTIFACT):
    """Return only SHA-256-verified bytes from one pinned file descriptor.

    POSIX dirfd + O_NOFOLLOW traversal refuses symlink redirection. This is
    local artifact integrity, NOT a signature or independent source proof.
    Unsupported platforms fail closed.
    """
    if (not isinstance(name, str) or not isinstance(digest, str)
            or DIGEST.fullmatch(digest) is None):
        return 'NO_HASH_OR_FILE', None
    if type(max_bytes) is not int or not 1 <= max_bytes <= MAX_ARTIFACT:
        return 'UNAVAILABLE_OR_UNSAFE', None
    if (not name or '\\' in name or ':' in name or name.startswith(('~', '/'))
            or any(part in ('', '.', '..') for part in name.split('/'))):
        return 'OUTSIDE_WORKSPACE', None
    parts = PurePosixPath(name).parts
    owned = []
    try:
        directory_flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
        rootfd = os.open(str(Path(root).resolve(strict=True)), directory_flags)
        owned.append(rootfd)
        for part in parts[:-1]:
            child = os.open(part, directory_flags, dir_fd=owned[-1])
            owned.append(child)
        filefd = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=owned[-1])
        owned.append(filefd)
        info = os.fstat(filefd)
        if not stat.S_ISREG(info.st_mode):
            return 'UNAVAILABLE_OR_UNSAFE', None
        if info.st_size > max_bytes:
            return 'ARTIFACT_TOO_LARGE', None
        with os.fdopen(os.dup(filefd), 'rb') as stream:
            raw = stream.read(max_bytes + 1)
        if len(raw) > max_bytes:
            return 'ARTIFACT_TOO_LARGE', None
        if hashlib.sha256(raw).hexdigest() != digest:
            return 'HASH_MISMATCH', None
        return 'HASH_MATCH', raw
    except (OSError, ValueError, AttributeError):
        return 'UNAVAILABLE_OR_UNSAFE', None
    finally:
        for fd in reversed(owned):
            os.close(fd)


def cycle_ids(by_id):
    """Iterative Kahn pruning; conservatively block cycles and descendants.

    No recursion-depth failure for large issue DAGs. A dependent of a cyclic
    task cannot be scheduled even if the descendant itself is not on the loop.
    """
    remaining = {i: len(t['depends_on']) for i, t in by_id.items()}
    children = {i: [] for i in by_id}
    for i, t in by_id.items():
        for dependency in t['depends_on']:
            children[dependency].append(i)
    queue = sorted(i for i, count in remaining.items() if count == 0)
    position = 0
    while position < len(queue):
        known = queue[position]
        position += 1
        for child in children[known]:
            remaining[child] -= 1
            if remaining[child] == 0:
                queue.append(child)
    return {i for i, count in remaining.items() if count > 0}


def validate(snapshot):
    check(isinstance(snapshot, dict), 'root must be object')
    tasks = snapshot.get('tasks')
    check(isinstance(tasks, list) and len(tasks) <= 2000, 'tasks must be list <=2000')
    by_id = {}
    for t in tasks:
        check(isinstance(t, dict), 'task must be object')
        tid = t.get('id')
        check(isinstance(tid, str) and 1 <= len(tid) <= 128, 'invalid id')
        check(tid not in by_id, 'duplicate task id: ' + tid)
        check(isinstance(t.get('objective'), str) and t['objective'].strip(), 'missing objective: ' + tid)
        check(isinstance(t.get('done_when'), str) and t['done_when'].strip(), 'missing done_when: ' + tid)
        check(t.get('priority') in PRIORITY, 'bad priority: ' + tid)
        check(t.get('state') in STATES, 'bad task state: ' + tid)
        check(isinstance(t.get('depends_on'), list) and all(isinstance(d, str) for d in t['depends_on']), 'bad dependencies: ' + tid)
        check(isinstance(t.get('paths'), list), 'paths must be list: ' + tid)
        for p in t['paths']:
            path_tokens(p)
        owner = t.get('claimed_by')
        check(owner is None or (isinstance(owner, str) and bool(owner.strip())
                               and len(owner) <= 128), 'bad claim: ' + tid)
        if t['state'] in ('CLAIMED', 'IN_PROGRESS', 'REVIEW'):
            check(owner is not None, 'active task without claim owner: ' + tid)
        by_id[tid] = t
    for tid, t in by_id.items():
        for d in t['depends_on']:
            check(d in by_id, 'unknown dependency: ' + tid + ' -> ' + d)
            check(d != tid, 'self dependency: ' + tid)
    submissions = snapshot.get('submissions', [])
    check(isinstance(submissions, list), 'submissions must be list')
    sub_by_id = {}
    for s in submissions:
        check(isinstance(s, dict), 'submission must be object')
        tid = s.get('task_id')
        check(tid in by_id and tid not in sub_by_id, 'invalid/duplicate submission: ' + str(tid))
        check(isinstance(s.get('author'), str) and s['author'], 'author missing: ' + str(tid))
        check(isinstance(s.get('source_sha'), str) and SHA.fullmatch(s['source_sha']), 'invalid exact head: ' + str(tid))
        sub_by_id[tid] = s
    return by_id, sub_by_id


def evaluate(snapshot, root, actor):
    by_id, submissions = validate(snapshot)
    cycles = cycle_ids(by_id)
    # Scope collision is also a pre-claim hazard: OPEN work overlapping an
    # already active claim must be held before a second agent starts editing.
    # Two active collisions block both; path claims are never auto-authorized.
    collision = {tid: set() for tid in by_id}
    active_states = {'CLAIMED', 'IN_PROGRESS', 'REVIEW'}
    all_tasks = sorted(by_id.items())
    for n, (i, a) in enumerate(all_tasks):
        for j, b in all_tasks[n + 1:]:
            if a['state'] not in active_states and b['state'] not in active_states:
                continue
            if any(path_overlaps(x, y) for x in a['paths'] for y in b['paths']):
                collision[i].add(j)
                collision[j].add(i)
    result = []
    for tid, t in sorted(by_id.items(), key=lambda it: (PRIORITY[it[1]['priority']], it[0])):
        reasons = []
        if tid in cycles:
            reasons.append('CYCLIC_DEPENDENCY')
        if not t['paths']:
            reasons.append('WORK_SCOPE_UNDECLARED')
        if t['depends_on']:
            # Task status from JSON is a reported claim. Do not treat it as
            # cryptographic admission; depends-on tasks need a trusted external
            # marker before this tool can recommend starting successors.
            reasons.append('DEPENDENCIES_NOT_INDEPENDENTLY_ADMITTED')
        if collision[tid]:
            reasons.append('OVERLAPPING_ACTIVE_SCOPES')
        owner = t.get('claimed_by')
        if owner and owner != actor:
            reasons.append('COORDINATE_WITH_CLAIM_OWNER')
        sub = submissions.get(tid)
        evidence = 'NO_SUBMISSION'
        if sub:
            if owner and sub['author'] != owner:
                reasons.append('SUBMISSION_NOT_FROM_CLAIM_OWNER')
            evidence = verify_local_file(root, sub.get('artifact_file'), sub.get('artifact_sha256'))
            if evidence != 'HASH_MATCH':
                reasons.append('ARTIFACT_NOT_REPLAYED')
            tests = sub.get('tests')
            if not isinstance(tests, list) or not tests or any(not isinstance(v, dict) or
                v.get('source_sha') != sub['source_sha'] or v.get('result') != 'PASS' for v in tests):
                reasons.append('TEST_EVIDENCE_MISSING_OR_STALE')
            # Reviewer identity strings are claims, not independently proven IDs.
            review = sub.get('review')
            reviewer = review.get('reviewer') if isinstance(review, dict) else None
            if (not isinstance(reviewer, str) or not reviewer.strip()
                    or reviewer == sub['author']
                    or review.get('verdict') != 'ACCEPT'
                    or review.get('source_sha') != sub['source_sha']):
                reasons.append('INDEPENDENT_REVIEW_NOT_RECORDED')
            if t['state'] == 'REPORTED_LANDED':
                reasons.append('LANDING_REPORTED_NOT_ATTESTED')
            else:
                reasons.append('PROTECTED_MAIN_ADMISSION_UNVERIFIED')
        if t['state'] == 'BLOCKED':
            reasons.append('TASK_REPORTED_BLOCKED')
        # This offline tool never awards DONE. Exact source and hash attest
        # only local integrity; GitHub merge/check provenance remains external.
        readiness = ('BLOCKED' if any(r in reasons for r in (
                         'CYCLIC_DEPENDENCY', 'DEPENDENCIES_NOT_INDEPENDENTLY_ADMITTED', 'TASK_REPORTED_BLOCKED'))
                     else 'COORDINATE' if collision[tid] or (owner and owner != actor)
                     else 'REVIEW_READY_NOT_ADMITTED' if sub and evidence == 'HASH_MATCH' and
                         all(r not in reasons for r in ('TEST_EVIDENCE_MISSING_OR_STALE', 'INDEPENDENT_REVIEW_NOT_RECORDED', 'SUBMISSION_NOT_FROM_CLAIM_OWNER', 'WORK_SCOPE_UNDECLARED'))
                     else 'AVAILABLE' if not reasons else 'EVIDENCE_NEEDED')
        result.append({'id': tid, 'priority': t['priority'], 'assigned_to': owner,
                       'readiness': readiness, 'evidence': evidence,
                       'scope_collisions': sorted(collision[tid]), 'blockers': reasons,
                       'source': t.get('source')})
    return {'schema': 'AEGIS_HOLON_PRE_ADMISSION_V1', 'actor': actor,
            'authority_effect': 'NONE', 'admitted_tasks': 0,
            'truth_boundary': 'Claims and reviewer strings are untrusted; admission requires external signed protected-main evidence.',
            'tasks': result}


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--input', required=True, help='provider-neutral JSON task snapshot')
    ap.add_argument('--root', default='.', help='read-only artifact root')
    ap.add_argument('--actor', required=True, help='caller/model claim, not verified identity')
    args = ap.parse_args(argv)
    try:
        if Path(args.input).stat().st_size > 1024 * 1024:
            raise InvalidSnapshot('input exceeds 1 MiB')
        with open(args.input, encoding='utf-8') as f:
            data = json.load(f, object_pairs_hook=unique_json_object,
                             parse_constant=reject_json_constant)
        out = evaluate(data, Path(args.root), args.actor)
        print(json.dumps(out, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    except (InvalidSnapshot, ValueError, OSError, json.JSONDecodeError) as e:
        print(json.dumps({'schema': 'AEGIS_HOLON_PRE_ADMISSION_V1', 'error': str(e),
                          'disposition': 'INVALID_INPUT', 'authority_effect': 'NONE'}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
