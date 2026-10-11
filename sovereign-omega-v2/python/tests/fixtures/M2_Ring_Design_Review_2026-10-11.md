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


## Security ingress dependency (2026-10-11; issue #763 scope extension)

**Source witness:** `bridge.py` binds `HTTPServer(('0.0.0.0', port), BridgeHandler)` and previously accepted arbitrary `/gate_signal` JSON with wildcard CORS and preflight. A loopback-only gate guard is **not** a principal/authorization proof; in particular, a local reverse proxy may relay remote requests using a loopback peer address.

**Candidate changes and falsifiers:**
- `/gate_signal` rejects non-loopback TCP peers before reading request bytes or mutating M2/gate. `X-Forwarded-For` is ignored; IPv4-mapped IPv6 (`::ffff:127.0.0.1`) is explicitly denied (Python `ip_address(...).is_loopback` alone reports true).
- Browser-origin gate POSTs and CORS OPTIONS preflights are rejected. Wildcard Access-Control-Allow-Origin is not emitted for the gate route; unrelated endpoints retain their old CORS behavior, **which remains a separate audit obligation**.
- Gate payload requires JSON object, Content-Type application/json, unambiguous Content-Length 1..4096 and no Transfer-Encoding. Large/malformed/non-object requests are rejected before any gate mutation. Fixed maximum is a safety bound, not a measured application optimum.
- Valid local non-browser JSON producer remains supported. The current Cloud Run deployment contract expects `0.0.0.0`; this candidate will **deny legitimate remote gate writers** until a separately reviewed caller-authentication/authority envelope is implemented. No production or deployment configuration has changed.
- Local mirror transport mutation regression initially **FAILED** for mapped IPv6 loopback; the corrected guard then passed **7/7 unittest methods**. Mirror != hosted exact-head PASS; the source-bound AST tests are committed and must run on a fresh checkout.

**Residual blockers:** anyone who can submit raw HTTP from a local process (or from a loopback-address proxy) may still send gate signals. Application-level authenticated principal, scoped action approval, replay protections beyond monotonic sequence, provider trust boundary, all other mutating routes and rate/time limits remain unverified. Do not promote `/gate_signal` to a publicly usable governance API.

**Primary external references:**
- Python standard library security warning: https://docs.python.org/3.12/library/http.server.html
- OWASP API Top 10 API2:2023 authentication / API4:2023 resource consumption / API5:2023 function authorization: https://api-security.owasp.org/editions/2023/en/0x11-t10/
- OWASP API4 mitigations: https://api-security.owasp.org/editions/2023/en/0xa4-unrestricted-resource-consumption/

