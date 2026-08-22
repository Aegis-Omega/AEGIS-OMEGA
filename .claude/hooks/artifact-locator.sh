#!/usr/bin/env bash
set -u

# AEGIS artifact locator
# Purpose: prevent false global absence claims from a single worktree/ref.
# Evidence classes are deliberately distinct: a matching ref name is not proof that
# an implementation exists, and a current-worktree miss is never a global miss.

TERM_TO_FIND="${1:-}"
if [[ -z "$TERM_TO_FIND" ]]; then
  echo 'usage: artifact-locator.sh <term>' >&2
  exit 64
fi

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || true)"
if [[ -z "$ROOT" ]]; then
  echo 'AEGIS_ARTIFACT_SCAN_STATUS=INCOMPLETE reason=not-a-git-worktree'
  exit 4
fi
cd "$ROOT"

printf 'AEGIS_ARTIFACT_QUERY=%q\n' "$TERM_TO_FIND"
printf 'AEGIS_ARTIFACT_WORKTREE=%s\n' "$ROOT"
printf 'AEGIS_ARTIFACT_HEAD=%s\n' "$(git rev-parse HEAD 2>/dev/null || printf UNKNOWN)"
printf 'AEGIS_ARTIFACT_BRANCH=%s\n' "$(git branch --show-current 2>/dev/null || printf DETACHED)"

incomplete=0
implementation_hits=0
reference_hits=0

section() {
  printf '\n== %s ==\n' "$1"
}

# Refresh remote knowledge. A failed fetch means a negative conclusion cannot be global.
section 'REMOTE REFRESH'
if git fetch --all --prune --tags --quiet 2>/dev/null; then
  echo 'remote_refresh=OK'
else
  echo 'remote_refresh=FAILED'
  incomplete=1
fi

# Enumerate all locally known refs after refresh.
mapfile -t REFS < <(git for-each-ref --format='%(refname)' refs/heads refs/remotes refs/tags 2>/dev/null | sort -u)
if [[ ${#REFS[@]} -eq 0 ]]; then
  echo 'ref_enumeration=FAILED_OR_EMPTY'
  incomplete=1
fi

section 'REF NAME MATCHES'
ref_matches=()
while IFS= read -r ref; do
  [[ -n "$ref" ]] && ref_matches+=("$ref")
done < <(git for-each-ref --format='%(refname:short)' refs/heads refs/remotes refs/tags 2>/dev/null | grep -iF -- "$TERM_TO_FIND" || true)
if [[ ${#ref_matches[@]} -gt 0 ]]; then
  printf '%s\n' "${ref_matches[@]}"
  reference_hits=$((reference_hits + ${#ref_matches[@]}))
else
  echo 'NONE'
fi

section 'CURRENT WORKTREE PATH/CONTENT MATCHES'
worktree_out="$( { find . -path './.git' -prune -o -type f -print 2>/dev/null | grep -iF -- "$TERM_TO_FIND"; git grep -I -n -i -F -- "$TERM_TO_FIND" HEAD 2>/dev/null; } | sort -u | head -n 200 || true )"
if [[ -n "$worktree_out" ]]; then
  printf '%s\n' "$worktree_out"
  implementation_hits=$((implementation_hits + 1))
else
  echo 'NONE'
fi

section 'ALL-REF CONTENT MATCHES'
all_ref_out=''
if [[ ${#REFS[@]} -gt 0 ]]; then
  # git grep accepts revision/ref arguments and searches repository objects without checkout.
  all_ref_out="$(git grep -I -n -i -F -- "$TERM_TO_FIND" "${REFS[@]}" 2>/dev/null | head -n 400 || true)"
fi
if [[ -n "$all_ref_out" ]]; then
  printf '%s\n' "$all_ref_out"
  implementation_hits=$((implementation_hits + 1))
else
  echo 'NONE'
fi

section 'ALL-REF PATH MATCHES'
path_hits=0
for ref in "${REFS[@]}"; do
  matches="$(git ls-tree -r --name-only "$ref" 2>/dev/null | grep -iF -- "$TERM_TO_FIND" | head -n 20 || true)"
  if [[ -n "$matches" ]]; then
    while IFS= read -r path; do
      [[ -n "$path" ]] && printf '%s:%s\n' "$ref" "$path"
    done <<< "$matches"
    path_hits=1
  fi
done
if [[ $path_hits -eq 1 ]]; then
  implementation_hits=$((implementation_hits + 1))
else
  echo 'NONE'
fi

section 'COMMIT MESSAGE MATCHES'
commit_out="$(git log --all --decorate=short --oneline --regexp-ignore-case --fixed-strings --grep="$TERM_TO_FIND" 2>/dev/null | head -n 100 || true)"
if [[ -n "$commit_out" ]]; then
  printf '%s\n' "$commit_out"
  reference_hits=$((reference_hits + 1))
else
  echo 'NONE'
fi

section 'GITHUB PR MATCHES'
if command -v gh >/dev/null 2>&1; then
  pr_out="$(gh pr list --state all --search "$TERM_TO_FIND" --limit 100 --json number,title,state,headRefName,baseRefName,url 2>/dev/null || true)"
  if [[ -n "$pr_out" && "$pr_out" != '[]' ]]; then
    printf '%s\n' "$pr_out"
    reference_hits=$((reference_hits + 1))
  else
    echo 'NONE'
  fi
else
  echo 'INCOMPLETE: gh CLI unavailable; GitHub PR search not performed'
  incomplete=1
fi

section 'VERDICT'
if [[ $implementation_hits -gt 0 ]]; then
  echo 'AEGIS_ARTIFACT_SCAN_STATUS=IMPLEMENTATION_EVIDENCE_FOUND'
  echo 'rule=Inspect the matched ref/path before making implementation claims.'
  exit 0
fi

if [[ $reference_hits -gt 0 ]]; then
  echo 'AEGIS_ARTIFACT_SCAN_STATUS=NAMED_REFERENCE_FOUND'
  echo 'rule=A named branch/commit/PR is evidence of a reference, NOT evidence that implementation content exists. Inspect that ref before claiming either existence or absence.'
  exit 0
fi

if [[ $incomplete -ne 0 ]]; then
  echo 'AEGIS_ARTIFACT_SCAN_STATUS=INCOMPLETE'
  echo 'rule=You MUST NOT say "does not exist". Say what scopes were searched and which scope could not be checked.'
  exit 4
fi

echo 'AEGIS_ARTIFACT_SCAN_STATUS=NO_MATCHES_IN_COMPLETE_REPO_SCAN'
echo 'rule=This supports only: "no matching artifact was found in the refreshed Git repository/PR scope". It does NOT prove absence from Drive, chat history, external corpora, or deleted/unfetched history.'
exit 3
