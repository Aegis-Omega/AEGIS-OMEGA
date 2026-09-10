# AEGIS Ω Provider-Neutral Skill Factory v1

## Purpose

Replace the Claude-coupled cognitive-manifest admission path with two smaller, independently testable mechanisms:

1. exact checked-out Git-head verification for repository evidence; and
2. a provider-neutral skill-candidate factory whose outputs carry no authority until independently validated.

## Skill candidate matrix

The v1 taxonomy contains 16 domains × 16 capabilities × 8 modalities = **2,048 deterministic candidate skills**.

Candidate generation is not learning proof. Every generated record begins with:

- `status = CANDIDATE`
- `epistemic_status = UNVERIFIED_CANDIDATE`
- `validated_runs = 0`
- `authority_effect = NONE`

Promotion requires independent execution evidence satisfying the registry promotion policy. Cardinality, naming, model output, or repetition alone cannot promote a skill.

## Active files

- `knowledge/skill-taxonomy.v1.json` — provider-neutral source taxonomy.
- `scripts/build-skill-factory.py` — deterministic registry builder.
- `scripts/validate-exact-head.py` — exact Git-head/worktree verifier.
- `harness/sdk/provider_neutral_execution.py` — workspace verifier that retains constitution/claims checks without Claude-specific anchor requirements.
- `.github/workflows/automaton-2.yml` — required status check preserving the exact name `aegis / automaton-2` while executing the provider-neutral gates.

## Removed active control-plane files

The decommission removes the root `.claude.json` manifest, `skill-hashes.sha256`, cognitive-manifest writer, trusted-cognitive-admission workflow/evaluators, cognitive-state schema, and their dedicated regression/policy files.

`.claude/skills/**` content is not deleted in this change. It is treated as legacy source corpus pending migration/deduplication into provider-neutral knowledge storage. Retaining source material does not grant it execution authority.

## Verification

```bash
python sovereign-omega-v2/python/tests/test_exact_head.py -v
python sovereign-omega-v2/python/tests/test_skill_factory.py -v
python sovereign-omega-v2/python/tests/test_provider_neutral_execution.py -v
python scripts/build-skill-factory.py --expect-count 2048
```

Automaton-2 also emits `EXACT_HEAD_RECEIPT.json` and a generated `SKILL_REGISTRY_V1.json` artifact. Neither artifact grants merge, execution, or claim-promotion authority by itself.

## Migration boundary

This change deliberately does not merge, change the protected-main ruleset, or claim that 2,048 candidates are validated competencies. After hosted CI is green, remaining open PRs and legacy branches must be triaged against the new boundary and classified as keep/rebase, superseded, archive, or independently repairable.
