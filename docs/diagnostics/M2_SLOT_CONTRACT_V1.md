# M2 Slot Contract V1 — Diagnostic Disposition

Status: `DIAGNOSTIC_ONLY`

Authority effect: `NONE`

Production wiring: `NONE`

Base: `main` at `495bfd85d79abcb2b4f6898fe9c156488492426a`

## Current implementation witness

The shipped M2 address expression is:

```text
offset = (sequence * 8 + len(verifier_result)) % (len(state) // 8)
```

and the resulting value is then used directly as a **byte offset**.

This mixes two units:

- numerator: bytes;
- modulus: count of 8-byte slots;
- result: treated again as bytes.

Consequences machine-reproduced by the diagnostic:

1. sequence 0 with a one-byte verifier writes at byte 1, not aligned slot 0;
2. the same logical sequence moves when verifier length changes;
3. on an 80-byte / 10-slot witness, verifier length 1 yields starts
   `1,9,7,5,3,1,...`, so sequence 0 and sequence 5 collide exactly;
4. the starts are unaligned and remain in the first ten bytes instead of covering
   ten non-overlapping 8-byte slots;
5. #510's theorem `8 ∤ M2_SIZE` is true but is not a complete model of this live
   expression, because the code is not `(8 * sequence) % region_bytes`.

## Live geometry

Default 4 GB profile:

```text
M2 region bytes = 1,288,490,188
slot capacity   =   161,061,273
tail bytes      =             4
```

Cloud 256 MiB profile:

```text
M2 region bytes = 80,530,636
slot capacity   = 10,066,329
tail bytes      =          4
```

The four tail bytes are not themselves a defect under slot-indexed addressing;
they are simply outside the complete-record capacity.

## Reference contract

The inert `m2_slot_contract_v1.py` defines:

```text
entry_n  = vcg_error_fixed:u32le || gate_lcb_fixed:u32le
capacity = floor(region_bytes / 8)
offset_n = 8 * (sequence_n mod capacity)
```

Verifier bytes determine M2 values but never the record address.

## Evidence

Preregistered RED head: `43686f6d0b00cc31f3f455edf84da99013f9f68a`

Hosted RED run `35284762352`: `16 PASS / 3 FAIL`.

The 16 PASS results reproduce the current implementation defect. The three
FAIL results were only the missing inert reference-contract obligations.

Reference implementation head: `91401ea0984ec42bd2e216cf70e3d8c04b0a0e14`

Hosted run `35284826805`: `35 PASS / 0 FAIL`.

## Explicitly not changed

- `core_matrix.py`
- M1 runtime/persistence stack
- `main`
- deployment state
- RH / Weil work
- cognitive manifests or authority

## Smallest next live transition

A later live M2 cutover should replace only the storage-address computation with
logical record-slot addressing while preserving the existing returned
`(vcg_error_fixed, gate_lcb_fixed)` values.

The live transition must prove:

1. same sequence + different verifier lengths write the same slot;
2. consecutive sequences use distinct non-overlapping aligned slots until wrap;
3. sequence `capacity` wraps exactly to byte zero;
4. default and Cloud geometries use every complete slot and never touch the four
   tail bytes;
5. both `process_event()` and `receive_gate_signal()` address the same logical
   sequence deterministically;
6. no M1, checkpoint, RH/Weil, deployment, or authority surface changes.
