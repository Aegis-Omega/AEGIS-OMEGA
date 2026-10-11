# AEGIS Ω WorkPack — portable work protocol (experimental v0.1)

**Any model can author the same manifest. Any person can check its artifact bytes without trusting the model.** Python 3 standard library only; no API key, database, cloud service or GitHub login needed to run the local verifier.

This is **not** an autonomous superintelligent agent. It is one small, reusable work-product protocol intended to complement AEGIS Issues #734 (firm of agents), #746 (GitHub exact-head delivery gate), and PRs #732 (context), #730 (capability ranking), #743 (model-call receipts). No signed admission, independent reviewer authentication, CI merge or deployment is implemented in this package.

## v0.2 research-first requirement (new, fail-closed)

**Before agents call their work complete**, they must perform and document a bounded live literature / competitor / standard search, compare at least two alternatives, specify a measurable falsification test and capture a learning outcome. See [RESEARCH_STANDARD.md](RESEARCH_STANDARD.md).

`manifest.json` may include a `research` object with schema `aegis.research-cycle.v1`. The Python verifier checks timestamps (≤7 days), ≥2 source publishers, SHA-256 anchored local source notes, ≥2 compared alternatives, an explicit baseline, metrics, falsification and next experiment. For an existing v0.1 pack without research the receipt still shows **artifact-level** integrity and structure, but `delivery_readiness=BLOCKED_RESEARCH_OR_COMPARISON`; the normal CLI exits 1. If a packet is structurally complete but its falsification outcome is `NOT_RUN`, delivery still exits 1 (`BLOCKED_UNRUN_FALSIFICATION`). A model-reported experiment result is never authenticated factual success. **v0.4 fail-closed change:** even a packet with a replayed local exact-match evaluation has `delivery_readiness=BLOCKED_UNATTESTED_RESEARCH_AND_ORACLE`, `work_complete=false`, `disposition=NOT_ADMITTED` and the normal CLI exits 1. The old exit-0 path falsely promoted self-authored sources and answer keys. To inspect legacy artifact integrity only, explicitly run `--integrity-only`.

Even a complete packet remains `RESEARCH_PACKET_PRESENT_UNATTESTED`: a self-authored website excerpt is not an authenticated capture, and no offline tool can guarantee an agent really browsed or prove scientific truth. Real web queries and independent source cross-checks belong to the connected, permitted agent harness. **No automatic network requests or unapproved actions** are added to the verifier.

```bash
python3 -m unittest discover -s tests -q
python3 build_demo.py
python3 -m aegis_workpack.protocol examples/data-baseline --integrity-only
# Normal agent-delivery CLI refuses a manifest missing the research cycle:
python3 -m aegis_workpack.protocol examples/data-baseline   # expected exit 1
```

## v0.3 — deterministic falsification replay (2026-10-11)

A model **cannot** satisfy a completed experiment merely by changing `evaluation.outcome` from `NOT_RUN` to `SUPPORTED` or `FALSIFIED`. When the claimed outcome is not `NOT_RUN`, the research packet **requires** `evaluation.metric_kind="case_exact_match"`, an `evaluation.evidence_artifact` relative path, and its `evaluation.evidence_sha256`. The evaluator reads the evidence file under the workspace without following POSIX symlinks, verifies its SHA-256, requires 3–100 case records, and computes the outcome directly from each record's `expected`, `baseline`, and `candidate` values. Claimed outcomes that disagree with computed results are blocked.

Example research evaluation fields:

```json
{
  "metric_kind": "case_exact_match",
  "evidence_artifact": "evidence/eval-cases.json",
  "evidence_sha256": "REPLACE_WITH_REAL_SHA256",
  "outcome": "SUPPORTED"
}
```

`evidence/eval-cases.json` contains `{"schema":"aegis.exact-match-eval.v1","cases":[{"id":"case01","expected":"a","baseline":"b","candidate":"a"}, ...]}` with at least three distinct cases. `SUPPORTED` means **more locally matched cases** for the candidate, `FALSIFIED` means fewer, and `INCONCLUSIVE` means equal. These labels do **not** establish true real-world improvement: the expected answers and test cases may still be authored by the agent itself, or contaminated by its training data. `domain_quality=UNVERIFIED`, `improvement=UNPROVEN` and `authority_effect=NONE` remain unchanged. Other metrics must use separately reviewed evaluator adapters; we do not accept arbitrary commands or code from the manifest.

This exactly follows the distinction between deterministic offline test doubles and independent end-to-end model integration described in the current [OpenAI Agents SDK testing guidance](https://openai.github.io/openai-agents-python/testing/) and the need for layered evaluation, holdouts and human calibration in [Anthropic's eval engineering guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents). Source documentation is contextual; no claim of A2A or MCP certification is made.

## Run immediately

```bash
python3 build_demo.py
python3 -m unittest discover -s tests -v
python3 -m aegis_workpack.protocol examples/data-baseline --integrity-only
python3 -m aegis_workpack.protocol examples/data-tampered
```

The verifier reads `manifest.json` inside a workspace, checks declared artifact SHA-256 bytes and limited **structural** acceptance checks. The default is no execution, no network, no writes, and no authority. A positive **local_result** is `LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED`, but the **disposition is always `NOT_ADMITTED`** until an independently authenticated external verifier is integrated. By default the CLI returns nonzero even for locally replayed research packets; the explicit `--integrity-only` diagnostic returns zero only for successful artifact-level checks. Neither exit code grants real-world correctness, source authenticity or permission to deploy. The tampered data fixture should return exit 1.

## Protocol (manifest.json)

```json
{
  "schema": "aegis.workpack.v1",
  "task_id": "my-agent-work-001",
  "domain": "data",
  "authority": "read_only",
  "objective": "Produce a sample table with two measured rows",
  "producer": {"agent": "any-local-or-cloud-model"},
  "artifacts": [{"path": "sample.csv", "sha256": "64_HEX_CHARACTER_SHA256_OF_THE_FILE"}],
  "checks": [
    {"id": "A1", "kind": "sha256", "artifact": "sample.csv"},
    {"id": "A2", "kind": "csv_columns", "artifact": "sample.csv", "columns": ["id", "value"], "min_rows": 2}
  ]
}
```

Supported task domains: `code`, `science`, `data`, `operations`, `design`, `writing`. Structural checks: `sha256`, `json_keys`, `csv_columns`, `text_contains`; `independent_review` explicitly blocks offline because an agent-supplied reviewer name is not authentication. Additional validators for scientific truth, production policy and secure provenance must be separate trusted adapters, not a self-attested `PASS`.

## Synthetic evaluation (no model-performance claims)

`python3 build_demo.py` generates 12 entirely synthetic cases: baseline + tampering for each of the six domains. Baseline artifact **integrity/structure** should be accepted 6/6; tampering should be rejected 6/6. These are deterministic integrity regression fixtures, **not** a benchmark proving a model solved 12 real tasks or beating the frontier.

## Open distribution

The containing AEGIS-OMEGA repository is licensed AGPL-3.0. The protocol uses portable JSON and has no provider-specific SDK dependencies. It is designed to be adapted to A2A task transport and MCP tool access through separately reviewed adapters; no compatibility or interoperability certification is claimed.

## Security and constraints

- Paths must be relative and component-safe. Symlinks, duplicate manifest keys, NaN, oversized files, missing assets, undeclared artifacts, unexpected check types, and malformed CSV/JSON reject by default.
- The local verifier only **reads** workspaces and cannot run arbitrary `command` strings from manifests. `--output` is an explicitly requested local receipt write, not an external side effect.
- File bytes and hashes can be forged together by the same agent; integrity **does not** mean independent authenticity. `domain_quality` stays `UNVERIFIED` even after structural success.
- Concurrent filesystem mutation between `lstat` and file read is a documented TOCTOU limitation: run on a fixed, immutable checkout when adversarial writers exist. For stronger guarantees add dirfd/openat-based traversal and signed provenance.
- Never infer authorization to charge money, access secrets, merge a PR, send emails, write production data or claim a mathematics conjecture is proved.

## Methodology compared with frontier

The OpenAI Agents SDK provides runtime handoffs/tracing/guardrails; Anthropic describes routing and evaluator-optimizer patterns; A2A targets inter-agent task interoperability; MCP provides tool integration and authorization. WorkPack is **only** a minimal artifact contract and local check, not a replacement for those systems. Quality should be assessed in independent, real-world tasks with confidential holdouts to avoid contaminated benchmark claims.

## v0.5 — calibrated paired comparisons (still NOT_ADMITTED)

The original exact-match evaluator could label a 2-of-3 directional gain as `SUPPORTED` without quantifying uncertainty. The read-only comparator now emits `candidate_improvements` and `candidate_regressions` on the SAME cases, `discordant_pairs`, `paired_accuracy_delta_pp`, a two-sided exact McNemar/binomial `paired_p_value`, and `statistical_signal`. Samples smaller than **20** cases are always `UNDERPOWERED`, regardless of the score. At 20+ cases, a signal requires an exact paired p-value ≤0.05. This is a conservative descriptive threshold, **not** a valid causal or cross-model superiority claim: task independence, multiple comparisons, holdout ownership, authentic reference answers, source provenance and repeated trials remain unverified. `calculated_outcome=SUPPORTED` is only the directional score, explicitly marked `SELF_REPORTED_DIRECTION_ONLY`.

The evaluator neither learns nor validates the reference oracle, and no outcome changes the default `NOT_ADMITTED` state. Use real heterogeneous agent tasks, held-out independent adjudication, repeated attempts and controlled costs to make comparative claims. Synthetic test fixtures measure only implementation behavior.
