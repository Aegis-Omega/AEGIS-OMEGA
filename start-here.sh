#!/usr/bin/env bash
# AEGIS Ω session entrypoint. Reuses the existing 8-gate contract and 14-suite CI.
# Default mode is read-only and does NOT install dependencies or trigger CI.
set -euo pipefail

ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
GATES_DOC="$ROOT/sovereign-omega-v2/.claude/commands/run-gates.md"
WORKFLOW="$ROOT/.github/workflows/repository-verification.yml"
COLLECTOR="$ROOT/scripts/repository_verification.py"
MEMBRANE="$ROOT/sovereign-omega-v2/scripts/verify-hashes.mjs"

usage() {
  printf 'Usage: bash start-here.sh [--inspect|--gates|--help]\n'
  printf '  --inspect  Validate existing contracts only (default, no test execution).\n'
  printf '  --gates    Run the existing eight TypeScript gates in strict order.\n'
  printf '             This runs LOCAL tests, typecheck and build; never deploys.\n'
  printf '  Corpus:    .github/workflows/repository-verification.yml (14 named suites).\n'
}

mode="${1:---inspect}"
if [[ $# -gt 1 ]]; then usage >&2; exit 2; fi
case "$mode" in
  --help|-h) usage; exit 0 ;;
  --inspect|--gates) ;;
  *) usage >&2; exit 2 ;;
esac

for file in "$GATES_DOC" "$WORKFLOW" "$COLLECTOR" "$MEMBRANE"; do
  if [[ ! -f "$file" ]]; then
    printf 'HOLD: missing canonical dependency %s\n' "${file#"$ROOT/"}" >&2
    exit 2
  fi
done

# These are the exact commands already defined in .claude/commands/run-gates.md.
# Reject documentation drift rather than silently inventing replacement gates.
GATE_CMDS=(
  'npm run test -- --reporter=verbose test/unit/jcs.test.ts'
  'npm run test -- test/unit/sequence.test.ts'
  'npm run test -- test/unit/immutable.test.ts'
  'npm run test -- test/unit/reducer.test.ts'
  'npm run test -- test/unit/vcg.test.ts'
  'npm run test -- test/unit/gate.test.ts'
  'npm run test -- test/integration/replay.test.ts test/integration/pipeline.test.ts'
  'npm run test && npm run typecheck && npm run build'
)
for idx in "${!GATE_CMDS[@]}"; do
  gate="$((idx+1))"
  if ! grep -Fxq "Gate $gate: \`${GATE_CMDS[$idx]}\`" "$GATES_DOC"; then
    printf 'HOLD: Gate %s command differs from canonical %s\n' "$gate" "${GATES_DOC#"$ROOT/"}" >&2
    exit 2
  fi
done

# The canonical gate commands must point to actual tracked test entrypoints.
# A missing test source is not evidence that the corresponding gate is healthy.
GATE_TEST_FILES=(
  test/unit/jcs.test.ts
  test/unit/sequence.test.ts
  test/unit/immutable.test.ts
  test/unit/reducer.test.ts
  test/unit/vcg.test.ts
  test/unit/gate.test.ts
  test/integration/replay.test.ts
  test/integration/pipeline.test.ts
)
for path in "${GATE_TEST_FILES[@]}"; do
  if [[ ! -f "$ROOT/sovereign-omega-v2/$path" ]]; then
    printf 'HOLD: missing canonical gate test %s\n' "$path" >&2
    exit 2
  fi
done

# Count definitions in the existing GitHub Actions workflow, not executed tests.
suite_count=$(grep -Ec '^[[:space:]]+run_suite[[:space:]]' "$WORKFLOW" || true)
if [[ "$suite_count" != 14 ]]; then
  printf 'HOLD: expected 14 named repository suites, found %s; inspect workflow drift\n' "$suite_count" >&2
  exit 2
fi
# The named suite invocations and aggregate's required-suite list must agree.
# A missing required suite is a HOLD even if the workflow still has 14 calls.
declared=$(sed -nE 's/^[[:space:]]+run_suite[[:space:]]+([a-zA-Z0-9_-]+)[[:space:]].*/\1/p' "$WORKFLOW" | LC_ALL=C sort)
required=$(sed -nE 's/^[[:space:]]+--required-suite[[:space:]]+([a-zA-Z0-9_-]+).*/\1/p' "$WORKFLOW" | LC_ALL=C sort)
if [[ "$declared" != "$required" ]] || [[ "$(printf '%s\n' "$declared" | uniq | wc -l | tr -d ' ')" != "$suite_count" ]]; then
  echo 'HOLD: defined and required suite IDs differ or are duplicated' >&2
  exit 2
fi
printf 'AEGIS_BOOTSTRAP_CONTRACT=PASS gates=8 suites=%s\n' "$suite_count"
if git -C "$ROOT" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  printf 'HEAD=%s\n' "$(git -C "$ROOT" rev-parse HEAD)"
  if [[ -n "$(git -C "$ROOT" status --porcelain)" ]]; then
    printf 'WORKTREE=DIRTY (local results are NOT exact-HEAD receipts)\n'
  else
    printf 'WORKTREE=CLEAN\n'
  fi
else
  printf 'HEAD=UNKNOWN (not a Git checkout)\n'
fi

if [[ "$mode" == --inspect ]]; then
  printf 'EXECUTION=NOT_RUN (no package installation, paid provider calls or GitHub workflow dispatch)\n'
  printf 'CORPUS_TEST_COUNT=UNKNOWN_ON_THIS_HEAD (historical PR #248 counts do not transfer)\n'
  exit 0
fi

if ! command -v node >/dev/null 2>&1 || ! command -v npm >/dev/null 2>&1; then
  echo 'HOLD: Node.js and npm are required locally' >&2
  exit 2
fi
if [[ ! -d "$ROOT/sovereign-omega-v2/node_modules" ]]; then
  echo 'HOLD: dependencies not installed; refusing implicit npm ci/network download' >&2
  exit 2
fi

printf 'MEMBRANE: executing original hash verifier\n'
(cd "$ROOT/sovereign-omega-v2" && node scripts/verify-hashes.mjs) || {
  echo 'GATE 0: FAILED (membrane), HALT' >&2
  exit 1
}
for idx in "${!GATE_CMDS[@]}"; do
  gate="$((idx+1))"
  printf 'GATE %s: START command=%s\n' "$gate" "${GATE_CMDS[$idx]}"
  if (cd "$ROOT/sovereign-omega-v2" && bash -c "${GATE_CMDS[$idx]}"); then
    printf 'GATE %s: PASSED (exit 0)\n' "$gate"
  else
    rc=$?
    printf 'GATE %s: FAILED (exit %s), HALT\n' "$gate" "$rc" >&2
    exit "$rc"
  fi
done
printf 'EIGHT_GATES=PASSED (local commands only; no deployment or repository-wide receipt)\n'
