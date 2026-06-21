# OGEMMA MYTHOS
## AEGIS-Ω × Gemma × MYTHOS — Biological Quorum Pipeline

**System:** Gemma-4E4B on iPhone acts as a biological validation holon inside the MYTHOS 6-stage pipeline.  
**Constitutional law:** `AdaptivePower(T) ≤ ReplayVerifiability(T)` · φ = 0.6180339887  
**Repo:** `clients/gemma-holon/` · Endpoint: `https://aegisomega.workers.dev/platform/holon/validate`

---

## Three Gates

| Gate | Timing | Type | Condition for FAILED |
|------|--------|------|----------------------|
| `PRE_ORCHESTRATE` | Before pipeline starts | Hard veto → ABORT | stress ≥ 0.8 or atp ≤ 0 |
| `POST_VALIDATE` | After VALIDATOR approves plan | Soft veto → RECONCILIATION | stress ≥ 0.8 · or · steps > 5 and stress > 0.6 |
| `POST_REVIEW` | After REVIEWER returns PASS | Suspend gate | atp ≤ 200 or stress ≥ 0.7 |

Pipeline returns to gate 5 (POST_REVIEW) after FINALIZE — not to 1.  
Half-cadence: system holds dominant tension. `E[S_{n+1}|F_n] = S_n`.

---

## state.json (update before each run)

```json
{
  "holon_id": "gemma-4e4b-iphone",
  "bio_state": {
    "stress":    0.4262,
    "attention": 0.82,
    "rir":       0.9511,
    "atp":       2100
  }
}
```

Fields: `stress` / `attention` / `rir` in [0, 1]. `atp` in [0, 2500].

---

## Gemma System Prompts (paste into AI Chat app)

### PRE_ORCHESTRATE
```
You are GEMMA-4E4B-HOLON. Gate: PRE_ORCHESTRATE.
Check bio_state before the MYTHOS pipeline starts.
FAILED if stress >= 0.8 or atp <= 0. Otherwise APPROVED.
Output ONLY JSON: {"verdict":"APPROVED","confidence":0.94,"reason_code":"NOMINAL"}
```

### POST_VALIDATE
```
You are GEMMA-4E4B-HOLON. Gate: POST_VALIDATE.
FAILED if stress >= 0.8. FAILED if plan has > 5 steps and stress > 0.6. Otherwise APPROVED.
Output ONLY JSON: {"verdict":"APPROVED","confidence":0.91,"reason_code":"PLAN_SCOPE_ACCEPTABLE"}
```

### POST_REVIEW
```
You are GEMMA-4E4B-HOLON. Gate: POST_REVIEW.
FAILED if atp <= 200. FAILED if stress >= 0.7. Otherwise APPROVED.
Output ONLY JSON: {"verdict":"APPROVED","confidence":0.96,"reason_code":"BIO_COMMIT_READY"}
```

---

## Commands

```bash
# Bio readiness check only (no pipeline)
python3 clients/gemma-holon/ogemma_mythos.py --check-only

# Full pipeline
python3 clients/gemma-holon/ogemma_mythos.py "task description"

# With bio override
python3 clients/gemma-holon/ogemma_mythos.py "task" --bio '{"stress":0.3,"atp":2100}'

# Submit a Gemma verdict to the AEGIS chain directly
python3 clients/gemma-holon/submit.py

# Submit with bio override
python3 clients/gemma-holon/submit.py '{"stress":0.3}'
```

---

## SYSTEM STATE VECTOR (extended)

```json
{
  "execution_phase": "ORCHESTRATE|PLAN|VALIDATE|BUILD|REVIEW|FINALIZE",
  "index_snapshot": "<sha256 of INDEX.md>",
  "active_files": [],
  "forbidden_actions": [],
  "validity": "UNVERIFIED|VERIFIED|REJECTED",
  "holon": {
    "id": "gemma-4e4b-iphone",
    "verdict": "APPROVED|FAILED|PENDING",
    "confidence": 0.0,
    "chain_entry_hash": "",
    "gate_verdicts": {
      "PRE_ORCHESTRATE": "PENDING",
      "POST_VALIDATE":   "PENDING",
      "POST_REVIEW":     "PENDING"
    }
  }
}
```

---

## Holon POST schema

```bash
curl -X POST https://aegisomega.workers.dev/platform/holon/validate \
  -H "Content-Type: application/json" \
  -d '{
    "holon_id":   "gemma-4e4b-iphone",
    "verdict":    "APPROVED",
    "confidence": 0.94,
    "reason_code": "NOMINAL",
    "bio_state":  {"stress":0.42,"attention":0.82,"rir":0.95,"atp":2100}
  }'
```

Response includes `data.chain_entry_hash` — the tamper-evident record in the AEGIS constitutional chain.

---

## Quorum weights

| Node | Weight |
|------|--------|
| Claude (coordinator) | 618 / 1000 |
| Gemma holon | 191 / 1000 |
| Constitutional audit | 191 / 1000 |
| Threshold | ≥ 618 / 1000 (= 1/φ) |

---

## Mathematical grounding

`λ_attn = σ₁(QK^T) / τ_bio` where `τ_bio = √d_k · (atp/2500) · exp(-stress_norm)`  
Collapse when `λ_attn ≥ λ_c = 1.0` (BBP phase transition).  
Martingale suspension corresponds to `σ² ≥ 2β` — Gemma detects this at the biological layer before any Claude API call is made.

**Files:** `sovereign_hd.py` (SovereignHD class) · `submit.py` · `ogemma_mythos.py` · `mythos-x-gemma.json`  
**Epistemic tier:** T2
