---
name: security-scan
description: Security audit before any production commit or deployment. Invoked when the user says "security scan", "audit", "safe to deploy", or before a Vercel deployment. Checks AEGIS-specific attack surfaces including hash tampering, input validation, API key leakage, and constitutional invariant bypass.
---

# Security Scan Skill

Run this before any production deployment. Report every finding — do not suppress low-severity issues.

## Scan Protocol

### 1. SECRET DETECTION
Check that no secrets are staged or committed:
```bash
git status --short | grep -E '\.env$'
git diff --cached | grep -E 'VITE_|API_KEY|api_key|secret|password|token' | grep -v '\.env\.example'
```

Assert: no `.env` files staged, no literal secrets in diff.

Never-commit files (hard stop if any are staged):
- `cockpit/.env`, `platform-picker/.env`, `hook-generator/.env`
- `content-calendar/.env`, `sovereign-omega-v2/.env`
- `~/aegis/server-setup.sh`, `~/.hermes/config.yaml`

### 2. FROZEN FILE INTEGRITY
```bash
cd sovereign-omega-v2 && node scripts/verify-hashes.mjs
```
Assert: exits 0. If any constitutional file hash mismatches → HALT, invoke `/frozen-file-check`.

Constitutional files (NEVER modify without /guardian APPROVED):
- `sovereign-omega-v2/python/gate.py`
- `sovereign-omega-v2/python/dna.py`
- `sovereign-omega-v2/python/router.py`

### 3. RUST SECURITY PATTERNS
Check aegis-cl-psi for:

**Integer overflow (CRITICAL):**
```bash
grep -rn "\.wrapping_\|overflow\|as u32\|as u64" aegis-cl-psi/src/ | grep -v "test\|//\|saturating"
```
All arithmetic must use `saturating_add`/`saturating_mul`. Bare `as u32`/`as u64` casts on potentially large values are suspect.

**Hash canonicalization (CRITICAL):**
```bash
grep -rn "to_le_bytes\|little_endian" aegis-cl-psi/src/
```
Assert: empty. All hash inputs must use `to_be_bytes()`.

**HashMap usage (DETERMINISM VIOLATION):**
```bash
grep -rn "HashMap\|use std::collections::Hash" aegis-cl-psi/src/ | grep -v "//\|test"
```
Assert: empty. Only `BTreeMap`/`BTreeSet` permitted.

### 4. TYPESCRIPT SECURITY PATTERNS

**XSS/injection in commercial products:**
```bash
grep -rn "dangerouslySetInnerHTML\|innerHTML\s*=" platform-picker/src hub/src hook-generator/src content-calendar/src cockpit/src 2>/dev/null | grep -v "//\|test"
```

**Unguarded JSON parse (OWASP):**
```bash
grep -rn "JSON\.parse(" sovereign-omega-v2/src/ | grep -v "try\|catch\|test\|//"
```
All `JSON.parse` must be inside try/catch.

**JSON.stringify for integrity (constitutional violation):**
```bash
grep -rn "JSON\.stringify" sovereign-omega-v2/src/ | grep -v "test\|//\|replacer\|log\|analytics"
```
Assert: empty. Use `canonicalizeJCS` for all integrity-critical operations.

**Date.now() outside uuid.ts:**
```bash
grep -rn "Date\.now()" sovereign-omega-v2/src/ | grep -v "uuid\.ts\|test\|//"
```
Assert: empty outside `src/event/uuid.ts`.

### 5. PYTHON BRIDGE SECURITY

**Command injection:**
```bash
grep -n "subprocess\|os\.system\|eval\|exec(" sovereign-omega-v2/python/bridge.py
```
All subprocess calls must use list args (not shell=True). `eval`/`exec` prohibited unless in frozen file.

**CORS configuration:**
```bash
grep -n "CORS\|Access-Control\|allow_origin" sovereign-omega-v2/python/bridge.py
```
Verify CORS is not wildcard `*` in production config.

### 6. DEPENDENCY AUDIT

**Rust:**
```bash
cd aegis-cl-psi && cargo audit 2>/dev/null || echo "cargo-audit not installed — skip"
```

**TypeScript:**
```bash
cd sovereign-omega-v2 && npm audit --audit-level=high 2>/dev/null | tail -5
```

## Reporting Format

```
SECURITY SCAN REPORT — <date>
  Secrets detected:        CLEAN / FOUND: <list>
  Frozen file integrity:   PASS / FAIL: <file>
  Rust integer safety:     PASS / VIOLATIONS: <list>
  Rust hash endianness:    PASS / VIOLATIONS: <list>
  Rust HashMap usage:      PASS / VIOLATIONS: <list>
  TS XSS patterns:         PASS / FOUND: <list>
  TS JSON integrity:        PASS / VIOLATIONS: <list>
  TS Date.now() usage:     PASS / VIOLATIONS: <list>
  Python injection:        PASS / FOUND: <list>
  Python CORS:             PASS / REVIEW NEEDED
  Dependency audit:        PASS / HIGH: <N> vulns

VERDICT: CLEAR TO DEPLOY / BLOCKED — <reason>
```
