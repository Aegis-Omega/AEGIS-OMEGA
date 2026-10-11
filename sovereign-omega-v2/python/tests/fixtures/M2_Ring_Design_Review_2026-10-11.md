# M2 ring design review — issue #763 (2026-10-11)

Status: **candidate-only / not admitted**. Review of checked-in implementation, not a claim of production readiness. No governance authority granted.

## Baselines examined

| Source | Grounded behavior | M2 application |
| --- | --- | --- |
| Linux tracing ring buffer | Explicit **overwrite** vs **producer/consumer** (drop/reject new data), with writer reserve/commit | Document current bounded overwrite; do **not** claim lossless storage |
| Linux BPF ringbuf | Separate producer/consumer positions, reserve and commit publication ordering | Adopt only if an M2 reader/retention requirement exists; not a justification to import complex concurrency now |
| LMAX Disruptor | Sequence-gated consumer progress prevents producer overruns | Future M2 reader must track consumed sequence or explicitly accept retention loss |
| CPython free-threading docs | Mutable memoryview access to the same underlying region needs external synchronization | Existing CoreMatrix RLock remains required; a single 8-byte slice assignment is **not** an atomic publication guarantee |

Sources (official):
- https://www.kernel.org/doc/html/latest/trace/ring-buffer-design.html
- https://www.kernel.org/doc/html/v6.2/bpf/ringbuf.html
- https://lmax-exchange.github.io/disruptor/user-guide/
- https://docs.python.org/3/builtins/threadsafety.html

## Verified source-bound design invariants (candidate)

- `N = floor(L/8)`, `event_capacity = ceil(N/2)`, `gate_capacity = floor(N/2)`, minimum `L = 16`.
- Event slot indexes are `[0, event_capacity)`; gate signal indexes are `[event_capacity, N)`. Cross-source overlap is impossible by construction, even for the same numeric sequence.
- Byte position is `8 * slot_index`, with `offset % 8 = 0` and `offset + 8 <= L`. `L % 8` bytes at the end remain untouched.
- Replay and writer source are bound to explicit inputs; `source` cannot be inferred from verifier length.
- Valid sequences are integers in `[0, 2^64)`; `CoreMatrix.process_event` rejects when its current sequence is `>= 2^64-1`, **before** invoking M1, because M1 increments before M2.
- The bridge rejects out-of-domain `/gate_signal` inputs before gate mutation; it advances the ACK sequence only after both guarded write calls return successfully.
- The two 32-bit fields are constructed before a **single** 8-byte slice assignment; this reduces the number of observable write operations but is *not* a hardware-atomic transaction.

## Actual capacity accounting

| Profile | M2 region L (bytes) | Full 8-byte slots | Event capacity | Gate capacity | Unused tail bytes |
| --- | ---: | ---: | ---: | ---: | ---: |
| Default 4 GiB arena | 1,288,490,188 | 161,061,273 | 80,530,637 | 80,530,636 | 4 |
| Checked-in Cloud arena | 80,530,636 | 10,066,329 | 5,033,165 | 5,033,164 | 4 |

Each source ring wraps; therefore it can overwrite an older slot after `capacity` further writes at appropriately colliding sequences. **No independent M2 memory reader or durability/recovery guarantee has been established.** A 50/50 split has **not** been empirically optimized.

## Falsifiable acceptance / research debt

1. Exact-head Actions tests must actually execute and produce a source-bound JSON receipt. `steps=[]`, no runner or infrastructure failures are *not* source-code failures or PASS.
2. Run mutation-negative tests: collapsing the namespace, using a byte-offset modulus, accepting bool/out-of-range sequences, and moving ACK before writes **must** fail the regression gate.
3. Verify source-call coverage and M2 writer locks; independent paths or a new read path must trigger review. Concurrency tests on CPython do not prove lock-free safety on free-threaded Python.
4. Any new M2 consumer or checkpoint reader requires explicit reserve/commit, record identity/version, retention and corruption detection. Until then **do not promote** the scratch-ring design to durable agent memory.
5. Bench against observed per-source write rates and retention targets *before* choosing capacity split or changing the overwrite policy.
6. Keep `main` protected and the PR in Draft until independent replay and human review.

Decision: **minimal disjoint aligned storage is a justified candidate correction**, but world-leading reliability requires evidence for the full storage and consumer contract, not optimistic labels.
