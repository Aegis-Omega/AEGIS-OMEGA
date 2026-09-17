# M1 Record Contract V2 — Diagnostic Disposition

Status: `DIAGNOSTIC_ONLY`

Authority effect: `NONE`

Production wiring: `NONE`

Base containment head: `914a01e3f1679f454031a280b91e5782150a8558` (PR #524)

Diagnostic candidate head before this disposition note: `2d7346885a618f419deae0103daf629833a06e18`

## Current implementation witness

The current `core_matrix.py::M1` is not a transitive hash chain.

For payload hashes `p_n = SHA256(payload_n)`:

- sequence 0 returns `SHA256(p_0 || p_0)` because the current slot is written before `prev_hash` is read;
- sequence 1 returns `SHA256(p_0 || p_1)`;
- sequence 2 returns `SHA256(p_1 || p_2)`;
- therefore the recurrence is adjacent-payload pairing, not `chain_n = SHA256(chain_(n-1) || p_n)`.

The hosted preregistered diagnostic reproduced this boundary with `6 PASS / 4 FAIL` before the reference contract existed.

## Reference contract

The inert `m1_record_contract_v2.py` defines:

- `M1_ENTRY_BYTES = 40`;
- `M1_HASH_BYTES = 32`;
- `M1_GENESIS_HASH = 32 zero bytes`;
- `chain_n = SHA256(previous_chain_hash || SHA256(payload_n))`;
- `entry_n = u64le(sequence_n) || chain_n`;
- `offset_n = 40 * (sequence_n mod slot_capacity)`;
- raw payload bytes are not stored in the M1 fixed-width record.

Hosted reference verification at `2d7346885a618f419deae0103daf629833a06e18` produced `27 PASS / 0 FAIL`.

## Explicitly not changed

- `core_matrix.py`
- `ledger_persist.py`
- Cloud Run deployment state
- `main`
- RH / Weil work
- cognitive manifests or authority

## Next machine-checkable transition

A later live cutover must prove, in one bounded runtime transition, that:

1. `core_matrix.py::M1` emits exactly the reference 40-byte entry semantics;
2. the previous chain hash is read before current-slot mutation, with zero genesis at sequence 0;
3. slot addressing uses logical record capacity, not byte-ring multiplication modulo raw region length;
4. `ledger_persist.py` derives the active M1 region size from the matrix instance rather than a hard-coded 4 GB profile;
5. save → restore → next event yields the same next chain hash as uninterrupted execution for both the default and Cloud Run profiles;
6. PR #524 containment remains fail-closed until the live cutover is separately admitted.
