# GemmaEdge — AEGIS-Ω on-device constitutional verifier (iOS/macOS)

On-device edge validation path: a local Gemma runner (`GemmaEdgeRunner`) behind the
Khatt-loop constitutional verifier (`KhattLoopValidation`).

## The invariant this package exists to enforce

> Only an exact `"VERDICT: APPROVED"` returns `true`. Everything else returns `false`.

This replaces an earlier **fail-open** prototype where `executeInference()` always
returned `"VERDICT: APPROVED"`, auto-approving every block regardless of input, model
availability, or real validation. In a constitutional system, mock approval must never
be authoritative — governance components **fail closed**.

What that means concretely (all covered by tests):
- Missing model weights → throw.
- Uninitialized model → throw (never a mock approval).
- Native inference not implemented → throw.
- Any thrown error → `verifySequenceBlock` returns `false`.
- Verdict parsing is **exact equality**, not `.contains("APPROVED")` (so
  `"VERDICT: NOT APPROVED"` is rejected).
- Empty / lowercase / multi-line / malformed output → `false`.
- Adversarial `stateData` does not auto-approve.

`KhattLoopValidation` depends on the `EdgeInferenceRunning` protocol, not the concrete
runner, so it can be tested with a safe mock that needs no network, GPU, filesystem, or
real model.

## Build & test

This package is **not compiled or tested by the monorepo CI** (no Swift toolchain in
the cloud build env). Verify it on a machine with Swift:

```bash
cd clients/gemma-edge-ios
swift test        # or open in Xcode and run the GemmaEdgeTests target
```

## Status

`GemmaEdgeRunner` is intentionally fail-closed until a real native AIEdge/Metal
inference backend is implemented (the two `TODO`s). **Do not integrate this path into
any Khatt loop, Gate 8, or production governance flow until `swift test` is green** —
the fail-closed behavior must be proven by the tests first.
