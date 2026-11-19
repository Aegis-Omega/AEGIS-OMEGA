# AEGIS Ω / Sovereign Field — visual research and implementation decision

Date: 2026-10-11 · Existing PR: #745 · Issues: #768, #770, #760
Status: **SOURCE CANDIDATE / NOT ADMITTED**. This is NOT a claim of being the best interface globally.

## Distinct product idea

A spatial research atlas where a node is a *real indexed research source* and its inspection is an accountable action. Orbit the camera to navigate. Switch from **Spatial** to **Lineage** to view recorded limitations of the selected source, not fictitious scientific dependencies. The written research, status, and external references remain semantic HTML. This is not a screensaver, fake telemetry, marketing shader or evidence of proving a theorem.

Reused existing **ResearchWorkbench** source array and filters, **Holon Glass** CSS/material implementation, and the existing `/platform` route. The new component supersedes the visible `EvidenceFilament` slot without duplicating application routing or dependencies. It exports only **unsigned** metadata.

## Primary external technical / product references (inspected October 11)

| Primary reference | Applied rule | Deliberately NOT copied |
|---|---|---|
| [Apple — Materials](https://developer.apple.com/design/human-interface-guidelines/materials) | Optical/depth layers recede behind readable data; interactive controls preserve hierarchy | Do not use blurred glass for research prose or evidence |
| [Apple — Spatial Layout](https://developer.apple.com/design/human-interface-guidelines/spatial-layout/) | Depth describes position and user orientation | Do not displace text into hard-to-read 3D |
| [Google — CHI 2026 Expressive Design research](https://research.google/pubs/usability-hasnt-peaked-exploring-how-expressive-design-overcomes-the-usability-plateau/) | Support fast visual task targeting; test task outcomes, not purely visual opinion | Do not transplant study improvements to AEGIS as its own measurements |
| [OpenAI — Interactive math/science explanations](https://openai.com/index/new-ways-to-learn-math-and-science-in-chatgpt/) | Interactivity serves comprehension of real data | Do not copy brand marks, voice or interface |
| [Anthropic — Claude Design](https://www.anthropic.com/news/claude-design-anthropic-labs) | Iterate visual directions, test alternatives | Do not treat generated concept as finished product |
| [Linear — Calmer interface](https://linear.app/now/behind-the-latest-design-refresh) | Reduce competing chrome and prevent panel clutter | Do not equate dark themes with advanced design |
| [Three.js — WebGPURenderer](https://threejs.org/manual/pages/webgpurenderer) | WebGPU→WebGL2 fallback; account for TSL vs ShaderMaterial incompatibility | No unverified package upgrade or phantom dependency |
| [Three.js — Raycaster and disposal](https://threejs.org/docs/pages/Raycaster.html), [Memory disposal](https://threejs.org/manual/pages/how-to-dispose-of-objects.html) | Use authentic picking and explicit GPU cleanup when a Three.js adapter is justified | Do not add a library without lockfile/runtime support and lifecycle QA |

## Why no new Three.js dependency was committed

The hub dependency/lockfile is versioned, and local npm registry lookups failed with DNS `EAI_AGAIN`. Manually inventing lock integrity, using unapproved runtime CDN imports, or adding a version without a reproducible install would violate exact-source engineering. The current scoped candidate instead projects an actual data-derived 3D topology in a pure typed module, with the existing AEGIS WebGL2/GLSL optical material behind it. Future Three.js adoption should **replace**, not parallel, that rendering layer after a reproducible package install, static/mobile browser acceptance, GPU resource disposal tests and measured benefit.

## Tested boundaries

- Pure typed `hub/src/lib/fieldTopology.ts` and committed `hub/tests/field-topology.test.mjs`: 8 deterministic cases including empty, filtered, finite 3D coordinates, real-membership-only edges and unsigned export.
- Strict isolated component typecheck with a minimal React declaration shim: PASS, **not a full React build**.
- Isolated source-matched CSS/structure fixture: viewport 160 (representing narrow reflow at 200% zoom), 320, 390, 768, 1440: no horizontal overflow; six sources visible via spatial nodes or compact list; no node-node collisions; button hit targets measured at least 44px after repair. **Fixture rendering != authentic integrated React route**.
- Existing `SovereignMatter` SDF shader was previously validated separately via OpenGL ES, but **WebGL2 support and app integration in real browsers remain UNKNOWN**.
- All publicly unlicensed Library images remain excluded. No paid service, provider activity, authority, deployment, merge or protected-main mutation.

## Authentic release gate remains OPEN

Reproduce from exact head:
```sh
cd hub
npm ci
npm run test:experience
npm run build
```
Then run actual browser tests for `/`, `/platform`, `/console`, all other pre-existing routes, mobile Safari/Chrome; keyboard, screen-reader, reduced-motion, 320px 200%-zoom, real source navigation, color contrast, offline, context-loss and memory/field Core Web Vitals. Compare baseline/current-candidate task success with independent reviewers. Track actual `head_sha`, full CI status and signed/protected admission. `WORLD_BEST=NOT_ESTABLISHED`.

No production deploy, billing, secrets, or signing bypass authorized.
