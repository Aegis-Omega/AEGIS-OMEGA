---
license: gemma
base_model: google/gemma-3n-E4B-it
tags:
  - aegis-omega
  - gemma3n
  - on-device
  - governance
  - no-weights
pipeline_tag: image-text-to-text
---

# AEGIS-Ω oGemma Holon

oGemma is a configuration-defined advisory node for the AEGIS-Ω and MYTHOS pipeline. This repository contains no fine-tuned model weights. It contains versioned prompts, gate rules, schemas, tests, and client code that are applied to a separately obtained and pinned revision of `google/gemma-3n-E4B-it`.

## Provenance

- Internal holon identifier: `gemma-4e4b-iphone`
- External base model: `google/gemma-3n-E4B-it`
- Base architecture: `gemma3n`
- Base task: `image-text-to-text`
- Artifact kind: configuration holon with no weights
- Evidence tier: T2
- Grants authority: no
- Authority root: AEGIS Automaton-3

The internal holon identifier is not the base-model name. A release must include the exact base-model Hub commit and a SHA-256 manifest for every published artifact.

## Mathematical notation

```text
Phi = (1 + sqrt(5)) / 2
phi = 1 / Phi = Phi - 1
quorum = 618 / 1000 = 0.618, an approximation to phi
```

The deterministic audit is recorded in `platform/sol/wolfram/MATH_AUDIT.md`. Model-dependent threshold claims remain hypotheses until a complete model and calibration record are supplied.

## Release constraints

Publication is denied unless the base revision is immutable, the destination is owned by `aegis-omega`, weight-like files are absent, all files are hashed, credentials are absent, and the release remains private unless a separate public-release approval is admitted.

## License

The base model is governed by the Gemma license. No base-model weights are redistributed here.
