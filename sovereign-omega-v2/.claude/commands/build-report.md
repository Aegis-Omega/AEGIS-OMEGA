Generate a structured build status report for the sovereign-runtime package.

Collect the following information and format it as a report:

1. Run `node scripts/verify-hashes.mjs` — frozen file integrity status
2. Run `npm run typecheck` — TypeScript type error count
3. Run `npm run test -- --reporter=json` — test pass/fail counts per suite
4. Check that .env exists and contains required variables from .env.example
5. Report the current git status: branch, last commit hash, uncommitted changes

Format the report as:

SOVEREIGN OMEGA — Build Status Report
Date: [current date from event context]

Frozen File Integrity: [VERIFIED / VIOLATION at file X]
TypeScript: [CLEAN / N errors]
Test Suite: [N passed / N failed / N skipped]
  Gate 1 (JCS): [PASS/FAIL]
  Gate 2 (Sequence): [PASS/FAIL]
  Gate 3 (Immutable): [PASS/FAIL]
  Gate 4 (Reducer): [PASS/FAIL]
  Gate 5 (VCG): [PASS/FAIL]
  Gate 6 (Gate): [PASS/FAIL]
  Gate 7 (Integration): [PASS/FAIL]
  Gate 8 (Full suite): [PASS/FAIL]
Environment: [CONFIGURED / MISSING: list missing vars]
Git: [branch] @ [commit] — [clean / N uncommitted changes]

Overall Status: [DEPLOYMENT-READY / NOT READY — list blockers]
