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
- POSIX artifact, research excerpt and manifest reads use component-by-component `dir_fd`/`O_NOFOLLOW` traversal, plus **`O_NONBLOCK` on the final file descriptor before `fstat`**. A hostile named pipe (FIFO) must never hang verification while waiting for a writer. The Python `read_json()` helper uses the same bounded regular-file reader. Non-POSIX precheck/fallback and concurrent content mutations remain insufficiently protected against TOCTOU: verify immutable workspaces with independent provenance.
- Never infer authorization to charge money, access secrets, merge a PR, send emails, write production data or claim a mathematics conjecture is proved.

## Methodology compared with frontier

The OpenAI Agents SDK provides runtime handoffs/tracing/guardrails; Anthropic describes routing and evaluator-optimizer patterns; A2A targets inter-agent task interoperability; MCP provides tool integration and authorization. WorkPack is **only** a minimal artifact contract and local check, not a replacement for those systems. Quality should be assessed in independent, real-world tasks with confidential holdouts to avoid contaminated benchmark claims.

## v0.5 — calibrated paired comparisons (still NOT_ADMITTED)

The original exact-match evaluator could label a 2-of-3 directional gain as `SUPPORTED` without quantifying uncertainty. The read-only comparator now emits `candidate_improvements` and `candidate_regressions` on the SAME cases, `discordant_pairs`, `paired_accuracy_delta_pp`, a two-sided exact McNemar/binomial `paired_p_value`, and `statistical_signal`. Samples smaller than **20** cases are always `UNDERPOWERED`, regardless of the score. At 20+ cases, a signal requires an exact paired p-value ≤0.05. This is a conservative descriptive threshold, **not** a valid causal or cross-model superiority claim: task independence, multiple comparisons, holdout ownership, authentic reference answers, source provenance and repeated trials remain unverified. `calculated_outcome=SUPPORTED` is only the directional score, explicitly marked `SELF_REPORTED_DIRECTION_ONLY`.

The evaluator neither learns nor validates the reference oracle, and no outcome changes the default `NOT_ADMITTED` state. Use real heterogeneous agent tasks, held-out independent adjudication, repeated attempts and controlled costs to make comparative claims. Synthetic test fixtures measure only implementation behavior.

## v0.6 — bounded filesystem reads, no named-pipe stalls

The v0.5 verifier called blocking POSIX `open(O_RDONLY)` on an untrusted artifact, manifest or source-note path **before** `fstat` could prove it was a regular file. A FIFO with no writer could therefore hang the verifier indefinitely. This was reproduced with a subprocess timeout. The final-leaf POSIX open now includes `O_NONBLOCK` and is immediately followed by a regular-file check. `read_json()` uses this exact safe path rather than a separate unchecked `open()`. Four sandboxed negative tests cover FIFO in an artifact, CLI manifest, public helper, and research evidence. The default delivery verdict remains `NOT_ADMITTED`, independent quality `UNVERIFIED`, and this remains a local hardening patch, not a cross-platform security proof.

## v0.7 — strict bounded JSON decoding across the entire pipeline

**Before fix:** `json_keys` accepted `{"value":NaN}` and `{"value":Infinity}` as structurally valid JSON. This is a Python decoder extension and **violates RFC 8259**. `1e400` is a legal JSON numeric token but overflows Python binary64 to non-finite infinity, making interpretation implementation-dependent. The manifest helper previously caught special tokens but not this exponent-overflow case, while research evaluation had a separate parser.

**Fix:** one shared `_strict_json_loads` decoder for CLI manifests, the public `read_json` helper, data `json_keys` checks and evaluation-case JSON. It rejects NaN/±Infinity extensions via `parse_constant`, and parsed floating-point values that become non-finite via a bounded `parse_float` guard. Duplicate JSON keys remain rejected. The output remains **structural evidence only**, not authenticated scientific correctness.

**Falsification:** baseline exact SHA `f5c01cfece6abf3fba64c56b5f1de378591794ba` reported `PASS` for `json_keys` on `NaN`, `Infinity`, `-Infinity` and binary64-overflow `1e400`. The new source rejects all, while normal finite decimal JSON succeeds. Seven new adversarial/positive regressions extend the Python stdlib suite from 83 to **90**. Existing CLI work-admission remains `NOT_ADMITTED`, including in `--integrity-only` mode. This is a narrowly evidenced improvement in parser correctness; cross-runtime canonicalization, JSON Schema conformance and a production AEGIS admission are **not** claimed.

Reference: [RFC 8259 §6](https://www.rfc-editor.org/rfc/rfc8259#section-6) and [Python json decoder documentation](https://docs.python.org/3/library/json.html#json.loads).

## v0.8 — no symlink traversal in the public `read_json()` helper

**Reproduced on the previous helper:** `read_json(workspace/alias/secret.json)` followed a symbolic link in `alias` because the helper passed `source.parent` to `_artifact_bytes()`, which called `Path.resolve(strict=True)` on that parent **before** running any `O_NOFOLLOW` checks. The helper returned valid JSON from outside the apparent directory. It was not enough that the leaf was checked.

**Exact fix:** On POSIX, the public helper walks the absolute path lexically from the trusted filesystem anchor `/` using the existing component-wise `open(dir_fd=..., O_DIRECTORY|O_NOFOLLOW)` and guarded nonblocking leaf reader. It does not resolve link-bearing parents and rejects explicit `..` components before traversal. CLI/workspace artifact reads retain their separate trusted-root contract. Non-POSIX behavior remains a documented immutable/trusted-workspace fallback; no universal cross-platform race-freedom is claimed.

The new tests require that parent symlinks and leaf symlinks fail, explicit `..` is rejected, and ordinary nested regular JSON still passes. Together with the v0.7 RFC-8259 parser hardening, this is a narrowly demonstrated local security improvement, not an independently validated agent benchmark. Default `NOT_ADMITTED` behavior is unchanged.

## v0.9 — parser resource limits and direct-API cycle defense

The previous parser could crash with an uncaught `RecursionError` on ~60 KB of deeply nested JSON, or with a `ValueError` on a 5000-digit integer. The direct Python `verify()` API could also accept cyclic or excessively nested programmatic manifests far below the file-byte cap. This release adds a quote/escape-aware **64-level pre-parse nesting limit**, 100-digit maximum integer input, 128-character float literal cap, and bounded iterative cycle/depth/node checks before canonicalization of direct API inputs. Invalid inputs produce an explicit denial receipt; they never constitute an agent quality verdict. Regression coverage includes deeply nested manifests, direct cyclic manifests, JSON artifacts, evaluation datasets, huge integers, and bracket characters inside legitimate JSON strings. The remaining JSON parser can still consume CPU proportionate to accepted bounded input.

## v0.10 — bounded JSON node count on decoded files

The prior JSON decoder enforced maximum nesting depth but accepted more than the declared 50,000-node limit in flat arrays. A 100 KB file with 50,001 numeric entries passed `json_keys` despite a documented `MAX_JSON_NODES` cap in the direct-Python manifest path. Fixed by a quote-aware pre-parse lower-bound check (container openers and unquoted separators), followed by an exact iterative node count of the decoded graph. The parsed artifact text allowance remains 8 MiB; a legitimate 300 KB string document is still accepted. Existing manifests and receipts remain `NOT_ADMITTED` by default. This prevents a false positive and bounds **validated** JSON structure, but a third-party parser's peak memory before the post-parse check remains implementation-dependent; no full resource-limit attestation is claimed.

External safety references: OWASP Input Validation Cheat Sheet, “Parse Safely, Then Validate” (https://cheatsheetseries.owasp.org/cheatsheets/Input_Validation_Cheat_Sheet.html); Python `json` implementation limitations (https://docs.python.org/3/library/json.html).

## v0.11 — well-formed Unicode boundary (controlled denial)

The v0.10 decoded-JSON validator called `str.encode('utf-8')` while estimating
JSON node text size. A syntactically permitted but **unpaired escaped UTF-16
surrogate** (`"\\ud800"` or `"\\udfff"`) therefore raised an unhandled
`UnicodeEncodeError` from `read_json()` and printed a traceback instead of an
ordinary JSON receipt from the CLI. It also bypassed the per-check error
handler for `json_keys`, upgrading a single malformed artifact into a whole
contract-processing error. This was reproduced against the exact v0.10
source, then covered by seven subprocess, direct-API, JSON-check and positive
Unicode regression tests.

v0.11 rejects such strings and object keys explicitly with
`JSON_UNPAIRED_SURROGATE`; complete UTF-16 surrogate pairs, correctly decoded
Unicode code points, and ordinary UTF-8 remain supported. No Unicode repair,
source authenticity claim, production admission, or authority expansion is
implied. RFC 8259 §8.2 explicitly warns that lone UTF-16 surrogates have
unpredictable interoperability: https://www.rfc-editor.org/rfc/rfc8259#section-8.2

## v0.12 — portable workspace file names

The v0.11 `valid_path()` accepted `C:/Windows/...`, `D:secret.txt`, and
`report.txt:secret` as workspace-relative names. On Windows those may denote a
different drive, a drive-relative path or an NTFS alternate data stream.
Names such as `CON`, `NUL.txt`, `COM1`, or trailing-dot/space aliases are also
special on Windows. The WorkPack path grammar now rejects those constructs
on every platform, including Linux, before opening files. Ordinary nested
file names and Unicode text remain allowed.

The `PureWindowsPath` regression proves the parsing discrepancy on Linux;
it **does not** claim actual Windows filesystem exfiltration was reproduced.
A native Windows filesystem and reparse-point audit remains required before
making a general sandbox security claim. Reference: Microsoft Win32 filename
rules, Python `pathlib` path joining and OWASP file-upload/path guidance.

- https://learn.microsoft.com/en-us/windows/win32/fileio/naming-a-file
- https://docs.python.org/3/library/pathlib.html
- https://cheatsheetseries.owasp.org/cheatsheets/File_Upload_Cheat_Sheet.html

## v0.13 — safe receipt export (create-only)

The explicit CLI `--output` is an external **write** surface, unlike read-only
`verify()`. Previous versions used `Path.write_text()` and would follow a
symlink in an untrusted work directory, overwriting a file outside that
directory while still reporting `NOT_ADMITTED`. The exporter now creates
**new files only** (POSIX `O_CREAT|O_EXCL|O_NOFOLLOW`, component-by-component
`dir_fd|O_DIRECTORY|O_NOFOLLOW`, mode `0600`). Existing paths — even ordinary
`receipt.json` files — are never overwritten. On export failure CLI returns
exit `2` and an explicit `output_status=NOT_WRITTEN` receipt on stdout; normal
delivery `NOT_ADMITTED` remains exit `1`, with or without a successful export.
Choose a **new** filename for every attempt to preserve prior evidence.

Non-POSIX fallback uses exclusive creation and a best-effort lstat parent
check; unlike POSIX `dir_fd`, it does **not** close concurrent symlink races.
Run on an immutable/trusted parent on Windows; native Windows testing is open.
No background external write, network, deploy, authority or trusted reviewer
is implemented. The write path is operator-directed only.

## v0.14 — atomic, create-only POSIX receipt publication

**Reproduced v0.13 bug:** `--output` opened its final path with `O_EXCL`, wrote bytes and then called `fsync()`. An injected `ENOSPC`/`EIO` at the file-sync boundary left a visible receipt at the final path despite CLI export failure. If a process crashed during writing, the final name could expose truncated evidence.

The POSIX writer now creates a random, private (`0600`) *temporary sibling* without following directory symlinks; writes, flushes and `fsync()`s it; then uses `os.link(..., src_dir_fd=..., dst_dir_fd=...)` for **atomic no-overwrite publication**, removes the temporary name and `fsync()`s the parent directory. Unlike `rename`/`replace`, `link()` cannot overwrite an existing receipt. The final path never names a partially written file under the local-POSIX-filesystem assumptions.

Post-publication directory-sync failure has a **different outcome** (`WRITTEN_DURABILITY_UNVERIFIED` / `OUTPUT_DURABILITY_UNVERIFIED`, CLI exit 2) because claiming `NOT_WRITTEN` after a successful link would be false. Before the link, failures leave no final receipt; best-effort cleanup removes the hidden temporary file. Six deterministic regression tests cover injected pre-link `fsync`/`link` failures, post-link sync failure, existing-file exclusion, complete and private export, and two concurrent writers. Normal delivery remains `NOT_ADMITTED`; successful `--output` does not grant authority.

**Limits:** file/directory sync durability assumes a conforming local POSIX filesystem; network filesystem, power loss hardware guarantees, Windows-native atomicity and crash-time orphaned hidden temps are not certified. The fallback on non-POSIX platforms remains create-only but *not* atomic-visibility guaranteed. Evidence authenticity and domain correctness remain unverified.

Reference: POSIX `linkat` atomic new-name creation and `EEXIST` behavior; Python `os.link` dirfd support, and filesystem crash-durability patterns.
