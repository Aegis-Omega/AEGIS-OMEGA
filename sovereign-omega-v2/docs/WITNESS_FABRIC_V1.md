# AEGIS Always-On Witness Representation Fabric V1

Status: **DRAFT CANDIDATE / MACHINE-TESTED ON BRANCH**  
Authority effect: **NONE**

## Purpose

The witness fabric is the always-on observational layer for the Python bridge. It converts each admitted runtime observation into one hash-chained receipt with four simultaneous representation surfaces:

1. **coding** — exact canonical bytes and cryptographic commitment;
2. **sequence** — finite-field and Abjad sequence witnesses;
3. **structure** — value-independent structural-shape commitment;
4. **meaning lineage** — typed declared meaning bound to context/history/provenance without claiming truth.

It starts automatically with `run_bridge()`. It is deliberately a daemon worker **inside the bridge process**, not a second CoreMatrix process: a second OS process would create an unnecessary memory/fork boundary around a runtime whose CoreMatrix may reserve gigabytes. The worker has no gate, router, mutation, admission, deployment, or execution authority.

## 1. Coding layer

Every observation is canonicalized as exactly one of:

- `AEGIS_WITNESS_RAW_BYTES_V1`;
- `AEGIS_WITNESS_UTF8_V1`;
- `AEGIS_WITNESS_JSON_V1` — sorted-key compact UTF-8 JSON.

The receipt stores only:

- canonicalization profile;
- byte length;
- SHA-256.

Generic raw payload bytes are **not persisted** in the receipt log.

### Universal F_101 byte encoding

Any byte `b ∈ [0,255]` is encoded losslessly as two elements of `F_101`:

```text
q = floor(b / 101)
r = b mod 101
b = 101*q + r
```

Because `q ∈ {0,1,2}` and `r ∈ [0,100]`, this is an exact reversible map for all 256 byte values.

The receipt does not persist the entire generic coefficient vector. It persists deterministic affine evaluations and the coefficient count; SHA-256 remains the exact source commitment.

## 2. Sequence layer

For a coefficient sequence `x=(c_0,...,c_{n-1})` over `F_101`:

```text
E_t(x) = Σ c_i t^i
A_t(x) = (E_t(x), t^n)
```

Ordered concatenation uses:

```text
(e,u) ⋆ (f,v) = (e + u f, u v) mod 101
```

Therefore:

```text
A_t(XY) = A_t(X) ⋆ A_t(Y)
```

and any order-preserving partition of the same sequence must fold to the same state.

V1 records fixed points:

- `t=0` — first-symbol projection behavior;
- `t=1` — additive coordinate;
- `t=35` — generic order-sensitive coordinate used by the existing affine-monoid work;
- `t=100=-1` — alternating/parity-sensitive coordinate.

The small F_101 value bundle is a **diagnostic algebraic fingerprint**, not a unique locator and not proof.

## 3. Cryptographic short carrier

Each receipt also exposes a compact lookup carrier derived from the first 72 bits of the payload SHA-256 and encoded base64url.

Properties:

- approximately 12 printable characters;
- lookup/index role only;
- collisions are never silently resolved;
- zero matches -> `NOT_FOUND`;
- one match -> `RESOLVED`;
- multiple matches -> `AMBIGUOUS`.

The short carrier never replaces the full SHA-256 receipt identity.

This is the operational form of “a few characters carry a much larger message”: the characters are a compact pointer into already shared AEGIS state, not a standalone proof or magical decompressor.

## 4. Canonical Abjad specialization

When a payload is an explicitly canonical Abjad sequence, V1 adds the stronger Abjad projection.

Frozen alphabet:

```text
ابجدهوزحطيكلمنسعفصقرشتثخذضظغ
```

No Unicode normalization is invented. Whitespace may separate canonical letters; any other unsupported character makes the Abjad projection inapplicable.

The receipt records:

- canonical sequence commitment;
- exact Mashriqi sum;
- exact Maghribi sum;
- the maximal universal common quotient `Z/10Z`;
- mod 9 / mod 12 / mod 36 summaries for both profiles;
- lossless classical-letter symbols in `F_101`;
- `E_1 = MashriqiSum mod 101`;
- affine states at the fixed points above.

The six moved weights are the existing cross-profile cycle:

```text
60 -> 300 -> 1000 -> 900 -> 800 -> 90 -> 60
```

while the remaining 22 weights are fixed. The common mod-10 residue is intentionally weaker than exact profile identity.

## 5. Structural layer

The fabric walks the Python/JSON shape without persisting scalar values.

The shape digest binds:

- container type;
- object key type and key identity;
- list/tuple lengths;
- nested type topology.

The walk is bounded by maximum node count and depth. If either bound is exceeded, the structural receipt marks `complete=false`; it does not pretend that the truncated shape is complete.

## 6. Meaning lineage

Meaning is treated as a typed declaration, not as truth.

The meaning commitment binds:

- event kind;
- payload SHA-256;
- declared ontology;
- declared claim;
- context references;
- history references;
- provenance.

Persisted public fields include commitments and references rather than the raw declared claim.

Every meaning receipt carries:

```text
truth_status     = NOT_ESTABLISHED_BY_COMMITMENT
authority_effect = NONE
```

Operationally this follows the MHP rule:

```text
meaning_candidate =
  Decode(signal | admitted_context, ontology, history, time, provenance)
```

A valid commitment proves that the declaration was bound to those inputs. It does not prove proposition truth, intent, identity, or subjective meaning.

## 7. Background worker and persistence

`WitnessFabric` is one bounded writer:

- bounded queue;
- one daemon worker thread;
- append-only JSONL receipt log;
- monotone local witness sequence;
- SHA-256 parent link to the previous receipt;
- bounded recent-receipt and carrier index.

If the queue overflows, continuity is marked broken and further submission is denied. Events are never silently dropped while the fabric continues claiming an intact chain.

### Restart replay

Before accepting new observations, the worker streams the **entire existing JSONL log** and verifies for every receipt:

1. schema;
2. receipt SHA-256;
3. exact monotone sequence;
4. exact `prev_receipt_hash`.

Any failure sets:

```text
continuity_intact       = false
history_replay_verified = false
blocked_reason          = PERSISTED_CHAIN_INVALID
```

and no new receipt is appended.

A valid replay restores:

- next sequence;
- terminal hash;
- bounded recent receipts;
- bounded short-carrier lookup index.

## 8. Bridge coverage

The candidate observes:

- bridge lifecycle start/stop;
- metacognitive observations;
- `/gate_signal`;
- `/event`;
- `/claude`;
- `/claude/stream`;
- both synchronous and asynchronous 39-department collaboration, through their shared worker.

For streamed model output, the bridge maintains an exact UTF-8 digest. Up to the configured bounded capture limit (default 262,144 characters), the complete streamed response is also passed to the representation fabric. Above the limit, only digest/length metadata is witnessed; the stream itself continues normally.

## 9. Observability

`GET /health` includes bounded witness status.

`GET /witness` returns:

- public witness status;
- recent receipts.

`GET /witness?carrier=<short-carrier>` additionally performs collision-safe lookup.

Receipts expose commitments and typed metadata, not generic raw payload contents.

## 10. Persistence location

If `AEGIS_WITNESS_PATH` is set, that path is used.

Otherwise, when `AEGIS_CHECKPOINT_PATH` is configured, the witness log is created as the sibling:

```text
aegis_witness_v1.jsonl
```

The production Docker Compose bridge already mounts `/app/data` persistently and uses `restart: unless-stopped`, so the witness log shares the durable bridge volume without adding another service.

## 11. “Always-on” infrastructure boundary

“Always-on” here means: **whenever the AEGIS bridge process is alive, the witness worker is started automatically and cannot be omitted by an ordinary request path.**

It does **not** claim the cloud host itself is guaranteed to run 24/7.

The current Render blueprint uses a free plan that may spin down when idle. This candidate deliberately does not change that plan, purchase infrastructure, deploy, or create a billing effect. A true 24/7 host requires a non-sleeping deployment tier or another persistent runtime decision.

## 12. Explicit non-claims

This fabric does not establish:

- cryptographic signer identity;
- proposition truth;
- linguistic or subjective meaning;
- AGI;
- correctness of a model response;
- repository admission;
- execution authority;
- merge authority;
- production deployment.

Its job is narrower and load-bearing:

```text
signal
  -> exact coding commitment
  -> sequence witnesses
  -> structural commitment
  -> meaning lineage commitment
  -> hash-chained receipt
  -> replayable shared pointer
```

`authority_effect = NONE`
