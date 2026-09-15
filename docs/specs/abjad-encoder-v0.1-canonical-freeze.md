# AbjadEncoder v0.1 — Canonical Freeze

Status: FROZEN

Classification: Exact Integer & Modular Encoding Kernel

Authority boundary:
- ARITHMETIC: EXACT / FAIL-CLOSED
- MOD-9 ORBIT CLASSIFICATION: EXACT
- MOD-12 ROUTING: DETERMINISTIC CONVENTION
- SEMANTIC/IDENTITY AUTHORITY: PROJECTION-BOUNDED

No implementation may strengthen these claims without a separately admitted specification revision.

## 1. Independent exact and modular accumulator channels

For canonical Abjad values `a_1, ..., a_n`, maintain four independent states:

- `S_exact`
- `S_9`
- `P_exact`
- `P_9`

with initial states `S_exact=0`, `S_9=0`, `P_exact=1`, `P_9=1` and recurrences

`S_9' = (S_9 + (a mod 9)) mod 9`

`P_9' = (P_9 * (a mod 9)) mod 9`

`S_exact' = checked_add(S_exact, a)`

`P_exact' = checked_mul(P_exact, a)`.

The exact channel is a sticky state machine: once either exact accumulator enters `Overflow`, that accumulator remains `Overflow` for the rest of the sequence. The modular channel continues independently and exactly.

Normative invariant:

`Exact = Overflow` DOES NOT imply `Mod9 = Unknown`.

Saturating arithmetic is forbidden for the v0.1 exact channel because saturation silently replaces arithmetic truth with a representable sentinel value.

## 2. Mod-9 orbit profile

The normative map is multiplication by 2 modulo 9. Its three disjoint orbits are:

- `O1 = {0}`, cycle length 1
- `O2 = {3,6}`, cycle length 2
- `O6 = {1,2,4,8,7,5}`, cycle length 6

For an integer `x`, define `r = x mod 9` and

`Profile_9(x) = (r, Orbit_9(r), L_9(r))`.

Examples fixed by this specification:

- `Profile_9(9) = (0,O1,1)`
- `Profile_9(3) = (3,O2,2)`
- `Profile_9(310) = (4,O6,6)`
- `Profile_9(180000) = (0,O1,1)`.

The legacy Gate 214 `Triadic/Hexadic` classifier is not the normative classifier for this profile.

## 3. Observability and authority domains

The encoder distinguishes three observability levels:

- `RAW_TEXT`
- `CANONICAL_LETTER_SEQUENCE`
- `AGGREGATE_PROFILE`

Raw text is first transformed by an externally versioned normalization specification:

`r --N_sigma--> w_canon`.

The v0.1 arithmetic kernel consumes `w_canon`; it does not claim that normalization is injective on Unicode strings.

If `N_sigma(r1) = N_sigma(r2)`, then any full encoding derived solely from the canonical sequence is equal for those raw inputs. Therefore an injectivity claim over raw text requires a separate proof about `N_sigma` and is outside this kernel.

On `CANONICAL_LETTER_SEQUENCE`, the full projection preserves ordered `canonical_letter_id` values and may therefore distinguish ordered canonical ID sequences.

The aggregate projection is

`E_agg(w) = (S_exact, P_exact, Profile_9(S), Profile_9(P))`.

Central projection-authority invariant:

`E_P(x) = E_P(y)` implies projection `P` cannot authorize a distinction between `x` and `y`.

An attempted inequality claim from an equal aggregate projection MUST fail closed as `OBSERVABILITY_AUTHORITY_BREACH`.

This does not assert that `x=y`; it asserts only that the chosen observable lacks authority to establish `x!=y`.

## 4. Dodecagonal routing

For each canonical Abjad value `a`, define the routing node `a mod 12`.

Routing uses the existing deterministic dodecagonal graph with neighbors `(i-1, i+1, i+6) mod 12`, visited in sorted order by deterministic BFS.

The resulting path is a reproducible routing convention only. It is not an Abjad theorem and carries no semantic or identity authority beyond the declared projection.

For Tariq values `(9,1,200,100)` the frozen node projection and path are:

`pi_12 = [9,1,8,4]`

`path = [9,3,2,1,2,8,2,3,4]`.

## 5. Digest serialization

Internal Rust storage MAY use `[u8;32]`, but serialized cross-runtime payloads MUST use exactly:

`"sha256:<64 lowercase hex>"`.

Normative rule:

`DigestJSON(d) = "sha256:" || lowercaseHex(d)`.

The following fields use this representation whenever present:

- `alphabet_spec_digest`
- `normalization_spec_digest`.

Uppercase hex, missing prefix, wrong length, and non-hex payloads are invalid.

## 6. ParetoMod9 Mode A

Mode A is a declared conditional Q-profile, not an intrinsic theorem of Abjad encoding.

The frozen points required by v0.1 are:

`F_A(O6) = (6, 1/2, -1/9)`

`F_A(O1) = (1, 0, -2/3)`.

Therefore

`F_A(O6) - F_A(O1) = (5, 1/2, 5/9)`

which lies in `Q_{>=0}^3 \ {0}` and establishes `O6 >_A O1` under declared Mode A.

No Mode A coordinates for `O2` are invented by this specification. Any comparison requiring an undefined Mode A point MUST fail closed.

## 7. Frozen regression ring

1. `9 -> (0,O1,1)` and `3 -> (3,O2,2)`.
2. Tariq `(9,1,200,100)` yields exact sum `310`, exact product `180000`, sum profile `(4,O6,6)`, product profile `(0,O1,1)`, node projection `[9,1,8,4]`, and path `[9,3,2,1,2,8,2,3,4]`.
3. For ten factors of `1000`, exact product is `Overflow` while modular product remains exactly `(1,O6,6)`.
4. Repeated routing of identical canonical input yields byte-identical path output.
5. `(200,100)` and `(100,200)` have identical aggregate projections but different full ordered projections; aggregate-only inequality evaluation returns `OBSERVABILITY_AUTHORITY_BREACH`.
6. Tariq sum orbit `O6` strictly dominates product orbit `O1` under Mode A with exact rational delta `(5,1/2,5/9)`.

## 8. Freeze rule

Further work after this point is implementation and verification, not semantic tightening. Any change to accumulator semantics, orbit definitions, observability domains, digest encoding, routing convention, or Mode A coordinates requires a new versioned specification and cannot silently mutate v0.1.
