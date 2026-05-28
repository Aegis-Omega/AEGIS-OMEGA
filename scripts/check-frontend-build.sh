#!/usr/bin/env bash
# scripts/check-frontend-build.sh
# Run before git commit: verifies npm run build passes in any frontend directory
# that has staged changes. Prevents ERROR-03 pattern (hub required 4 fix commits
# because build was not checked before committing).
#
# Install as git hook:
#   cp scripts/check-frontend-build.sh .git/hooks/pre-commit && chmod +x .git/hooks/pre-commit
#
# Or invoke manually before git commit:
#   bash scripts/check-frontend-build.sh

set -euo pipefail

FRONTEND_DIRS=(hub platform-picker hook-generator content-calendar cockpit)
REPO_ROOT="$(git rev-parse --show-toplevel)"
FAILED=0
CHECKED=0

for dir in "${FRONTEND_DIRS[@]}"; do
    if git diff --cached --name-only | grep -q "^${dir}/"; then
        CHECKED=$((CHECKED + 1))
        echo "→ ${dir}: staged changes detected — verifying build..."
        if ! (cd "${REPO_ROOT}/${dir}" && npm run build 2>&1 | tail -8); then
            echo "✗ ${dir}: build FAILED — fix before committing"
            FAILED=$((FAILED + 1))
        else
            echo "✓ ${dir}: build OK"
        fi
    fi
done

if [ "${CHECKED}" -eq 0 ]; then
    echo "✓ No frontend directories have staged changes — skipping build check"
fi

if [ "${FAILED}" -ne 0 ]; then
    echo ""
    echo "Pre-commit build check: ${FAILED} failure(s). Fix the errors above before committing."
    exit 1
fi
