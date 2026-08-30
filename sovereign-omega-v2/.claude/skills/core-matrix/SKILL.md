---
name: core-matrix
description: Automatically invoked when the user is working on the Python core matrix layer, asks about PGCS, TGCS, AFSE, epoch failsafe, gradient-anchor calibration, or the AMD RX 570 hardware constraints. Handles validation and integration of the Python inference layer with the TypeScript governance runtime.
---

# Core Matrix Skill

When invoked for the Python layer, follow this protocol:

Validate PGCS first. PGCS is the gating prerequisite for all downstream telemetry.
Run: python python/tests/stress_test.py --quick
If PGCS disk I/O is not zero, stop and address the memory issue before continuing.

For epoch failsafe validation:
Run: python python/tests/stress_test.py --crash-loops
Success criterion is T0 and non-negotiable: corruption_count must equal 0.

For the full 12-hour stress test:
Run: python python/tests/stress_test.py
All three criteria must pass simultaneously:
  PGCS: disk_swap_bytes_in = 0 AND disk_swap_bytes_out = 0
  Epoch Failsafe: corruption_count = 0
  Gradient-Anchor: drift_index D = 0 across 100,000 epochs

For Python/TypeScript integration:
Start the bridge: python python/bridge.py
The bridge exposes HTTP on port 7890 (configurable via SOVEREIGN_BRIDGE_PORT).
The TypeScript pipeline connects to it for hardware-bounded inference.

Core matrix constraints that must never be violated:
All temporal semantics use event sequence numbers, never time.time().
Bit-shifted integer arithmetic (Q16.16 fixed-point) in all determinism-critical paths.
The byte array is pre-allocated (4GB) and never dynamically resized.
All operations are user-space only — no kernel calls, no privileged system calls.
