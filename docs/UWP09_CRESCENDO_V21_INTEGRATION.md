# UWP-09 / UWP-10: Crescendo V2.1 evidence cascade adapter

**Scope:** existing GitHub #757 benchmark and #758 evidence-gated evolution. Offline, branch-only integration candidate; not a competing benchmark, a deployed system, or an external model evaluation.

## Source lineage (14 November 2026)

- Operator-held ZIP AEGIS_CRESCENDO_V21_INDEPENDENT_AUDIT_20261114.zip SHA-256: 8a4eebcf74048396c798613aecda96fa3cbd5e7d5e29e68355759039bb7df993
- Private V2.1 runner cascade.py SHA-256: 8c76ee81fcac687d9e809f1848f0d417d68a16492c07b0ff0ab3236d904b5d96
- Private V2.1 PREREGISTRATION_ABC.json SHA-256: c6375fa65ca14f3d5b1e005cbeeb3b0817aadd2108f27bdf50f752e100ae97ea

The original ZIP, sealed prompts, model answers, holdout fixtures and private evaluator artifacts were not copied into GitHub.

## What was integrated

- scripts/uwp09_crescendo_adapter.py provides read-only preregistration/source-hash checking and inventories optional *local unauthenticated* A/B/C results.
- scripts/test_uwp09_crescendo_adapter.py contains 20 falsifier tests with only dynamically synthesized, publicly shareable records. No test imports the secret holdout.
- This is an adapter to the existing #757 fixture-only UWP-09 benchmark, not a parallel evaluator or a replacement for scripts/uwp_benchmark_manifest.py.
- A local good grade, complete synthetic arm reports, or self-consistent hash chain never sets verified_execution_denominator above 0, never sets independent approval, and never promotes a capability.
- A validated plan yields status PLAN_ONLY_NOT_RUN, verified_success_rate null, hidden_holdout NOT_PROVIDED_TO_PUBLIC_ADAPTER, promotion_status HOLD and authority_effect NONE.

## Offline reproduction

Run tests from repository root:

    python3 -m unittest discover -s scripts -p 'test_uwp09_crescendo_adapter.py' -v

With an authorized, private, locally extracted V2.1 preregistration:

    python3 scripts/uwp09_crescendo_adapter.py --prereg /path/to/AEGIS_CRESCENDO_V2_1/PREREGISTRATION_ABC.json --expected-prereg-sha256 c6375fa65ca14f3d5b1e005cbeeb3b0817aadd2108f27bdf50f752e100ae97ea --runner-archive-sha256 8a4eebcf74048396c798613aecda96fa3cbd5e7d5e29e68355759039bb7df993

Private content is not required to run public tests. Input JSON rejects duplicate keys and nonfinite numbers, and each prereg slot must be NOT_ASSIGNED/NOT_RUN. Optional locally reported trials cannot claim approval or authenticated review.

## Checkpoint and boundaries

- Local original V2.1 offline tests: 31/31 PASS. Local adapter tests: 20/20 PASS.
- Original preregistration contains 30 planned pairs, 90 planned A/B/C arm slots, and **0 independently verified model runs**.
- No independent ChatGPT/Claude run, hidden holdout comparison, false-PASS rate, cost/latency measurement, CI validation on this exact GitHub head, independent reviewer signature or skill promotion is established by the local tests.
- GitHub #757 still requires 10 real cross-domain pilots, 100+ public fixture tasks and an independent withheld set; #758 requires >=30 genuine paired held-out trials per candidate, independent review and existing authority gates.
- Existing protected-main merge, secret, billing, production, and permission controls are unchanged.

## Rules

Operator authority does not substitute for evidence. Local grade is not independently verified execution. Historical source claims do not automatically become current authenticated facts. Lesson promotion and use as agent instructions require explicit independent review and existing protected gates.

Links: https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/757 and https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/758
