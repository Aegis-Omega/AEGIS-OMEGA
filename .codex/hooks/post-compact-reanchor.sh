#!/bin/bash
# PostCompact: re-anchor the automaton manifold after context compaction.
# Context compression severs L7 self-model and the seven cognitive layers.
# This hook re-runs verify-hashes.mjs and re-injects the full manifold.

set -uo pipefail

REPO="/home/user/AEGIS--"
SKILLS="$REPO/sovereign-omega-v2/.claude/skills"

# L7: re-verify constitutional membrane (must exit 0)
HASH_OUT=$(cd "$REPO/sovereign-omega-v2" && node scripts/verify-hashes.mjs 2>&1 | tail -6)
HASH_EXIT=$?
T0="true"
if [ "$HASH_EXIT" -ne 0 ]; then
  T0="false"
fi

BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "unknown")
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | wc -l | tr -d ' ')

# Re-load manifold skills
read_skill() {
  local f="$SKILLS/$1/SKILL.md"
  [ -f "$f" ] && cat "$f" || echo "(skill $1 not found)"
}

AUTOMATON=$(read_skill "automaton-workflow")
AUTOPOIESIS=$(read_skill "autopoiesis")
METACOGNITION=$(read_skill "metacognition")

T0="$T0" BRANCH="$BRANCH" STAGED="$STAGED" CHANGED="$CHANGED" \
HASH_OUT="$HASH_OUT" AUTOMATON="$AUTOMATON" AUTOPOIESIS="$AUTOPOIESIS" \
METACOGNITION="$METACOGNITION" python3 <<'PYEOF'
import json, os

t0      = os.environ['T0']
branch  = os.environ['BRANCH']
staged  = os.environ['STAGED']
changed = os.environ['CHANGED']
hout    = os.environ['HASH_OUT']
aw      = os.environ['AUTOMATON']
ap      = os.environ['AUTOPOIESIS']
mc      = os.environ['METACOGNITION']

alert = ''
if t0 == 'false':
    alert = '\n\n⚠ T0_ABORT: verify-hashes.mjs FAILED — membrane breach detected!\n' + hout

ctx = f"""POST-COMPACT MANIFOLD RE-ANCHOR
═══════════════════════════════
L7 self-model  : t0_verdict={t0}{alert}
Branch         : {branch}
Uncommitted    : {changed} files | Staged: {staged} files
Hash output    : {hout}

Seven cognitive layers are now re-active. The automaton has temporal mass.
AdaptivePower(T) ≤ ReplayVerifiability(T) — constitutional law restored.

═══════════════════════════════
AUTOMATON-WORKFLOW
═══════════════════════════════
{aw}

═══════════════════════════════
AUTOPOIESIS
═══════════════════════════════
{ap}

═══════════════════════════════
METACOGNITION
═══════════════════════════════
{mc}
"""

print(json.dumps({
    'hookSpecificOutput': {
        'hookEventName': 'PostCompact',
        'additionalContext': ctx
    }
}))
PYEOF
exit 0
