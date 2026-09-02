# Kaggle 2026 — Hallucination Delta Submission Evidence

This directory binds the April 2026 Kaggle submission archive to this
repository.  The archive itself is retained as an external historical
artifact; `manifest.json` supplies its stable filename, byte length, and
SHA-256 digest so that a supplied copy can be verified without relying on a
mutable hosting location.

## Submission record

| Field | Value |
| --- | --- |
| Entry | **Sovereign AGI OS: Measuring Metacognition via Hallucination Delta** |
| Competition track | **Measuring Progress Toward AGI — Metacognition** |
| Declared deadline | 16 April 2026 |
| Archive | `kaggle_submission_FINAL(1).zip` |
| Archive size | 56,988 bytes |
| SHA-256 | `517f9287dc9ae472a0edb37378c5314e0865ccf31ee287320d205eea1b34e380` |

Verify an obtained archive with:

```sh
sha256sum kaggle_submission_FINAL\(1\).zip
```

The result must equal the digest recorded above and in `manifest.json`.

## Historical benchmark evidence

The package records these April benchmark outputs:

| Evaluation | Result |
| --- | --- |
| T1–T9 mean Hallucination Delta (Kimi) | 0.0806 |
| T1–T9 mean Hallucination Delta (DeepSeek) | 0.1130 |
| T1–T9 mean Hallucination Delta (Devstral) | 0.1177 |
| T1–T9 mean Hallucination Delta (Nemotron) | 0.3981 |
| T10–T14 mean Hallucination Delta | 0.33 |
| ARC mean Hallucination Delta | 0.3411 |
| ARC mean accuracy | 0.6589 |
| Proof suite | 8/8 PASS; mean Hallucination Delta 0.0907 |

## Epistemic boundary

This evidence establishes only that the identified Hallucination Delta
submission package and its historical output artifacts exist. It does **not**
validate or upgrade separate claims about the ECDist graph/Laplacian estimator,
its mathematical proof, biological scaling, or later benchmark tables.

The package contains neither an official Kaggle receipt nor a winner notice.
Accordingly, this record makes no claim that the entry was accepted, ranked,
or awarded by Kaggle.
