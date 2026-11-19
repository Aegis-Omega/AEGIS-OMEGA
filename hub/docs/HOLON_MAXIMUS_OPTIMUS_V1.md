# AEGIS Ω — HOLON MAXIMUS OPTIMUS / first functional slice

**Status:** DRAFT / NOT_ADMITTED / NOT_DEPLOYED. Existing PR #745. No new branch, paid model calls, backend storage or authorization changes.

## Product invariant

Human creativity and judgment are first-class. This is a creative lineage workbench, not autonomous generation disguised as human thought.

- **Seed:** human-created first idea only; no model may forge a human seed.
- **Diverge:** human direction, or explicitly *pasted and unverified* external model/agent suggestion. The product does not call an LLM here.
- **Choose:** only a human may accept a direction. The resulting event points at one existing branch. A suggestion cannot promote itself.
- **Weave:** requires two to four **distinct** human-selected branches. The UI states the actual included count.
- **Craft:** a human-created description of intended work, following a weave. A record is not evidence that an artifact was built, published or independently verified.
- **Trace:** SHA-256-linked, explicitly versioned and bounded to 128 events, 1,600 UTF-16 code units per event, and 4 parents per event. Import rechecks each event, order, parent, role, fields and digest. Export is portable JSON. This is **not** a signed credential, timestamp attestation, author identity proof, provider receipt, or anti-forgery against an adversary who recomputes every unsigned hash.

## Existing code, not a parallel design system

- New route `/holon` is mounted via the existing `HolonRoute` in `hub/src/App.tsx`, with its native nav/metadata in `HolonGlass.tsx`.
- `HolonMaximusStudio.tsx` is the UI and graph driven by the actual journal. The graph displays only at most 12 recent events and their visible intra-window relations, not simulated thought or invented telemetry.
- `SovereignMatter` from the existing AEGIS WebGL/SDF renderer is reused as **static concept art** with boundaryCount=0. It does not represent the user's idea network, computational intelligence or a proof.
- Existing Holon Glass palette/tokens govern the new scoped CSS; no imported stock UI kit, Apple fonts, WebGL framework, model SDK, network service or new backend.
- `holonTrace.ts` is the portable, deterministic event contract, using the standard Web Crypto API only.

## Privacy and honest capability boundary

The first slice stores the trace only in the current browser session memory. Reloading or leaving the route loses unsaved work. **Export** to keep it; **import** only files you trust. The app sends no ideas or files over a network, contains no AI inference and makes no provider payments. UI does not claim model responses were generated or authenticated. Browser JSON import is bounded at 256 KB. Future persistence must have explicit user opt-in and a deletion/export policy.

## Reproducible acceptance path

At exact candidate head:
```sh
cd hub
npm run test:experience
npm run build
```
The included `holon-maximus.test.mjs` covers honest roles, human-only select/weave/finalize, graph lineage, invalid imported hash/fields, missing parents and local-only execution boundaries. Additional independent acceptance is required: mount actual React route in Chromium and Safari, test at 320 px / 200% zoom and 390/768/1440, keyboard/VoiceOver/TalkBack, 3D unavailable fallback, reduced motion, file import/export, tamper detection and unrecoverable session warning. Compare at least five real tasks and evaluate typography/interaction comfort with humans.

**Important:** Node tests were committed and registered. Unless and until exact-head logs show successful execution, record test execution as **UNKNOWN**, not PASS. Structural readback is not TypeScript, WebGL, WCAG or user-study certification.

## Later evolution (not yet delivered)

1. Opt-in encrypted at-rest persistence + independently verifiable checkpoint signatures or trusted timestamp receipts, under explicit consent.
2. Human-curated agent/model prompts, costs, quotas, review and a safe execution authority gate. A plugin connection is not consent for autonomous publishing.
3. Real interactive 3D holonic topology from signed/authorized lineage events, with WebGL fallback and measured device budgets.
4. Non-generative creative collaboration, peer fork/merge with explicit attribution, accessibility and originality evaluation.
5. Only after independent product/UX review: publication, pricing experiments and production admission.

**Release gate:** protected main, signed commits, checks and explicit operator approval. Keep current PR draft until authentic testing and design review are complete.

## Holonski konac — record-bound creative thread

The V1 Studio now mounts `HolonicThread` instead of its previous 4-column event grid. The thread is a **3D mathematical projection rendered through SVG**, not a hardware WebGL graph and not a simulation of a human mind. Existing separate `SovereignMatter` WebGL/SDF art remains explicitly illustrative and is not passed off as the underlying source graph.

- Pure model `hub/src/lib/holonThread.ts` derives every visible node from a journal event, and every filament from an explicit `parents[]` relationship. No orphan parent gets an invented on-screen edge. Neither PBR material appearance nor graphical proximity is a claim about causation, proof, model reasoning or authorship.
- History window: at most 24 events at a time, navigable **Earlier / Later / Latest** in deterministic overlapping 12-event steps. The screen reports how many events and links lie outside the current window. The underlying 128-event journal remains unmodified.
- Interactive node selection highlights recorded relationships and displays full text, recorded time, source event numbers, claimed actor/origin and event digest. Claimed `model`/`agent` origin is clearly labelled **pasted, unverified**; no model execution or provider authentication.
- Desktop: user-directed perspective adjustments, no timers or auto-play; bounded projection and native accessible event buttons. On mobile widths <=640px, the same event window appears as an accessible textual event list instead of an unusable scaled 3D stage. At all viewport sizes the inspection details remain available.
- Test: `hub/tests/holon-thread.test.mjs` now has **11 independently locally executed checks** covering empty truth, exact edges, role integrity, viewpoint identity invariants, 128-event bounds, omitted ancestry, deterministic projection, historical replay window, invalid input. It is registered in existing `test:experience`.
- Synthetic QA preview checked in Chromium at 320, 390, 768 and 1440 CSS px with **no horizontal overflow**. Browser preview is a static fixture built from the same pure projector/CSS, *not* a running React route or mobile Safari test. The screenshot and preview must not be passed off as real customer activity.

**Remaining admission:** verified React/Vite production build at exact head, full 24-node keyboard/VoiceOver focus audit, iOS Safari/Android touch, browser import→thread→export test, signed commit policy and provider-independent design review. No production change or publish authorization is inferred by adding source code to draft PR.
