#!/usr/bin/env python3
"""One-shot source-verified GitHub GraphQL signed candidate, no PR/main ref writes.

Expected source is the prior immutable PR head. A single ephemeral branch is used
for the GraphQL mutation; signed candidate and the old graph get immutable tag
references. The ephemeral branch is deleted even when an API call fails.
A separate exact-head compare-and-swap is required to promote any candidate.
"""
import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request

REPO = 'Aegis-Omega/AEGIS-OMEGA'
BASE = 'c6f4f2131ab06c5b20cfd3d0eafd99e3ca246bc8'
SOURCE = '7e08c2a9e872c79055c332332825bd94264b07a7'
SOURCE_TREE = 'd1f425bb590275bc95a5c9d3cab775bd27d5db97'
BRANCH = 'feat/repository-cartographer-v1'
WORKFLOW = '.github/workflows/aegis-pr795-signed-squash-once.yml'
SCRIPT = '.github/workflows/aegis-pr795-signed-squash-once.py'
TRIGGER_MESSAGE = 'ops(signing): stage one-time GitHub-verified exact-tree candidate'
STAGING = f'aegis-pr795-signed-staging-{SOURCE[:12]}'
BACKUP_TAG = f'ae-pr795-backup-{SOURCE[:12]}'
SIGNED_TAG = f'ae-pr795-github-signed-{SOURCE[:12]}'
API = 'https://api.github.com'
TOKEN = os.environ['GITHUB_TOKEN']


def git(*argv):
    return subprocess.check_output(['git', *argv])


def gh(method, path, body=None):
    url = path if path.startswith('https://') else API + path
    data = None if body is None else json.dumps(body, separators=(',', ':')).encode()
    request = urllib.request.Request(url, data=data, method=method, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Accept': 'application/vnd.github+json',
        'X-GitHub-Api-Version': '2022-11-28',
        'Content-Type': 'application/json',
        'User-Agent': 'AEGIS-exact-head-signed-candidate/1',
    })
    try:
        with urllib.request.urlopen(request, timeout=45) as response:
            return json.load(response)
    except urllib.error.HTTPError as exc:
        msg = exc.read(4096).decode('utf-8', 'replace')
        # GitHub API errors do not contain the Authorization header.
        raise RuntimeError(f'GitHub {method} {path.split("?")[0]} failed {exc.code}: {msg[:500]}') from None


def ensure_ref(path, expected):
    current = gh('GET', f'/repos/{REPO}/git/ref/{path}')
    actual = current.get('object', {}).get('sha')
    if actual != expected:
        raise RuntimeError(f'STALE_REF {path}: {actual} != {expected}')


def create_tag(name, sha):
    refpath = f'tags/{name}'
    try:
        ensure_ref(refpath, sha)
    except RuntimeError as exc:
        if 'failed 404' not in str(exc):
            raise
        gh('POST', f'/repos/{REPO}/git/refs', {'ref': f'refs/tags/{name}', 'sha': sha})
        ensure_ref(refpath, sha)


def get_tree_head(commit):
    data = gh('GET', f'/repos/{REPO}/git/commits/{commit}')
    return data['tree']['sha'], [p['sha'] for p in data['parents']], data.get('verification', {})


def build_payload():
    if git('rev-parse', 'HEAD').decode().strip() != os.environ['AEGIS_GITHUB_EVENT_SHA']:
        raise RuntimeError('EVENT_HEAD_NOT_CHECKED_OUT')
    if os.environ['AEGIS_GITHUB_REPOSITORY'] != REPO:
        raise RuntimeError('UNEXPECTED_REPOSITORY')
    if git('rev-parse', 'HEAD^').decode().strip() != SOURCE:
        raise RuntimeError('UNEXPECTED_WORKFLOW_PARENT')
    if git('log', '-1', '--format=%s').decode().strip() != TRIGGER_MESSAGE:
        raise RuntimeError('UNEXPECTED_TRIGGER_MESSAGE')
    actual_tree = git('rev-parse', f'{SOURCE}^{{tree}}').decode().strip()
    if actual_tree != SOURCE_TREE:
        raise RuntimeError('SOURCE_TREE_CHANGED')
    changed_workflow = git('diff', '--name-only', SOURCE, 'HEAD').decode().splitlines()
    if sorted(changed_workflow) != sorted([WORKFLOW, SCRIPT]):
        raise RuntimeError(f'TRANSPORT_WORKFLOW_NOT_ISOLATED {changed_workflow}')
    source_paths = git('diff', '--name-only', '--no-renames', BASE, SOURCE, '-z').split(b'\0')
    paths = sorted(p.decode('utf-8') for p in source_paths if p)
    if len(paths) != 78 or len(set(paths)) != len(paths):
        raise RuntimeError('UNEXPECTED_SOURCE_PATH_COUNT')
    changed_lines = git('diff', '--name-status', '--no-renames', BASE, SOURCE).decode().splitlines()
    if len(changed_lines) != 78 or any(not (x.startswith('A\t') or x.startswith('M\t')) for x in changed_lines):
        raise RuntimeError('SOURCE_DELTA_NOT_ADDITIONS_ONLY')
    additions = []
    for path in paths:
        source_mode = git('ls-tree', SOURCE, '--', path).decode().split()[0]
        prev_line = git('ls-tree', BASE, '--', path).decode()
        if prev_line:
            base_mode = prev_line.split()[0]
            if source_mode != base_mode:
                raise RuntimeError(f'MODE_DRIFT_REJECTED {path}')
        elif source_mode != '100644':
            raise RuntimeError(f'NONREGULAR_ADDITION_REJECTED {path}')
        content = git('show', f'{SOURCE}:{path}')
        additions.append({'path': path, 'contents': base64.b64encode(content).decode('ascii')})
    if sum(len(x['contents']) for x in additions) > 8_000_000:
        raise RuntimeError('GRAPHQL_PAYLOAD_LIMIT_REJECTED')
    return additions


def main():
    # Pure source verification BEFORE ANY REMOTE MUTATION.
    additions = build_payload()
    ensure_ref('heads/main', BASE)
    ensure_ref('heads/' + BRANCH, os.environ['AEGIS_GITHUB_EVENT_SHA'])
    ref_created = False
    try:
        # An immutable backup anchor is required BEFORE staging any signed rewrite.
        create_tag(BACKUP_TAG, os.environ['AEGIS_GITHUB_EVENT_SHA'])
        gh('POST', f'/repos/{REPO}/git/refs', {
            'ref': f'refs/heads/{STAGING}', 'sha': BASE})
        ref_created = True
        ensure_ref('heads/' + STAGING, BASE)
        query = ('mutation($input:CreateCommitOnBranchInput!){'
                 'createCommitOnBranch(input:$input){commit{oid}}}')
        variables = {'input': {
            'branch': {'repositoryNameWithOwner': REPO, 'branchName': STAGING},
            'expectedHeadOid': BASE,
            'message': {
                'headline': 'feat(optimus): signed exact-tree consolidation of PR 795',
                'body': ('Exact Git tree from source '+SOURCE+'; historical graph '
                         'retained under backup tag '+BACKUP_TAG+'. No production admission.'),
            },
            'fileChanges': {'additions': additions},
        }}
        response = gh('POST', '/graphql', {'query': query, 'variables': variables})
        if response.get('errors'):
            raise RuntimeError('GRAPHQL_SIGNING_FAILED: ' + str([x.get('message') for x in response['errors']])[:600])
        candidate = response['data']['createCommitOnBranch']['commit']['oid']
        ensure_ref('heads/' + STAGING, candidate)
        valid = False
        for _ in range(5):
            tree, parents, sig = get_tree_head(candidate)
            if tree != SOURCE_TREE or parents != [BASE]:
                raise RuntimeError('SIGNED_CANDIDATE_TREE_OR_PARENT_MISMATCH')
            if sig.get('verified') is True and sig.get('reason') == 'valid':
                valid = True
                break
            time.sleep(2)
        if not valid:
            raise RuntimeError('GITHUB_SIGNATURE_NOT_VERIFIED')
        # Tag the candidate before deleting the ephemeral branch, to keep reachability.
        create_tag(SIGNED_TAG, candidate)
        print('AEGIS_SIGNED_CANDIDATE_SHA=' + candidate, flush=True)
        print('AEGIS_SIGNED_CANDIDATE_TREE=' + tree, flush=True)
        print('AEGIS_SIGNED_CANDIDATE_BACKUP_TAG=' + BACKUP_TAG, flush=True)
        print('AEGIS_SIGNED_CANDIDATE_REF_TAG=' + SIGNED_TAG, flush=True)
        print('AEGIS_CANDIDATE_ONLY_NOT_PROMOTED_NO_PRODUCTION', flush=True)
    finally:
        if ref_created:
            # Never leave an unnecessary staging branch behind, including on failure.
            gh('DELETE', f'/repos/{REPO}/git/refs/heads/{STAGING}')


if __name__ == '__main__':
    try:
        main()
    except Exception as exc:
        print('AEGIS_SIGNED_CANDIDATE_FAILED: ' + str(exc), file=sys.stderr)
        raise SystemExit(1)
