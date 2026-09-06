# Spectral Time Inference V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a deterministic, fail-closed spectral/autocorrelation temporal-scale estimator with zero authority effect.

**Architecture:** A single standard-library SDK module computes a positive-frequency DFT scan, selects a deterministic dominant bin, verifies the corresponding lag with normalized overlapping autocorrelation, and returns an immutable receipt. A focused pytest module locks the eight falsification contracts before production code is added.

**Tech Stack:** Python standard library, pytest.

**Spec:** `docs/superpowers/specs/2026-09-06-spectral-time-inference-v1-design.md`

## Global Constraints

- Base authority is `main@6eb2ac201bbe60ebaa9cebad714b8696683772e8`.
- Production implementation must be standard-library only.
- `authority_effect` must always equal `NONE`.
- Minimum sample count is 8.
- Spectral scan uses bins `k=2..floor(n/2)`.
- Autocorrelation support threshold is `0.5`.
- No Claims Ledger promotion is part of this change.

---

### Task 1: Lock the RED contract

**Files:**
- Create: `sovereign-omega-v2/python/tests/test_spectral_time_inference.py`

**Interfaces:**
- Consumes: `harness.sdk.spectral_time_inference`.
- Produces: executable contract for `SpectralTimeInferenceError` and `infer_spectral_time(samples, sample_period)`.

- [x] **Step 1: Write the failing tests** for period recovery, sample-period scaling, constant rejection, non-finite rejection, deterministic tie-break, spectral/autocorrelation consistency, context-length anti-baseline, and zero authority effect.
- [x] **Step 2: Run** `pytest -q sovereign-omega-v2/python/tests/test_spectral_time_inference.py`.
- [x] **Step 3: Confirm RED** because `harness.sdk.spectral_time_inference` does not exist.
- [x] **Step 4: Commit** the RED contract before production code.

Evidence: RED contract commit `044483564ce81326c793a2c0344096ed65cf6d3e`; module lookup at that commit returns 404 and local collection fails with the expected `ModuleNotFoundError`.

### Task 2: Implement the minimal estimator

**Files:**
- Create: `harness/sdk/spectral_time_inference.py`
- Test: `sovereign-omega-v2/python/tests/test_spectral_time_inference.py`

**Interfaces:**
- Produces: `SpectralTimeInferenceError`, immutable `SpectralTimeInferenceReceiptV1`, and `infer_spectral_time(samples, sample_period)`.

- [x] **Step 1: Validate inputs** and mean-center the finite real sequence.
- [x] **Step 2: Compute deterministic DFT power** for bins `2..floor(n/2)` using `math.sin`, `math.cos`, and explicit summation.
- [x] **Step 3: Select the dominant bin** with smallest-index tie-break.
- [x] **Step 4: Compute normalized overlapping autocorrelation** at the nearest inferred period lag.
- [x] **Step 5: Fail closed** below support `0.5`.
- [x] **Step 6: Return the immutable receipt** with `integration_horizon == dominant_period` and `authority_effect == "NONE"`.
- [x] **Step 7: Run** `pytest -q sovereign-omega-v2/python/tests/test_spectral_time_inference.py` and require all tests GREEN.
- [x] **Step 8: Commit** the minimal GREEN implementation.

Evidence: production source commit `6d8793961c3fbbe1d21022e34b96c4e756f0b5f2`; exact Git blob SHA binding matched the locally replayed files; focused suite returned 12 passed, 0 failed.

### Task 3: Verify exact-head behavior and record limits

**Files:**
- Create: `docs/evidence/SPECTRAL_TIME_INFERENCE_V1_RECEIPT.json`

**Interfaces:**
- Consumes: exact feature-branch head and test result.
- Produces: non-authoritative verification receipt bound to the tested source head.

- [x] **Step 1: Run** focused pytest on the feature branch snapshot.
- [x] **Step 2: Record** base commit, tested head, test command, pass/fail counts, algorithm constants, and epistemic limits.
- [x] **Step 3: Mark** `authority_effect` and `claims_ledger_effect` as `NONE`.
- [x] **Step 4: Commit** the receipt.
- [x] **Step 5: Re-fetch branch head** and compare it to the receipt's tested source head; if documentation commit advances the head, explicitly distinguish `tested_source_head` from `receipt_commit_head` rather than pretending the receipt tested itself.

Evidence: receipt commit `2baf5f7172110a9272f608521b1ccb3929826c13`; receipt binds `tested_source_head=6d8793961c3fbbe1d21022e34b96c4e756f0b5f2` and explicitly rejects self-attestation. Additional adversarial sweep: 432 passed, 0 failed.

## Current external verification state

Draft PR: `#415`.

GitHub Actions were triggered for the PR. Until the workflows on the current final head complete successfully, `ci_authority` remains `NOT_ESTABLISHED`. No merge, Claims Ledger promotion, or production admission is authorized by this plan.

## Self-review

Spec coverage: all eight required falsification tests, validation rules, algorithm constants, and epistemic boundaries are mapped to Tasks 1-3.

Placeholder scan: no implementation placeholders are present.

Type consistency: the plan uses one public function and one immutable receipt type consistently across tests, implementation, and receipt.
