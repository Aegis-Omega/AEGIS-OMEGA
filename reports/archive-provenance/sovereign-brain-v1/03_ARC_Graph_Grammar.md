---
tags: [ARC, grammar-induction, MDL, graph-world-model, macros]
created: 2026-04-11
links: [000_Sovereign_OS_Master, Grammar_Induction, MacroLibrary, GrammarVM, GraphWorldModel]
---

# ARC — Graph Grammar Induction Engine

> Parent: [[000_Sovereign_OS_Master]]
> Related: [[Grammar_Induction]] | [[MacroLibrary]] | [[GrammarVM]] | [[GraphWorldModel]] | [[GraphEncoder]]

The ARC solver treats grids as **object graphs**, not pixel arrays. It induces transformation grammars rather than learning pixel statistics.

---

## The Three-Level Abstraction

```
Level 0  PRIMITIVES    11 DSL ops hardcoded in dsl/vocab.py
          NOP  ROT90  ROT180  FLIP_X  FLIP_Y  TRANSPOSE
          INVERT  SHIFT_UP  SHIFT_DOWN  SHIFT_LEFT  SHIFT_RIGHT

Level 1  MACROS        Induced n-gram sequences (MDL criterion)
          e.g., MACRO_001_FLIP_X_ROT90  →  [FLIP_X, ROT90]
          Induced when: count*(len-1) > len+1  (Rissanen 1978)

Level 2  GRAMMAR       GrammarPolicy: TransformerDecoder over MacroLibrary
          Dynamic output head — expand_head() grows on each induction cycle
          New macro neurons initialized with bias = -2.0 (near-zero probability)
```

---

## [[GridToGraph]] — The Core Inductive Bias

ARC is about **objects**, not pixels. The encoder converts grids to graphs:

```python
# arc/model/graph_encoder.py
def grid_to_raw(grid: np.ndarray):
    # 1. Find connected components (same color, 4-connectivity)
    components = scipy.ndimage.label(grid)
    
    # 2. Extract 10-dim node features per component:
    node_features = [
        color_norm,      # normalized color value
        height_norm,     # bounding box height
        width_norm,      # bounding box width
        cy_norm,         # centroid y
        cx_norm,         # centroid x
        area_norm,       # component area
        aspect_ratio,    # h/w ratio
        density,         # filled / bounding box
        is_background,   # 1 if color == most common
        size_rank_norm,  # rank by area
    ]
    
    # 3. Extract 4-dim edge features between component pairs:
    edge_features = [
        dy_norm,        # vertical offset
        dx_norm,        # horizontal offset
        same_color,     # 1 if same color
        adjacent,       # 1 if bounding boxes touch
    ]
```

---

## [[GraphWorldModel]] — Object-Level Dynamics

```
G_{t+1} = F(G_t, A_t)
```

Edge-conditioned MPNN:
1. **Action injection**: `x_a = x + action_proj(action_emb(action))`
2. **Messages**: `msg = msg_mlp(cat[x_src, x_dst, edge_attr])`
3. **Aggregate**: `agg.index_add_(0, dst, messages)`
4. **Update**: `x_new = node_mlp(cat[x_a, agg])`
5. **Reward**: `reward_head(x_new.mean(0))`

This is the **world model** — it predicts what the graph looks like after applying an action, without executing it.

---

## [[Grammar_Induction]] — MDL Criterion (Rissanen 1978)

```
MDL saving = count * (len - 1) - (len + 1)
Accept macro iff MDL saving > 0

→ Bigrams (len=2):  count > 3
→ Trigrams (len=3): count > 2
```

**Why MDL?** The best grammar minimises `|Grammar| + |Data encoded by Grammar|`. A macro is only worth adding if its compression of the corpus exceeds its own description cost.

**NOP filtering (critical — never remove):**
1. Skip all-NOP sequences (zero-padding artifact)
2. Skip sequences with >50% NOP ratio
3. Strip leading/trailing NOPs from macro body after selection

---

## [[MacroLibrary]] — Dynamic Grammar Registry

```python
# Starts with 11 primitives
library = MacroLibrary()    # vocab_size = 11

# After induction cycle 1:
library.add_macros([rule1, rule2])  # vocab_size = 13

# Policy head grows to match:
policy.expand_head()  # adds 2 neurons, bias=-2.0
```

Persistence: `arc/checkpoints/macro_library.json`
MDL grammar cost: `Σ (rule.length + 1)` for all macros (primitives are free)

---

## [[GrammarVM]] — Transparent Execution

```python
# arc/grammar/vm_grammar.py
gvm.run(["ROT90", "MACRO_001_FLIP_X_ROT90", "NOP"], grid)
# Expands to: [2, 4, 2, 0]
# Executes on DSLVM
# Always reducible to primitive ops — no black box
```

---

## [[GrammarPolicy]] — Dynamic TransformerDecoder

Architecture:
```
GraphState → mean-pool → [d_model]
+ PositionalEmbedding(t)
→ TransformerDecoder (conditions on graph embedding)
→ Linear(d_model, |library|)   ← grows as macros are added
→ softmax over current rule set
```

Autoregressive sampling: `sample(graph, max_len=8)` → `(rule_indices, log_prob)`

---

## Training Protocol

```
Phase A  Steps 0 → induct_every:
  Train GrammarPolicy on current library
  Collect (graph_sig, program, reward) when reward > 0.5

Phase B  Every induct_every steps:
  GrammarInducer.induce() → new macros (MDL > 0)
  MacroLibrary.add_macros() → deduplicate by op_sequence
  GrammarPolicy.expand_head() → grow output head
  Rebuild Adam optimizer
  Clear corpus → repeat Phase A
```

**MDL Convergence signal:**
```
mdl_total = |Grammar| + Σ len(compressed_program_i)
Plateau = grammar at natural complexity
```

**Run:**
```bash
cd swarm_os/arc
python train_grammar.py --steps 20000 --arc-data data/arc_data --induct-every 1000
```

---

## Current Results (2026-04-11)

| Metric | Synthetic Tasks | Real ARC Tasks |
|--------|----------------|----------------|
| Success rate | 100% (50/50) | 8% (4/50) |
| Mean accuracy | 1.000 | 0.731 |
| Macros induced | 2 | 0 (untrained) |
| Avg beam depth | 1.66 | 1.42 |

The 8% real ARC success rate is on an **untrained model** (random weights). Training on `arc_data/` is required for competitive performance.
