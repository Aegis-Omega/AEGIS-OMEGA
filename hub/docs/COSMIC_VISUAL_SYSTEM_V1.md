# AEGIS Ω · Cosmic Command · Integrated Visual System v1

> **Implementation candidate · NOT_ADMITTED**. Applies to the existing protected-main PR #745 branch, not production. Authoritative code is the latest exact branch head; commit and blob SHA must be rebound at release.

## Art direction

Built against the operator-supplied command-center and handoff references dated 2026-10-11. Do not publish either reference screenshot as an app screenshot. The output is a *single authored system*: midnight-blue sovereign operations, luminous cobalt/cyan/violet wayfinding, precisely bounded transparent panels, an authored planet/orbit SVG with real route links, and scientific contents rendered on solid reading planes. Avoid repeating spheres, random particle effects, stock illustrations, invented data and status-green decoration.

The user wants the full AEGIS software visual identity, not just a proof widget or a mockup. The implementation binds home, research, console, runtime, governance, docs, pricing, tools and sponsor claim to one existing Holon Glass shell. Its architecture stays repository-native. The visual expression differs between cinematic discovery and precise operational workflows, but the navigation, palette, typography, focus and controls are shared.

## Canonical implementation

| Concern | File |
|---|---|
| App routing | `hub/src/App.tsx` |
| Shared navigation, left rail, route chapter locator | `hub/src/HolonGlass.tsx` |
| Base global visual contract | `hub/src/aegis-visual-universe.css` |
| Cosmic command hero and destination filtering | `hub/src/components/CosmicCommand.tsx` |
| Responsive cosmic visuals and cross-route material overrides | `hub/src/components/cosmic-command.css` |
| Accessible route-only Cmd/Ctrl+K search | `hub/src/components/CommandJump.tsx` |
| Research domain data and interactions | `hub/src/components/ResearchWorkbench.tsx`, `hub/src/components/SovereignField.tsx` |
| Existing WebGL2 material with graceful fallback | `hub/src/components/SovereignMatter.tsx` |
| Semantic operator controls | `hub/src/components/console/ConsolePage.tsx` |
| Legacy NOUS shared primitives and tokens | `hub/src/components/console/NousUI.tsx`, `consoleTokens.ts` |
| Automated source guards | `hub/tests/visual-universe.test.mjs`, `hub/tests/cosmic-command.test.mjs` |

No Three.js dependency is added solely to manufacture a design claim. The production release must prove installed dependency provenance, performance and build before adding a heavier renderer. Current SVG geometry is a bounded architectural visual; existing WebGL2 is retained in ResearchOS.

## Interaction and visual priorities

1. **One authored signature.** Omega sign, a glowing procedural planetary context and real orbital route controls occupy the cinematic entry only; avoid repeating the same motif behind dense docs, pricing, verification or console forms.
2. **Actual affordances.** Left rail navigates real routes. Top `⌘/Ctrl+K` searches the known route registry and never pretends to index code or personal data. Atlas shows five destinations; Evidence narrows to runtime, governance and documentation. All links are published routes.
3. **No fake state.** The illustrations are labeled concept art. No agent counts, percentages, activity, uptime or scientific result appears without a source. Unknown and not admitted remain explicitly available.
4. **Optical control.** Luminous glow belongs to the hero, selected navigation, a focused control or an evidence boundary. Operators work on darker opaque reading surfaces.
5. **Typography and hierarchy.** Local Inter and JetBrains Mono remain canonical. Oversized typography is reserved for first-level sections. Workbench labels receive a floor instead of 6–9px decorative microtype.
6. **Semantic colors.** A blue action never implies successful execution. Existing risk, unknown, verified, admitted and error semantics retain their source behavior; no state is restyled to false positive.
7. **Responsive and input model.** Left rail at ≥1200px, shared nav below, real 44px mobile command controls at ≤600px, and a 320px fallback. Orbit nodes stay ordinary links; GPU/animation are not required for use.
8. **Inclusion and performance.** Respect reduced-motion and increased-contrast preferences. The hero SVG is visual and its semantic links are normal HTML. Motion is restrained and opt-in where applicable; avoid blocking fonts, invented live polling and unnecessary large dependencies.
9. **No authority amplification.** The design layer does not modify payments, credentials, approval state, authorization, CI rules, signatures or protected main. Never conflate source visual completion with admission.

## Verification status and release gate

Current code readback and source assertions verify links, paths, CSS brace balance, source annotation, keyboard interactions, mobile CSS, reduced-motion, no invented metrics and test registration. These are **not** end-to-end UI proofs. The author-authored gradients must pass text contrast at both endpoints (white text on #126bd1 exceeds AA 4.5:1). Other component state-dependent contrasts still need full automated/audited review.

Before release: execute `npm run build`, `npm run test:experience` and `npm run lint` in an installable exact-head environment; capture **real React route** screenshots on 320, 390, 768, 1200 and 1600 widths; verify keyboard, screen-reader labels, focus return, reduced-motion, contrast, clipping, Core Web Vitals and the page navigation flows. Review critical paid/identity workflows without using live transactions. Conduct a blinded comparison against reference interfaces rather than claiming 'best' by assertion.

Vercel failures attributed to quota/build-rate limits must be distinguished from actual source compilation failures. No merge or deploy until each independent admission gate is reported with exact-head evidence.
