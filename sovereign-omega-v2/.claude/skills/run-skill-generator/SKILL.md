---
name: run-skill-generator
description: Run the AEGIS skill generator to populate the constitutional skill catalog from seed sources
---

## Trigger

Invoked when the user asks to run, execute, or populate the skill catalog from the Cognitive Triad or manifest sources. Also triggered when checking that the constitutional sound floor is established.

## Behavior

1. Confirm working directory is `sovereign-omega-v2/`
2. Run the skill generator CLI:
   - **Cognitive Triad only** (default): `npx tsx scripts/import-skills.ts`
   - **Include core-agent + antigravity manifests**: `npx tsx scripts/import-skills.ts --all`
   - **Save catalog to JSON**: `npx tsx scripts/import-skills.ts --out=catalog.json`
3. Verify output shows all 3 Cognitive Triad seeds as CERTIFIED (coefficient > 5.0)
4. Confirm `Cognitive Triad : ALL 3 PRESENT ✓`
5. Confirm `propagate=YES` on all 3 network layers (LAN/IP/WWW) for each seed

## What to check

- Each skill shows `CERTIFIED` (not RESONANT or BREACH)
- `resonance_depth: 4/4` for all Cognitive Triad seeds
- Vortex labels are all `Triadic` (dr ∈ {3, 6, 9})
- `Cognitive Triad : ALL 3 PRESENT ✓` in summary
- `Constitutional sound floor established.`
- Script exits 0

## Reporting format

```
SKILL GENERATOR: [pass/fail]
Admitted : N
Rejected : N
Cognitive Triad : [ALL 3 PRESENT ✓ / INCOMPLETE ✗]
Catalog hash : [first 32 chars]...
```

## Notes

- The generator reads from `src/skill-harness/seeds.ts` (Cognitive Triad) and optionally
  `src/skill-harness/manifests/core-agents.ts` + `manifests/antigravity.ts` (--all flag)
- Each skill is validated through the 3-layer network resonance gate (LAN/IP/WWW)
- Only resonant skills are admitted to the catalog via `registerResonant()`
- Exit code 1 only if admitted === 0 (total failure); partial rejection exits 0
