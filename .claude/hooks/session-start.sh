#!/bin/bash
# Session-start dependency installer + repository-universe/continuity hydration for Claude Code on the web.
# Idempotent where possible; universe hydration is evidence-critical and refreshes refs/history.
set -euo pipefail

if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

echo '{"async": true, "asyncTimeout": 300000}'

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
RUNTIME="$REPO/.aegis/runtime"
mkdir -p "$RUNTIME"

# Hydrate complete Git history and every reachable branch/tag before Claude forms
# repository-wide beliefs. main is canonical admission state, not the universe.
RAW_UNIVERSE="$RUNTIME/repo-universe.json"
RECON_UNIVERSE="$RUNTIME/repository-universe.v1.json"
PR_CENSUS="$RUNTIME/prs.json"
WORK_LINEAGE="${AEGIS_WORK_LINEAGE:-$RUNTIME/work-lineage.v1.json}"
WORK_REQUEST="${AEGIS_WORK_REQUEST:-$RUNTIME/work-request.v1.json}"
WORK_RESOLUTION="$RUNTIME/work-resolution.v1.json"

UNIVERSE_OK=0
if [ -x "$REPO/scripts/repo-universe.sh" ] || [ -f "$REPO/scripts/repo-universe.sh" ]; then
  echo "SessionStart: hydrating complete repository universe..."
  if bash "$REPO/scripts/repo-universe.sh" \
      --repo "$REPO" \
      --main origin/main \
      --refresh \
      --json "$RAW_UNIVERSE"; then
    UNIVERSE_OK=1
    python3 - "$RAW_UNIVERSE" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
print(
    "REPOSITORY_UNIVERSE_ACTIVE | "
    f"history_complete={str(p['history_complete']).lower()} | "
    f"branches={p['branch_count']} | "
    f"all_ref_commits={p['all_ref_commit_count']} | "
    f"main_commits={p['main_reachable_commit_count']} | "
    f"off_main_unique_commits={p['commits_not_reachable_from_main']} | "
    f"main={p['main_sha']}"
)
print(
    "EPISTEMIC_RULE: canonical main = admitted state; all fetched refs = searchable artifact universe. "
    "Never infer global absence from the current checkout or main alone."
)
PY
  else
    echo "REPOSITORY_UNIVERSE_INCOMPLETE: full-history/ref hydration failed; global absence claims and new-branch authorization are forbidden."
  fi
fi

# Build the provider-neutral WorkID graph when the local GitHub CLI can read PRs.
# Failure is not papered over: it leaves continuity unbound and branch creation denied.
LINEAGE_OK=0
if [ "$UNIVERSE_OK" -eq 1 ] \
    && command -v gh >/dev/null 2>&1 \
    && [ -f "$REPO/scripts/reconcile-repository-universe.py" ] \
    && [ -f "$REPO/scripts/build-work-lineage.py" ] \
    && [ -f "$REPO/.aegis/reconciliation/spines.v1.json" ]; then
  echo "SessionStart: resolving GitHub PR census into WorkID lineage..."
  if python3 - "$PR_CENSUS" <<'PY'
import json, subprocess, sys
out_path = sys.argv[1]
try:
    raw = subprocess.run(
        ["gh", "pr", "list", "--state", "all", "--limit", "1000", "--json",
         "number,state,isDraft,title,baseRefName,baseRefOid,headRefName,headRefOid,mergeable,url"],
        check=True, capture_output=True, text=True,
    ).stdout
    prs = json.loads(raw)
except Exception as exc:
    print(f"PR_CENSUS_INCOMPLETE: {exc}", file=sys.stderr)
    raise SystemExit(2)
if len(prs) >= 1000:
    print("PR_CENSUS_INCOMPLETE: hard limit reached", file=sys.stderr)
    raise SystemExit(2)
repo = subprocess.run(["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"], check=True, capture_output=True, text=True).stdout.strip()
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({
        "schema_version": "AEGIS_GITHUB_PR_CENSUS_V1",
        "repository": repo,
        "complete": True,
        "pull_requests": prs,
    }, f, sort_keys=True, indent=2)
    f.write("\n")
PY
  then
    if python3 "$REPO/scripts/reconcile-repository-universe.py" \
          --repo-universe "$RAW_UNIVERSE" \
          --prs "$PR_CENSUS" \
          --out "$RECON_UNIVERSE" >/dev/null \
       && python3 "$REPO/scripts/build-work-lineage.py" \
          --universe "$RECON_UNIVERSE" \
          --spines "$REPO/.aegis/reconciliation/spines.v1.json" \
          --out "$WORK_LINEAGE" >/dev/null; then
      LINEAGE_OK=1
      python3 - "$WORK_LINEAGE" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
print(
    "WORK_LINEAGE_ACTIVE | "
    f"work_items={len(p['work_items'])} | active_spine={len(p['active_spine'])} | "
    f"manifest={p['manifest_sha256'][:16]}"
)
PY
    fi
  fi
fi

if [ "$LINEAGE_OK" -ne 1 ]; then
  echo "WORK_CONTINUITY_INCOMPLETE: WorkID graph not established; new branch creation is forbidden."
elif [ -f "$WORK_REQUEST" ] && [ -f "$REPO/scripts/resolve-work-lineage.py" ]; then
  if python3 "$REPO/scripts/resolve-work-lineage.py" \
      --lineage "$WORK_LINEAGE" \
      --request "$WORK_REQUEST" \
      --out "$WORK_RESOLUTION" >/dev/null; then
    python3 - "$WORK_RESOLUTION" <<'PY'
import json, sys
p = json.load(open(sys.argv[1], encoding='utf-8'))
resolution = p['resolution']
if resolution == 'AMBIGUOUS_HALT':
    print(
        "WORK_CONTINUITY_AMBIGUOUS_HALT | "
        f"candidates={','.join(p['candidate_work_ids']) or 'none'} | "
        f"basis={','.join(p['evidence_basis']) or 'none'} | branch_creation=false"
    )
elif resolution == 'CREATE_NEW':
    print(
        "WORK_CONTINUITY_CREATE_NEW | discovery_complete=true | "
        f"resolution_digest={p['resolution_digest'][:16]} | branch_creation=true"
    )
else:
    print(
        "WORK_CONTINUITY_ACTIVE | "
        f"resolution={resolution} | work_id={p['work_id'] or 'none'} | "
        f"ref={p['continuation_ref'] or 'none'} | expected_head={p['expected_head'] or 'none'} | "
        "branch_creation=false"
    )
PY
  else
    echo "WORK_CONTINUITY_AMBIGUOUS_HALT: resolver failed closed; new branch creation is forbidden."
  fi
else
  echo "WORK_CONTINUITY_UNBOUND: no scheduler-bound WorkRequest; new branch creation is forbidden until ResolveLineage=CREATE_NEW."
fi

install_npm() {
  local dir="$REPO/$1"
  if [ -f "$dir/package.json" ] && [ ! -d "$dir/node_modules" ]; then
    echo "  installing $1..."
    npm install --prefix "$dir" --prefer-offline --no-audit --no-fund --silent
  fi
}

echo "SessionStart: installing npm deps..."

# Install in dependency order
install_npm packages/shared
install_npm sovereign-omega-v2
install_npm hub
install_npm platform-picker
install_npm hook-generator
install_npm content-calendar
install_npm cockpit
install_npm studio
install_npm enterprise
install_npm aegisomega-webgpu

echo "SessionStart: all deps ready."

# Python agent-layer deps (bridge + swarm). Idempotent: skip if already importable.
if [ -f "$REPO/sovereign-omega-v2/python/requirements.txt" ]; then
  if ! python -c "import anthropic" >/dev/null 2>&1; then
    echo "  installing python agent deps..."
    pip install -q -r "$REPO/sovereign-omega-v2/python/requirements.txt" 2>/dev/null || true
  fi
fi

# Ground truth — open every session knowing branch / main-drift / unpushed / membrane / live.
# Per WORKFLOW.md: no session starts blind; nothing is "done" until it is on main.
bash "$REPO/scripts/ground-truth.sh" 2>/dev/null || true
