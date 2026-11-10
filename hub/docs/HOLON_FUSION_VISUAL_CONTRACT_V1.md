# AEGIS Ω — Sovereign Holon Glass Fusion / Visual Quality Contract v1

> Status: **DESIGN CANDIDATE / NOT ADMITTED** · 2026-10-11  
> Implementation owner: existing [Holon Glass PR #745](https://github.com/Aegis-Omega/AEGIS-OMEGA/pull/745).  
> Work contract: [#768](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/768) · Asset curation [#769](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/769) · Graphics fusion [#770](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/770) · Mobile workbench [#760](https://github.com/Aegis-Omega/AEGIS-OMEGA/issues/760).

## Nonduplication invariant

Use the existing `hub/src/holon-glass.css`, `hub/src/HolonGlass.tsx`, `hub/HOLON_GLASS_DESIGN.md` and `hub/public/design-system/colors_and_type.css` as the source of truth. This document **does not** create an independent palette, React framework, navigation shell or rendering engine. Introduce new tokens only when the existing canonical names and semantic meanings cannot express the required contrast/material/style.

## Visual direction

**Holon**: a nested bounded topology with legible parent/child/evidence edges; never a meaningless repeating particle field.

**Glass**: purposeful optically layered surfaces with sparse Fresnel hairlines, local blue-tinted refraction, gentle gradients, restrained glow and accessible solid reading planes. Avoid glass-on-glass contrast loss and blur behind source identifiers.

**Cinematic**: a small number of hero compositions using the existing AEGIS visual archive and domain scenes; reserve spectacle for public communication, not dense operator task flows.

**Operational**: crisp typography, scanable navigation, dense-but-calm panels, exact action naming, deterministic focus handling, explicit UNKNOWN/STALE/REPORTED/VERIFIED states. All status claims are data-bound.

**Scientific**: graphs, plots and source receipts use actual domain data, sources and experiment versions. Concept renders must be marked as art. A graphic is not a scientific finding.

## Prior art and concrete inventory

- Library: `/AEGIS Research Archive/17_Media_Visuals` contains Holon Control Plane, Frontier Standards, cinematic visual references and DNA Spectrum Lab. The previous inventory claims 181 media images; issue #769 must recount and compare hashes.
- Library: `/AEGIS/Artifact Registry/2026-10-11/01_Product_UI` contains mobile workbench previews.
- Four operator-supplied reference screenshots of orbit/globe and mobile/public interfaces are references, not automatically publishable production images.
- Canonical visual tokens and accessible interaction repairs already exist in PR #745, including reduced-motion and navigation tests. **Extend them; do not reset their semantics.**
- Concepts to evaluate, not claims of uniqueness: Evidence Filament, Sovereign Matter, Living Type, Proof Observatory, Causal Motion, Visual Genome.

## Required agent delivery record for ANY AEGIS visual change

1. **Repo/source inspection:** exact HEAD SHA; reused files/versions; existing issue and PR overlap; Library selection and content digests; supported license/rights, otherwise UNKNOWN.
2. **Proposed change:** smallest source diff, before/after rationale, tokens/components retained, reference image classification (concept art vs real photograph vs measurement).
3. **UX and semantics:** what the user actually accomplishes; no fake progress/status/provider state; evidence-linked drilldowns; roles, actions and expected failure states.
4. **Adaptive access:** 320 at 200% zoom, 390/768/1440 widths; keyboard tab/escape/focus restore; touch; screen-reader; reduced-motion (absolute override); high contrast; slow/offline/unavailable API.
5. **Evidence:** screenshot/diff artifacts at exact candidate, authentic build/tests run, Web Vitals where observable (LCP p75 <=2.5s, INP p75 <=200ms, CLS p75 <=0.1), outcome-based matched user task baseline, independent review. Target values are NOT reported PASS.
6. **Gate:** label each result PASS/FAIL/OPEN/UNKNOWN with evidence and source version; no world-best claim, production deployment, protected-main merge, billing, authority expansion or security regression without separate signed/reviewed admission.
7. **Machine-readable companion:** propose JSON receipt with `repo`, `head_sha`, `asset_digests`, `reused_components`, `screenshots`, `test_commands`, `results`, `unknowns`, `admission`.

## Fusion experiments — avoid unmeasured complexity

- Begin with existing CSS/SVG/React, not a new rendering engine. Test one holon morphology or evidence lineage visual on a noncritical route.
- If SDF/TSL/WebGPU are introduced, provide feature support matrix, Safari fallback, CPU/GPU telemetry, memory/time budget, reduced-motion behavior and a static accessible rendering.
- If Rive/state machines are introduced, events must be tied to authenticated domain state; decorative animation starts OFF and can be paused.
- Dark glass must include fallback backgrounds for no backdrop-filter and separate token-backed contrast surfaces for copy and evidence.
- Keep semantic source/graph model separate from any shader geometry so proof and provenance remain inspectable without GPU.

## Current disposition

This contract is implementation guidance and a candidate documentation change. It is **not** proof of a full Vite build, WCAG certification, rights clearance, physical-device acceptance, deployment or exact-head admission. Existing #745 receipts tied to older commits must be rebound after any new commit.
