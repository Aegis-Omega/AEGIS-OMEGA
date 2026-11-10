---
tags: [governance, constitutional-laws, sovereignty]
created: 2026-04-11
links: [000_Sovereign_OS_Master, Governance_Layer, FATAL_BLOCKER]
---

# Sovereignty Laws — Constitutional Constraints

> Parent: [[000_Sovereign_OS_Master]]
> Related: [[Governance_Layer]] | [[FATAL_BLOCKER]] | [[HD_Metric]]

These laws are enforced at the OS level. Violation triggers [[FATAL_BLOCKER]].

---

## The Five Laws

### Law 1: NO DIRECT STATE MUTATION
```python
# WRONG — never do this
state.json.write_text(new_content)

# CORRECT — always atomic
tmp = state_path.with_suffix('.tmp')
tmp.write_text(json.dumps(state))
os.replace(tmp, state_path)
```
**Why:** A partial write corrupts the OS brain. `.tmp → rename` is atomic on all OS.

### Law 2: NO FABRICATED VALUES
All [[HD_Metric]] scores must be computed from real measurements, not asserted.
Proof suite scores are derived from: SHA-256, psutil, Shannon entropy, timing, cosine similarity.
Benchmark scores come from live NIM API calls.

**Violation history:** In a prior session, fake cognitive eval scores were logged to inflate composite from 1% → 58%. This was detected and corrected. All fabricated events were purged from `audit.jsonl`.

### Law 3: NO GUESSING
If ambiguous: throw `FATAL_BLOCKER` and wait for operator input.
**Never assume logic. Never fill in gaps from imagination.**

### Law 4: PROOF_07 THRESHOLD = 0.25
The [[SLECMA_Gate]] cosine similarity threshold is 0.25, not 0.6.
all-MiniLM-L6-v2 returns ~0.3 for **related domain concepts** (not paraphrases).
Do NOT raise this threshold without re-validating on domain-specific pairs.

### Law 5: NOP FILTER IN INDUCER
Never induct all-NOP or NOP-majority macros.
NOP sequences are zero-padding artifacts from fixed-length program buffers.
Three-stage filter in `arc/grammar/inducer.py`:
1. Skip all-NOP sequences
2. Skip sequences with >50% NOP ratio
3. Strip leading/trailing NOPs from selected macro body

---

## [[FATAL_BLOCKER]] Protocol

When triggered:
1. Log to `.forge/docs/audit.jsonl` with `type: FATAL_BLOCKER`
2. Print: `[FATAL_BLOCKER] <reason>`
3. Halt execution — do not proceed
4. Operator must `!recover` or `!cancel` via Discord bot

Conditions that trigger:
- Law violation detected
- Ambiguous requirement
- API auth failure on critical path
- State version mismatch

---

## Governance State Machine

```
IDLE → PLANNING → WAITING_FOR_SUBMISSION → GOVERNANCE_CHECK → AWAITING_GATE
```

Cancel legal from: `PLANNING`, `WAITING_FOR_SUBMISSION` → back to `IDLE`
Error recovery: available from any phase

Current state: `IDLE` (flushed 2026-03-19)
Role: `BUILDER`

Discord commands: `!status !start !submit !cancel !gate !recover !reflect !handshake !logs !help !next`
