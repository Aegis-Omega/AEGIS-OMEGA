# April 2026 Kaggle HD Submission — Evidence Lineage

This directory preserves the user-supplied submission package for the Kaggle **Measuring Progress Toward AGI — Metacognition track** and separates its genuine Hallucination Delta evidence from later unsupported manuscript material.

## Identity

- **Entry:** *Sovereign AGI OS: Measuring Metacognition via Hallucination Delta*
- **Track:** Measuring Progress Toward AGI — Metacognition
- **Declared deadline:** 16 April 2026
- **Author:** Tarik Skalic
- **Original uploaded archive:** `kaggle_submission_FINAL(1).zip`
- **Archive SHA-256:** `517f9287dc9ae472a0edb37378c5314e0865ccf31ee287320d205eea1b34e380`
- **Archive size:** `56988` bytes

The competition identity and deadline are stated inside `swarm_os/kaggle_submission.ipynb` and the benchmark runner. This archive does **not** contain an official Kaggle receipt, leaderboard result, or winner notification, so this repository records it as an author-supplied submission package rather than independently proving platform acceptance.

## Actual scientific object in this lineage

The April submission defines **Hallucination Delta (HD)** as:

```text
HD = |claimed_correctness - actual_correctness|
```

This is the operational metacognition metric used in the `swarm_os` Kaggle lineage. It is separate from the AEGIS execution-provenance/ECDist research line:

- **HD / swarm_os:** historical April 2026 benchmark and model-output evidence.
- **ECDist / AEGIS provenance:** proposed graph distance over claim and evidence structures.

The existence of the HD benchmark must not be used to imply that an ECDist graph builder, normalized-Laplacian estimator, metric-space proof, or production evaluator exists.

## Hash-pinned historical outputs

| Artifact | Recorded result | SHA-256 |
|---|---|---|
| `multi_model_HD_comparison.md` | T1-T9 mean HD: kimi 0.0806; deepseek 0.1130; devstral 0.1177; nemotron 0.3981 | `e16aae352b82ee1cec7e6cd3910ddc9fd023456ffc04b5729468440df57791aa` |
| `extended_benchmark_latest.json` | T10-T14 mean HD 0.33 | `ecb754298b896ce18318090c42f00f33eaf9e93b018e13af471f77e58a703262` |
| `arc_eval_verified.json` | mean HD_ARC 0.3411; mean accuracy 0.6589 over two 100-sample runs | `d947c395c99ce21a1da1c5c4e8c329cfb713b04477a3bc1fe5fba3fe091a1842` |
| `proof_suite_run.txt` | 8/8 PASS; mean HD 0.0907 | `2d364e992d5bfa54ed00ed0a832d48dcec098da6096d6f6fae06e99068058043` |
| `benchmark_run_final.txt` | historical raw multi-model execution log | `857787ac67c8ee693e9007f6b19b0d7b66c2b3ccf8316ee170f09cc81fa92ecd` |
| `kaggle_submission.ipynb` | submitted notebook narrative and embedded result tables | `8cf6a5b6f889cb61c4419addd5fc1e486a4f3f1bea7ae1662c7fbaa4b67ea33f` |

See `manifest.json` for every file, byte size, digest, extracted result, and epistemic boundary.

## Evidence status

**Verified as artifacts:** the archive exists, its files are readable, and the hashes/results above match the supplied package.

**Historical empirical outputs, not independently rerun here:** the model scores, proof-suite result, extended tasks, and ARC runs. Reproduction requires the original environment and, for the live multi-model runner, NVIDIA NIM credentials.

**Not promoted by this patch:** biological-correction causality, Digital Being/epiphany counts as AGI evidence, generalized scaling-law claims, or any later AgentTrace/Aegis-Bench/SABER tables. Those require independent evidence and remain outside this lineage.
