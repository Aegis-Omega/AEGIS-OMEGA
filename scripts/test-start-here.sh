#!/usr/bin/env bash
# Completely offline regression tests for AEGIS root start-here.sh.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMP="$(mktemp -d)"
trap 'rm -rf "$TEMP"' EXIT
mkdir -p "$TEMP/repo/sovereign-omega-v2/.claude/commands" "$TEMP/repo/sovereign-omega-v2/scripts" "$TEMP/repo/sovereign-omega-v2/node_modules" "$TEMP/repo/.github/workflows" "$TEMP/repo/scripts" "$TEMP/bin"
cp "$ROOT/start-here.sh" "$TEMP/repo/start-here.sh"
cat > "$TEMP/repo/sovereign-omega-v2/.claude/commands/run-gates.md" <<'GATES'
Gate 1: `npm run test -- --reporter=verbose test/unit/jcs.test.ts`
Gate 2: `npm run test -- test/unit/sequence.test.ts`
Gate 3: `npm run test -- test/unit/immutable.test.ts`
Gate 4: `npm run test -- test/unit/reducer.test.ts`
Gate 5: `npm run test -- test/unit/vcg.test.ts`
Gate 6: `npm run test -- test/unit/gate.test.ts`
Gate 7: `npm run test -- test/integration/replay.test.ts test/integration/pipeline.test.ts`
Gate 8: `npm run test && npm run typecheck && npm run build`
GATES
for i in $(seq 1 14); do printf '          run_suite fixture-%02d cargo WIRED cmd\n' "$i"; done > "$TEMP/repo/.github/workflows/repository-verification.yml"
for i in $(seq 1 14); do printf '            --required-suite fixture-%02d\n' "$i"; done >> "$TEMP/repo/.github/workflows/repository-verification.yml"
printf '# existing collector fixture\n' > "$TEMP/repo/scripts/repository_verification.py"
printf 'console.log("fixture")\n' > "$TEMP/repo/sovereign-omega-v2/scripts/verify-hashes.mjs"
for f in \
  test/unit/jcs.test.ts test/unit/sequence.test.ts \
  test/unit/immutable.test.ts test/unit/reducer.test.ts \
  test/unit/vcg.test.ts test/unit/gate.test.ts \
  test/integration/replay.test.ts test/integration/pipeline.test.ts; do
  mkdir -p "$TEMP/repo/sovereign-omega-v2/$(dirname "$f")"
  printf '// canonical fixture\n' > "$TEMP/repo/sovereign-omega-v2/$f"
done
cat > "$TEMP/bin/npm" <<'NPM'
#!/usr/bin/env bash
printf '%s\n' "$*" >> "$AEGIS_TEST_NPM_LOG"
if [[ "${AEGIS_FAIL_AT:-0}" == "$(wc -l < "$AEGIS_TEST_NPM_LOG" | tr -d ' ')" ]]; then exit 43; fi
NPM
chmod +x "$TEMP/bin/npm"
export PATH="$TEMP/bin:$PATH" AEGIS_TEST_NPM_LOG="$TEMP/npm.log"
cd "$TEMP/repo"
git init -q
git -c user.name=Test -c user.email=test@example.invalid add .
git -c user.name=Test -c user.email=test@example.invalid commit -qm fixture

# Inspect must not execute any tests or modify the local working tree.
bash start-here.sh --inspect > "$TEMP/inspect.log"
grep -q 'AEGIS_BOOTSTRAP_CONTRACT=PASS gates=8 suites=14' "$TEMP/inspect.log"
grep -q 'EXECUTION=NOT_RUN' "$TEMP/inspect.log"
test ! -f "$AEGIS_TEST_NPM_LOG"

# Every gate must execute, with Gate 8's three subcommands preserved.
bash start-here.sh --gates > "$TEMP/full.log"
grep -q 'EIGHT_GATES=PASSED' "$TEMP/full.log"
test "$(wc -l < "$AEGIS_TEST_NPM_LOG")" -eq 10

# Fail-closed: Gate 4 failure must prevent Gate 5-8 execution.
: > "$AEGIS_TEST_NPM_LOG"
export AEGIS_FAIL_AT=4
if bash start-here.sh --gates > "$TEMP/failure.log" 2>&1; then echo 'expected gate failure' >&2; exit 1; else test "$?" -eq 43; fi
grep -q 'GATE 4: FAILED' "$TEMP/failure.log"
! grep -q 'GATE 5: START' "$TEMP/failure.log"
test "$(wc -l < "$AEGIS_TEST_NPM_LOG")" -eq 4
unset AEGIS_FAIL_AT

# Contract drift must fail before any commands are executed.
sed -i 's@test/unit/gate.test.ts@test/unit/changed.test.ts@' "$TEMP/repo/sovereign-omega-v2/.claude/commands/run-gates.md"
: > "$AEGIS_TEST_NPM_LOG"
if bash start-here.sh --gates > "$TEMP/drift.log" 2>&1; then echo 'expected gate drift HOLD' >&2; exit 1; else test "$?" -eq 2; fi
grep -q 'Gate 6 command differs' "$TEMP/drift.log"
test ! -s "$AEGIS_TEST_NPM_LOG"
sed -i 's@test/unit/changed.test.ts@test/unit/gate.test.ts@' "$TEMP/repo/sovereign-omega-v2/.claude/commands/run-gates.md"

# Missing corpus source is a hard HOLD, not a manufactured success.
rm "$TEMP/repo/scripts/repository_verification.py"
if bash start-here.sh --inspect > "$TEMP/missing.log" 2>&1; then echo 'expected missing source HOLD' >&2; exit 1; else test "$?" -eq 2; fi
grep -q 'missing canonical dependency' "$TEMP/missing.log"
# Mismatched required-suite contract is a HOLD, never a green receipt.
printf '# collector restored\n' > "$TEMP/repo/scripts/repository_verification.py"
sed -i 's/--required-suite fixture-14/--required-suite unexpected-suite/' "$TEMP/repo/.github/workflows/repository-verification.yml"
if bash start-here.sh --inspect > "$TEMP/required.log" 2>&1; then echo 'expected required-suite mismatch HOLD' >&2; exit 1; else test "$?" -eq 2; fi
grep -q 'defined and required suite IDs differ' "$TEMP/required.log"
# A missing gate test must block both inspection and execution.
sed -i 's/--required-suite unexpected-suite/--required-suite fixture-14/' "$TEMP/repo/.github/workflows/repository-verification.yml"
rm "$TEMP/repo/sovereign-omega-v2/test/unit/jcs.test.ts"
if bash start-here.sh --inspect > "$TEMP/gate-source-missing.log" 2>&1; then
  echo 'expected missing gate test HOLD' >&2; exit 1
else test "$?" -eq 2; fi
grep -q 'missing canonical gate test test/unit/jcs.test.ts' "$TEMP/gate-source-missing.log"

# When dependencies are missing, refuse to run local suites implicitly.
printf '// restored canonical fixture\n' > "$TEMP/repo/sovereign-omega-v2/test/unit/jcs.test.ts"
rm -rf "$TEMP/repo/sovereign-omega-v2/node_modules"
if bash start-here.sh --gates > "$TEMP/deps-missing.log" 2>&1; then
  echo 'expected node_modules HOLD' >&2; exit 1
else test "$?" -eq 2; fi
grep -q 'refusing implicit npm ci' "$TEMP/deps-missing.log"

# Membrane failure must halt before the first npm command, preserving original verifier.
mkdir -p "$TEMP/repo/sovereign-omega-v2/node_modules"
printf 'process.exit(71)\n' > "$TEMP/repo/sovereign-omega-v2/scripts/verify-hashes.mjs"
: > "$AEGIS_TEST_NPM_LOG"
if bash start-here.sh --gates > "$TEMP/membrane-failure.log" 2>&1; then
  echo 'expected membrane failure HALT' >&2; exit 1
else test "$?" -eq 1; fi
grep -q 'GATE 0: FAILED (membrane), HALT' "$TEMP/membrane-failure.log"
test ! -s "$AEGIS_TEST_NPM_LOG"

# Missing canonical source check emits a real newline, not escaped text.
test "$(printf 'HOLD: missing canonical gate test %s\n' test/unit/jcs.test.ts | wc -l)" -eq 1
printf 'AEGIS_BOOTSTRAP_TESTS=9/9 PASS (offline, fixture-scoped)\n'
