# AEGIS Ω cross-platform agent entry point

Canonical working rules are in **WORKFLOW.md** and **CLAUDE.md**; do not fork
the authority policy into another agent-specific guide.

1. Run `scripts/ground-truth.sh`, identify exact SHA and live execution path.
2. Read `REPO_MAP.md`, `INDEX.md`, existing `sovereign-omega-v2/.claude/skills/`,
   and authorized knowledge stores *before* proposing a new module.
3. For substantive tasks, create a **metadata-only** source-reuse manifest
   (see `docs/SOURCE_REUSE_PREFLIGHT_V1.md`) and execute
   `PYTHONPATH=. python3 -m agents.source_reuse_preflight /path/to/manifest.json`.
4. If HOLD, disclose the missing source/coverage/tenant/staleness reason; never
   infer "absent" from a failed import, build, CI runner or a partial search.
5. If READY_FOR_AUTHORITY_REVIEW, continue only through the **existing**
   Automaton-3 evaluator and protected, signed exact-head PR/test process.
6. Run task-specific and adversarial tests; distinguish local PASS from native
   exact-head CI and deployed behavior. No self-reported skill promotion.
7. Preserve evidence and negative findings for #753/#758/#773. No account
   transfer, automatic billing, secret export, production mutation or privilege
   expansion through this instruction file.

This applies to Codex, Copilot, Claude, Gemini and any other agent that reads
repository instructions; it does not imply their hosts actually loaded this
file or grants them credentials.
