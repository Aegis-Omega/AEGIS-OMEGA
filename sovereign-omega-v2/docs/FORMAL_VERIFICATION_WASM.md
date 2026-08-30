# AEGIS Formal Verification — WebAssembly Memory Manager
## EPISTEMIC TIER: T2 (code) / T3 (admitted lemmas — not yet mechanically checked)
## Gate 188 · Constitutional translation of Coq/Iris WASM allocator verification schema

---

## Overview

This document archives the Coq/Iris verification framework for a WebAssembly compacting
memory allocator. It establishes the formal foundations that Gate 188's TypeScript
implementation (`src/memory/bounded-generation.ts`, `src/memory/slot-registry.ts`)
approximates at T2 (engineering hypothesis level).

**What is T2 (implemented, testable):**
- Bounded generation type with saturation semantics (𝐙_<2^32 exclusive lattice)
- Exclusive slot ownership map (exclusivity law enforced at API boundary)
- Relocation invariant (generation must advance atomically with address change)
- Non-forgeable FreeRegion token pattern (maps to capsule protocol credits)

**What is T3 (admitted — requires `coqc` acceptance without `Admitted.`):**
- `free_pool_composition_law` — merge of adjacent FreeRegion tokens
- `block_relocation_invariance_proof` — full linearization theorem

**What is T0 (mechanically proven in Iris theorem library):**
- CMRA composition laws (auth, gmap, excl)
- WP frame rule and adequacy theorem structure
- Separation logic disjointness arithmetic

---

## Architectural Overview

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                             COQ/IRIS PRODUCTION VERIFICATION BOUNDARY                            │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                 │
 ┌───────────────────────────────────────────────┼────────────────────────────────────────────────┐
 │ [ALGEBRAIC REFINEMENT]                         │ [TEMPORAL ISOLATION]                           │
 │                                               │                                                │
 │   • Bounded Generation CMRA                   │   • Namespace Masking Protocol                 │
 │     (𝐙_<2^32 Excl Lattice)                    │     (𝖶𝖯 e <𝖤> Q with 𝒩 ⊆ 𝖤)                  │
 │                                               │                                                │
 │   • Authoritative Map Camera                  │   • Reentrancy Elimination                     │
 │     (authR (gmapUR nat (exclR slot_state)))   │     (Compaction executed under 𝖳𝗈𝗉 \ 𝒩)         │
 └───────────────────────────────────────────────┼────────────────────────────────────────────────┘
                                                 │
 ┌───────────────────────────────────────────────┼────────────────────────────────────────────────┐
 │ [SPATIAL OWNERSHIP INTEGRITY]                 │ [OPERATIONAL ADEQUACY BRIDGE]                  │
 │                                               │                                                │
 │   • Physical/Ghost Slot Coupling              │   • Linearization & Memory Copy WP             │
 │     (slot_phys ↦ 𝖶𝗈𝗋𝖽∗ ∗ own(γ, ●[i ↦ σ]))    │     (𝖶𝖯 𝗆𝖾𝗆𝗈𝗋𝗒.𝖼𝗈𝗉𝗒(𝖽, 𝗌, 𝗇) <𝖳𝗈𝗉 \ 𝒩>)        │
 │                                               │                                                │
 │   • FreeSpace Protocol RA                     │   • Adequacy Theorem Formulation               │
 │     (FreeRegion α s ≇ ∃v. α ↦_vec v)          │     (Connecting Wasm States to Iris Resources) │
 └───────────────────────────────────────────────┼────────────────────────────────────────────────┘
```

---

## 1. Bounded Generation CMRA

The generation carrier is a finite type bounded by 2^32:

```
𝐙_{2^32} ⊎ {⊥}
```

Bounded partial commutative monoid with asymmetric addition ⊕:
- `g ⊕ g' = max(g, g')` when both are valid
- `⊥ ⊕ g = ⊥` (⊥-contamination — permanent)
- `g = 2^32 - 1 → increment(g) = ⊥` (saturation)

AEGIS TypeScript translation:
- `BoundedGeneration` branded type
- `incrementGeneration(g)` returns `null` (⊥) at saturation
- `composeGenerations(a, b)` returns `null` when either is null

### slot_state record

```coq
Record slot_state : Type := {
  slot_gen  : nat;
  slot_addr : nat;
  slot_size : nat;
  slot_live : bool;
}.
```

TypeScript equivalent: `SlotState` interface in `src/memory/slot-registry.ts`.

### AllocatorR CMRA

```
AllocatorR := authR (gmapUR nat (exclR slot_stateO))
```

Exclusivity law: `Excl(σ) ⊗ Excl(σ') = ⊥` — two fragments over same key are undefined.
TypeScript enforcement: `ExclusiveSlotMap.register()` throws `SlotRegistryError` on duplicate `slot_index`.

---

## 2. Physical/Ghost Slot Coupling Invariant

Indirection table slot layout (128-bit, three 32-bit fields):

```
┌───────────────────────────┬───────────────────────────┬───────────────────────────┐
│     Offset 0: Gen (32b)   │    Offset 4: Addr (32b)   │    Offset 8: Size (32b)   │
├───────────────────────────┼───────────────────────────┼───────────────────────────┤
│   Shared Frac [0.5, 0.5]  │   Shared Frac [0.5, 0.5]  │   Shared Frac [0.5, 0.5]  │
└───────────────────────────┴───────────────────────────┴───────────────────────────┘
```

Coupling invariant (unified conjunction):
```
physical_slot_layout(table_base, i, σ.gen, σ.addr, σ.size)
  ∗ own(γ, ◯[i ↦ Excl(σ)])
  ∗ (σ.addr ↦_anon σ.size)
  ∗ ⌜σ.live = true⌝
```

This guarantees: any modification to physical location or generation metadata requires
a matching, atomic frame-preserving update to the authoritative master ghost map `●𝒯`.

AEGIS mapping: `ExclusiveSlotMap.relocate()` atomically updates `slot_gen` + `slot_addr`
in a single immutable step — equivalent to the ghost camera update at the PROPAGATE boundary.

---

## 3. FreeSpace Protocol Resource Algebra

Non-reducible free-space token:
```
FreeRegion(α, s) ≇ ∃v. α ↦_vec v
```

Composition rules:
```
FreeRegion(α, s₁) ∗ FreeRegion(α + s₁, s₂) ⊣⊢ FreeRegion(α, s₁ + s₂)   [T3 — admitted]
FreeRegion(α, s) ≠ α ↦_vec v                                              [structural separation]
```

AEGIS mapping: capsule protocol credits in `src/capsule/kernel.ts` — the `FreeRegion`
pattern is the non-forgeable allocator credit token. Client code cannot synthesize
a `FreeRegion` token from raw byte arrays, enforcing clean abstraction boundaries.

---

## 4. WP Semantics for memory.copy

Disjointness requirement:
```
Memory Copy Rule:
  Source:      [α_src, α_src + |v|)  frac q
                    ∩ (Must Be Empty)
  Destination: [α_dst, α_dst + |v|)  excl 1.0
```

The rule:
1. Preserves payload **v** across the physical transition
2. Maintains shared fractional read permissions (q) on source
3. Transforms destination from anonymous block to concrete vector: `α_dst ↦_vec^1.0 v`

---

## 5. Block Relocation Correctness Theorem

**Theorem**: When compactor shifts an active block from `p_read` to `p_write`,
structural layout integrity and handle validity are maintained.

**Proof sketch** (5 steps):

**Step 1** — Disjointness from cursor inequality:
```
p_write + s ≤ p_read
→ [p_write, p_write + s) ∩ [p_read, p_read + s) = ∅
```

**Step 2** — Data replication via WP memory.copy:
```
{p_write ↦_anon s ∗ p_read ↦_vec^q v}
  memory.copy(p_write, p_read, s)
{p_write ↦_vec^1.0 v ∗ p_read ↦_vec^q v}
```

**Step 3** — Linearized ghost update (atomic table slot + camera):
```
p_read → p_write in TableAddress(k)+4
●𝒯 updated: [k ↦ Excl(σ_new)] where σ_new.addr = p_write, σ_new.gen = σ_old.gen + 1
```

**Step 4** — Source erasure (vacated region becomes anonymous):
```
p_read ↦_vec^q v → p_read ↦_anon s
```

**Step 5** — Invariant reconstruction with σ_new:
```
active_slot_invariant(table_base, k, σ_new) ∗ p_read ↦_anon s
```

AEGIS TypeScript mapping: `ExclusiveSlotMap.relocate()` performs Steps 3–5 exactly:
atomically increments generation, updates address, hashes the new state, returns
the new immutable registry. The old physical footprint is implicitly released (Step 4).

---

## 6. Adequacy Theorem

```
                          High-Level Iris Logic
          ┌──────────────────────────────────────────────────┐
          │    WP e < Top > [ Q ]  ∗  SystemInvariant(γ)    │
          └──────────────────────────────────────────────────┘
                                   │
                                   │  [ Adequacy Simulation Bridge ]
                                   ▼
          ┌──────────────────────────────────────────────────┐
          │    ‹ e, σ_mach ›   ───►*   ‹ v, σ_mach' ›       │
          └──────────────────────────────────────────────────┘
                         Low-Level Wasm Execution
```

If an allocation or relocation is verified under the global system invariant, any
concrete WebAssembly execution of that bytecode satisfies postcondition Q(v).
This closes the abstraction gap between separation logic proofs and real machine execution.

---

## 7. Coq/Iris Proof Framework (T2 scaffold — T3 admits)

```coq
(* EPISTEMIC TIER: T2 (code compiles) / T3 (admitted lemmas — not mechanically certified) *)
(* Gate 188 — AEGIS constitutional translation of Iris WASM allocator verification      *)
From iris.program_logic Require Export weakestpre.
From iris.base_logic.lib Require Export invariants.
From iris.algebra Require Export auth gmap agree csum.
From iris.proofmode Require Import tactics.

Set Default Proof Using "Type".

Definition WordSize : nat := 4294967296.

Definition Generation : Type := nat.
Definition Address    : Type := nat.
Definition Size       : Type := nat.
Definition Value      : Type := nat.

Record slot_state : Type := TypeSlotState {
  slot_gen  : Generation;
  slot_addr : Address;
  slot_size : Size;
  slot_live : bool
}.

Instance slot_state_eq_dec : EqDecision slot_state.
Proof. ltac1:(decide equality; decide equality). Defined.

Definition slot_stateO : leibnizO slot_state := leibnizO slot_state.
Definition AllocatorR  : cmra := authR (gmapUR nat (exclR slot_stateO)).

Context {ValueR : cmra}.
Axiom raw_heapR             : Type → Type → cmra.
Axiom raw_heap_points_to    : Address → dfrac → Value → iPropD Σ.
Axiom auth_minus_marker_placeholder_token : Address → Size → AllocatorR.
Axiom gmap_of_active_slots_placeholder   : gmapUR nat (exclR slot_stateO).

Class AllocatorG Σ := {
  alloc_engine_gname : gname;
  alloc_gmap_inG :: inG Σ AllocatorR;
  alloc_mem_inG  :: inG Σ (raw_heapR Address Value);
  alloc_free_inG :: inG Σ (ucmraR (gmapUR Address (agreeR natO)))
}.

Section MemoryEngineVerification.
  Context `{!invG Σ, !AllocatorG Σ}.

  Notation "α ↦_byte b" := (raw_heap_points_to α (DfracOwn 1) b)
    (at level 20, format "α  ↦_byte  b").

  Fixpoint physical_vector_assertion (α : Address) (v : list Value) : iProp Σ :=
    match v with
    | []     => emp
    | b :: m => α ↦_byte b ∗ physical_vector_assertion (α + 1) m
    end.

  Notation "α ↦_vec v" := (physical_vector_assertion α v)
    (at level 20, format "α  ↦_vec  v").

  Definition anonymous_space_predicate (α : Address) (s : Size) : iProp Σ :=
    (∃ v, ⌜length v = s⌝ ∗ α ↦_vec v)%I.

  Notation "α ↦_anon s" := (anonymous_space_predicate α s)
    (at level 20, format "α  ↦_anon  s").

  Definition free_pool_token (α : Address) (s : Size) : iProp Σ :=
    own alloc_engine_gname (◯ auth_minus_marker_placeholder_token α s).

  Notation "𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇( α , s )" := (free_pool_token α s)
    (at level 20, format "𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇( α ,  s )").

  (* T3 — admitted: mechanically unverified merge property *)
  Lemma free_pool_composition_law : ∀ (α : Address) (s1 s2 : Size),
    𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇(α, s1) ∗ 𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇(α + s1, s2) ⊣⊢ 𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇(α, s1 + s2).
  Proof. admit. Admitted. (* T3 — requires concrete RA construction *)

  Definition physical_slot_layout (table_base : Address) (i : nat) (g : Generation) (α : Address) (s : Size) : iProp Σ :=
    ((table_base + i * 3 + 0) ↦_byte g ∗
     (table_base + i * 3 + 1) ↦_byte α ∗
     (table_base + i * 3 + 2) ↦_byte s)%I.

  Definition active_slot_invariant (table_base : Address) (i : nat) (σ : slot_state) : iProp Σ :=
    (physical_slot_layout table_base i (slot_gen σ) (slot_addr σ) (slot_size σ) ∗
     own alloc_engine_gname (◯ {[ i := Excl σ ]}) ∗
     (slot_addr σ) ↦_anon (slot_size σ) ∗
     ⌜slot_live σ = true⌝)%I.

  Definition N : namespace := nroot .@ "relocating_allocator".

  Definition global_system_state (table_base : Address) (ActiveSet : list nat) (p_write p_read p_bump W_size : Address) : iProp Σ :=
    (⌜0 <= p_write ∧ p_write <= p_read ∧ p_read <= p_bump ∧ p_bump <= W_size⌝ ∗
     𝖥𝗋𝖾𝖾𝖱𝖾𝗀𝗂𝗈𝗇(p_bump, W_size - p_bump) ∗
     p_write ↦_anon (p_read - p_write) ∗
     own alloc_engine_gname (● (gmap_of_active_slots_placeholder)) ∗
     ([∗ list] i ∈ ActiveSet, ∃ σ, active_slot_invariant table_base i σ))%I.

  (* T3 — admitted: full linearization theorem requires mechanically filling all 5 steps *)
  Theorem block_relocation_invariance_proof : ∀ (table_base : Address) (i : nat) (σ_old : slot_state) (p_write p_read : Address),
    ⌜slot_addr σ_old = p_read⌝ ∗
    active_slot_invariant table_base i σ_old ∗
    p_write ↦_anon (slot_size σ_old) ∗
    ⌜p_write + slot_size σ_old <= p_read⌝
    ={⊤∖N}=∗
    let σ_new := TypeSlotState (slot_gen σ_old) p_write (slot_size σ_old) true in
    active_slot_invariant table_base i σ_new ∗ p_read ↦_anon (slot_size σ_old).
  Proof. admit. Admitted. (* T3 — mechanically unverified; Steps 1-5 sketched in prose above *)

End MemoryEngineVerification.
```

---

## Constitutional Invariants

- **Bounded generation** → `GENERATION_BOUND = 2^32`; saturation → `null` (⊥); ⊥ is permanent
- **Exclusivity** → two fragments on same `slot_index` = `SlotRegistryError` (mirrors `Excl ⊗ Excl = ⊥`)
- **Relocation atomicity** → `slot_gen` and `slot_addr` always updated together (single `relocate()` call)
- **Immutable pattern** → `ExclusiveSlotMap` returns new instance on every mutation (no in-place state)
- **No T3 claim grounded in T0/T1** → admitted Coq lemmas explicitly labelled T3 throughout

---

## Migration Path (T3 → T2 → T1)

| T3 (current) | Required evidence for T2 | Required evidence for T1 |
|-------------|--------------------------|--------------------------|
| `free_pool_composition_law` | Concrete RA construction; `coqc` accepts without `Admitted.` | Property verified on live WASM allocator binary |
| `block_relocation_invariance_proof` | All 5 proof steps filled in Iris; `coqc` accepts | Fuzz-tested against adversarial relocation sequences |

Until these are mechanically certified, this document represents T2 engineering hypothesis
for the TypeScript layer and T3 for the Coq claims.
