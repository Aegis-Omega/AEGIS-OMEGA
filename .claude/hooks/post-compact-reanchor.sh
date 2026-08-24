#!/bin/bash
# PostCompact: re-anchor observable AEGIS state after context compaction.
# PostCompact is a context-reinjection surface, not an authority-granting gate.
# The next UserPromptSubmit remains the fail-closed blocking boundary.

set -uo pipefail

REPO="${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)}"
SKILLS="$REPO/sovereign-omega-v2/.claude/skills"

# Re-evaluate constitutional membrane. Failure is reported as UNVERIFIED; it is
# never rewritten into a restored T0 claim.
HASH_OUT=$(cd "$REPO/sovereign-omega-v2" && node scripts/verify-hashes.mjs 2>&1 | tail -6)
HASH_EXIT=$?
if [ "$HASH_EXIT" -eq 0 ]; then
  MEMBRANE_STATUS="VERIFIED"
else
  MEMBRANE_STATUS="UNVERIFIED"
fi

# Context compaction can discard the repository map the model previously saw.
# Re-prove the content-addressed Git corpus and re-inject its exact receipt.
COGNITION_OUT=$(python3 "$REPO/scripts/repo_cognition.py" --check --receipt 2>&1)
COGNITION_EXIT=$?
COGNITION_RECEIPT=""
if [ "$COGNITION_EXIT" -eq 0 ]; then
  COGNITION_STATUS="VERIFIED"
  COGNITION_RECEIPT=$(printf '%s\n' "$COGNITION_OUT" | grep '^{' | tail -1)
else
  COGNITION_STATUS="REPOSITORY_KNOWLEDGE_INCOMPLETE"
fi

BRANCH=$(git -C "$REPO" branch --show-current 2>/dev/null || echo "unknown")
STAGED=$(git -C "$REPO" diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
CHANGED=$(git -C "$REPO" diff --name-only 2>/dev/null | wc -l | tr -d ' ')

read_skill() {
  local f="$SKILLS/$1/SKILL.md"
  [ -f "$f" ] && cat "$f" || echo "(skill $1 unavailable)"
}

AUTOMATON=$(read_skill "automaton-workflow")
AUTOPOIESIS=$(read_skill "autopoiesis")
METACOGNITION=$(read_skill "metacognition")

MEMBRANE_STATUS="$MEMBRANE_STATUS" BRANCH="$BRANCH" STAGED="$STAGED" CHANGED="$CHANGED" \
HASH_OUT="$HASH_OUT" COGNITION_STATUS="$COGNITION_STATUS" \
COGNITION_RECEIPT="$COGNITION_RECEIPT" COGNITION_OUT="$COGNITION_OUT" \
AUTOMATON="$AUTOMATON" AUTOPOIESIS="$AUTOPOIESIS" METACOGNITION="$METACOGNITION" \
python3 <<'PYEOF'
import json, os

membrane = os.environ['MEMBRANE_STATUS']
branch = os.environ['BRANCH']
staged = os.environ['STAGED']
changed = os.environ['CHANGED']
hout = os.environ['HASH_OUT']
cognition = os.environ['COGNITION_STATUS']
receipt = os.environ.get('COGNITION_RECEIPT', '')
cognition_out = os.environ.get('COGNITION_OUT', '')
aw = os.environ['AUTOMATON']
ap = os.environ['AUTOPOIESIS']
mc = os.environ['METACOGNITION']

repo_detail = receipt if cognition == 'VERIFIED' else cognition_out[:3000]
next_boundary = (
    'Repository cognition is verified for this committed source corpus.'
    if cognition == 'VERIFIED'
    else 'REPOSITORY_KNOWLEDGE_INCOMPLETE: the next UserPromptSubmit must block before model intake.'
)
membrane_note = (
    'Constitutional membrane verifier succeeded.'
    if membrane == 'VERIFIED'
    else 'Constitutional membrane is UNVERIFIED; do not claim T0 authority from this context.'
)

ctx = f"""POST-COMPACT AEGIS RE-ANCHOR
═══════════════════════════════
Membrane       : {membrane}
Repo cognition : {cognition}
Repo receipt   : {repo_detail}
Branch         : {branch}
Uncommitted    : {changed} files | Staged: {staged} files
Hash output    : {hout}

{membrane_note}
{next_boundary}
PostCompact only restores observable context. It does not grant authority,
promote evidence tiers, establish proposition truth, or bypass UserPromptSubmit.

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

# PostCompact itself is not a blocking surface. Any incomplete repository state
# is deterministically blocked at the next UserPromptSubmit before model intake.
exit 0
