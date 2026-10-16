#!/usr/bin/env python3
"""Inventory tracked AEGIS source, SQL declarations and local remote refs.
No provider calls, credentials, database connections, deployment or inference.
Source declarations and branch presence never imply deployed functionality.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path
import re
import subprocess

ROOT = Path(__file__).resolve().parents[1]

def git(*args):
    return subprocess.check_output(['git', '-C', str(ROOT), *args], text=True).strip()

def inventory():
    paths = git('ls-files').splitlines()
    head = git('rev-parse', 'HEAD')
    tables, packages = [], []
    for name in paths:
        path = ROOT / name
        if name.startswith('supabase/migrations/') and name.endswith('.sql'):
            source = path.read_text()
            # Remove SQL comments before identifying declarations.
            source = re.sub(r'/\*.*?\*/', '', source, flags=re.S)
            source = re.sub(r'--[^\n]*', '', source)
            for match in re.finditer(r'\bcreate\s+table\s+(?:if\s+not\s+exists\s+)?([\w.\"]+)', source, re.I):
                tables.append({'table': match.group(1).strip('"'), 'migration': name,
                               'git_blob': git('hash-object', name), 'applied_to_production': 'UNKNOWN'})
        if name.endswith('package.json') and path.is_file():
            obj = json.loads(path.read_text())
            packages.append({'path': name, 'name': obj.get('name'),
                             'scripts': sorted(obj.get('scripts', {})),
                             'git_blob': git('hash-object', name)})
    refs = [dict(zip(('ref', 'sha'), line.split('\t'))) for line in
            git('for-each-ref', '--format=%(refname:short)%09%(objectname)', 'refs/remotes/origin').splitlines()]
    return {'schema_version': 1, 'repository': 'Aegis-Omega/AEGIS-OMEGA',
            'head_sha': head, 'tree_sha': git('rev-parse', 'HEAD^{tree}'),
            'worktree_status': git('status', '--porcelain'),
            'tracked_entries': len(paths),
            'top_level_file_counts': dict(sorted(collections.Counter(p.split('/')[0] for p in paths).items())),
            'sql_declarations': tables, 'packages': packages, 'remote_refs': refs,
            'native_clients': [p for p in paths if p.startswith('clients/') and p.endswith(('Package.swift', 'client.go', 'client.sh', 'Code.gs', 'setup.py'))],
            'coverage': {'branches': 'Locally fetched remote refs only; branch contents not all audited',
                         'database': 'Repository SQL declarations only; live schema and data UNKNOWN',
                         'deployments': 'Not inferred from source inventory'},
            'generator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = inventory()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'output': str(args.output), 'head': result['head_sha'],
                      'files': result['tracked_entries'], 'refs': len(result['remote_refs']),
                      'sql_declarations': len(result['sql_declarations']), 'packages': len(result['packages'])}))

if __name__ == '__main__':
    main()
