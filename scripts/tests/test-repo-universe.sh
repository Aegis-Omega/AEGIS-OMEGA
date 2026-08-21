#!/usr/bin/env bash
set -euo pipefail

ROOT="$(git rev-parse --show-toplevel)"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

repo="$TMP/repo"
out="$TMP/universe.json"
mkdir -p "$repo"
git -C "$repo" init -q -b main
git -C "$repo" config user.email test@example.com
git -C "$repo" config user.name test

printf '0\n' > "$repo/base.txt"
git -C "$repo" add base.txt
git -C "$repo" commit -q -m base

# branch alpha contributes two commits not reachable from main
git -C "$repo" checkout -q -b alpha
printf 'a1\n' > "$repo/a.txt"
git -C "$repo" add a.txt
git -C "$repo" commit -q -m a1
printf 'a2\n' >> "$repo/a.txt"
git -C "$repo" commit -qam a2

# branch beta forks main and contributes one independent commit
git -C "$repo" checkout -q main
git -C "$repo" checkout -q -b beta
printf 'b1\n' > "$repo/b.txt"
git -C "$repo" add b.txt
git -C "$repo" commit -q -m b1

git -C "$repo" checkout -q main

bash "$ROOT/scripts/repo-universe.sh" --repo "$repo" --main main --json "$out"

python3 - "$out" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
assert p['schema_version'] == 'AEGIS_REPO_UNIVERSE_V1'
assert p['branch_count'] == 3, p
assert p['commits_not_reachable_from_main'] == 3, p
assert p['all_ref_commit_count'] == 4, p
assert p['main_reachable_commit_count'] == 1, p
by_name = {x['branch']: x for x in p['branches']}
assert by_name['alpha']['ahead_of_main'] == 2, by_name
assert by_name['beta']['ahead_of_main'] == 1, by_name
assert by_name['main']['ahead_of_main'] == 0, by_name
assert p['history_complete'] is True, p
print('repo-universe fixture: PASS')
PY
