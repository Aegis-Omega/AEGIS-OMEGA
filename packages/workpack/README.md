# AEGIS Ω WorkPack — portable work protocol (experimental v0.1)

**Any model can author the same manifest. Any person can check its artifact bytes without trusting the model.** Python 3 standard library only; no API key, database, cloud service or GitHub login needed to run the local verifier.

This is **not** an autonomous superintelligent agent. It is one small, reusable work-product protocol intended to complement AEGIS Issues #734 (firm of agents), #746 (GitHub exact-head delivery gate), and PRs #732 (context), #730 (capability ranking), #743 (model-call receipts). No signed admission, independent reviewer authentication, CI merge or deployment is implemented in this package.

## v0.2 research-first requirement (new, fail-closed)

**Before agents call their work complete**, they must perform and document a bounded live literature / competitor / standard search, compare at least two alternatives, specify a measurable falsification test and capture a learning outcome. See [RESEARCH_STANDARD.md](RESEARCH_STANDARD.md).

`manifest.json` may include a `research` object with schema `aegis.research-cycle.v1`. The Python verifier checks timestamps (≤7 days), ≥2 source publishers, SHA-256 anchored local source notes, ≥2 compared alternatives, an explicit baseline, metrics, falsification and next experiment. For an existing v0.1 pack without research the receipt still shows **artifact-level** integrity and structure, but `delivery_readiness=BLOCKED_RESEARCH_OR_COMPARISON`; the normal CLI exits 1. If a packet is structurally complete but its falsification outcome is `NOT_RUN`, delivery still exits 1 (`BLOCKED_UNRUN_FALSIFICATION`). A model-reported experiment result is never authenticated factual success. To inspect legacy artifact integrity only, explicitly run `--integrity-only`.

Even a complete packet remains `RESEARCH_PACKET_PRESENT_UNATTESTED`: a self-authored website excerpt is not an authenticated capture, and no offline tool can guarantee an agent really browsed or prove scientific truth. Real web queries and independent source cross-checks belong to the connected, permitted agent harness. **No automatic network requests or unapproved actions** are added to the verifier.

```bash
python3 -m unittest discover -s tests -q
python3 build_demo.py
python3 -m aegis_workpack.protocol examples/data-baseline --integrity-only
# Normal agent-delivery CLI refuses a manifest missing the research cycle:
python3 -m aegis_workpack.protocol examples/data-baseline   # expected exit 1
```

## Run immediately

```bash
python3 build_demo.py
python3 -m unittest discover -s tests -v
python3 -m aegis_workpack.protocol examples/data-baseline --integrity-only
python3 -m aegis_workpack.protocol examples/data-tampered
```

The verifier reads `manifest.json` inside a workspace, checks declared artifact SHA-256 bytes and limited **structural** acceptance checks. The default is no execution, no network, no writes, and no authority. A positive result is `LOCAL_INTEGRITY_AND_STRUCTURE_VERIFIED` — **not** correctness, provenance authenticity or production admission. The tampered data fixture should return exit 1.

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
