# Coordinator Authority Boundary

**Baseline:** `main@21aa288a0086e6dc82fc3c6e0a1fd8cd1cfd27cd`  
**Status:** remediation candidate

The coordinator currently assigns neutral authority (`0.5`) to unmapped capabilities, missing skills, and roles without capabilities. This contradicts the merged V2 skill-authority law:

```text
unobserved capability => authority = 0
```

This slice replaces neutral fallback semantics with deterministic denial, routes scoring through `harness.sdk.skill_authority.safe_competency_score`, validates selected evidence references against the repository boundary, and emits content-addressed routing receipts.

The authority invariant is:

```text
score(capability) = 0
unless validated_runs >= 3 and evidence is valid
```
