# AEGIS Ω — HOLON GLASS / Enterprise Visual System v1

## Target
One premium sovereign research experience across the nine existing hub routes. Design source: `/AEGIS Research Archive/17_Media_Visuals` (181 inventoried media images), including `AEGIS Ω Holon Control Plane.png`, `Aegis Omega: Frontierni standardi.png`, `Aegis Omega Labs: Suvereni istraživački interfejs.png`, `Aegis Omega Labs: Frontier Standards.png`, `aegis-home.png`, and `AEGIS laboratorija za DNK spektar.png`; site audit `https://aegisomega.com` on 2026-10-10.

## Design principles
1. True *holon* topology: nested bounded computation, not generic particle wallpaper.
2. Visual evidence: source -> compute -> challenge -> admit; visible boundaries for unknowns.
3. Glass as a material system: dark-blue refraction, hairline Fresnel strokes, controlled sapphire and ultraviolet radiance, neutral reading surfaces, mint for evidence status, gold reserved for constitutional authority.
4. Large editorial typography for narrative; mono typography only for source receipts and experiment identifiers.
5. Distinct workspaces: marketing overview, operator runtime, developer docs, research tools and admission/compliance remain separate functional routes with one identity.
6. No fabricated live provider state, invented proof, test claims, paid checkout side effects, or mislabelled benchmark data.
7. Responsive, reduced motion, keyboard focus, HTML semantic landmarks and source-visible CSS fallback.

## Route preservation
- `/` -> new `HolonHomepage`; the previous home source remains in the repo, recoverable by a one-line App.tsx revert. Its SHA-256 demo remains conceptually available as an explicitly labelled small in-browser sample on the new home and the existing constitutional `/runtime` route remains live.
- `/platform`, `/console`, `/docs`, `/pricing`, `/claim-sponsor`, `/runtime`, `/compliance`, `/tools` -> original TSX operational components wrapped inside `HolonRoute` without changing their APIs, payment callbacks, business rules or provenance.
- `https://aegis-quantum-integrity-mobile.tarikskalic33.workers.dev/` -> separate live edge PSD math research laboratory; not a physical bath backend.

## Security / production boundary
Design-only work on isolated branch. No authority elevation, no secrets added, no backend changes, no protected-main updates and no pricing/billing commitments. Preserve production deploy gate, required checks, and review before merge. Main site should not deploy until browser smoke testing proves payment flows still accessible and API/docs navigation intact.

## Expected checks
- Syntax/transpile of App.tsx and HolonGlass.tsx.
- Hub TypeScript project build and Vite emit on isolated exact head.
- Browser navigation for 9 paths and mobile 390px viewport; no duplicated route nav or horizontal overflow.
- Verify SHA-256 local tamper sample changes from intact to invalid; it does not claim to be a production chain receipt.
- Verify /pricing and /claim-sponsor forms still render and retain callbacks. Never actually initiate payment.
- Contrast and reduced-motion, keyboard tab order, viewport widths 390/768/1440.

## Known limits
The homepage style is freshly authored based on user Library references, not a literal reproduction or a claim of ownership of existing artwork. Assets are procedural SVG and CSS, so no external image loading or library private-file leakage is required. Full-site compilation / preview is required before production promotion. No claim to having completed all route QA until those checks actually run.

## 2026-10-11 second-pass anti-slop repair

- **Credibility:** /platform no longer states blanket 100% replay or a 10-second latency guarantee; unknown exact-head test status is explicit.
- **Legal claims:** /compliance control mapping is not an EU AI Act certification; formerly green COMPLIANT badges are now review-required CONTROL MAPPED labels.
- **Information architecture:** scientific cards link to relevant source repositories, not unrelated pricing/creator tools. Homepage has a public evidence register and unrecognized routes get a distinct 404 view.
- **Accessibility:** explicit skip link, keyboard-operable tab selection, Escape-close on mobile navigation, aria-controls and programmatically named result status.
- **Actual utility:** the simulated SHA-256 chain was removed from the main research home; the new artifact verifier computes SHA-256 of **local browser files** (up to 32 MiB) and compares with a supplied reference. No transfer or signatures. A match asserts byte identity relative to that reference, not scientific validity or admission.
- **Concurrency:** revision guard prevents an old async hash from being shown as verification of a newly selected file or expected digest.

### Reproducible test

From `hub/` under Node.js 22+:

```bash
npm run test:integrity
npm run build
```

Independent isolated TypeScript declaration check and 7 pure verifier tests passed locally. **Do not infer an exact-head full hub build from this.**

### Outstanding (not a production admission)

- The latest GitHub head is subject to Vercel's build-rate limit; only an earlier head had a completed TypeScript/Vite deployment.
- SSO-protected Vercel previews prevent unauthenticated route-by-route browser QA. The public Cloudflare page is a **homepage-only static design preview** with a separately implemented local verifier, not a release preview of all React routes.
- Browser upload interactions on the public preview are not certified; a remote QA run timed out.
- The dependency audit previously reported 13 npm vulnerabilities (1 low, 2 moderate, 10 high) which still require dependency-level triage.
- Pricing, sponsor provisioning, runtime, console, documentation navigation and all responsive breakpoints require authorized regression testing before merge/deploy.


## 2026-10-11 interaction quality repair: navigation focus and motion choice

This is a **bounded frontend repair on the existing #745 branch**, not a redesign or release admission. Exact candidate source must be rebound to the latest branch SHA before reporting results.

- Existing decorative orbital animations last 19, 24, 52 and 72 seconds and previously had no user-operated pause control. `HolonHome` now defaults to a paused ambient visual and adds a visible, keyboard-operated Play/Pause button outside the ornament's `aria-hidden` subtree. The same control covers the hero orbit and focus-panel holons without duplicating artwork. A device-level `prefers-reduced-motion: reduce` request always disables animations and hides a control that could not restart them.
- On mobile, opening navigation now focuses the first link. Escape closes it and restores focus to the disclosure button. Existing `aria-controls` and `aria-expanded` remain intact. The menu is a disclosure, not an incorrectly modeled modal dialog or focus trap.
- CSS provides a minimum 44px motion control height and explicit `:focus-visible`. No new audio, autoplay, tracking, remote assets, payment callbacks, new design tokens or authority permissions.
- The read-only source-contract tests under `hub/tests/holon-interaction.test.mjs` cover 10 source-level invariants and 6 negative mutation cases. Run `npm run test:experience` from `hub/`; negative source tests do **not** substitute for assistive-technology or browser behavior.

**Fresh source check:** connector readback confirmed the JSX/CSS/test blobs exist at a single exact commit and 10 independently inspected source predicates match. This is **SOURCE_CONTRACT_ONLY**. The Node test command and full TypeScript/Vite build are not proven by that inspection; native GitHub Actions and real browser journey must be independently replayed. A user experience cannot be declared best-in-world, WCAG-conformant or released based on this change.

**Next acceptance**: verify 390px mobile navigation by keyboard and touch, focus return after Escape, reduced-motion on physical/mobile browsers, Play/Pause with assistive tech, actual contrasts and performance, plus unchanged /pricing and /claim-sponsor callbacks. Hold protected main until signed commit, independent review and full release gates.

## 2026-10-11 additional mobile disclosure behavior

The open mobile disclosure also dismisses when a user taps/clicks outside it or moves keyboard focus out. Focus on the outside destination is preserved. Listeners for `pointerdown` and `focusin` exist **only while the disclosure is open** and are removed on close or unmount. The triggering menu button and nested menu links are excluded from outside-detection; detached refs do not invent a close decision. `Escape` retains its explicit focus restoration.

**Smallest reused implementation:** `src/lib/disclosure.ts` exports only `shouldDismissDisclosure`, a typed pure containment function; `HolonGlass.tsx` uses it instead of a second navigation system. `tests/disclosure.test.mjs` covers six runtime behaviors (inside/outside, toggle, missing refs). `tests/holon-interaction.test.mjs` includes five additional integration/negative source checks. Combined command: `cd hub && npm run test:experience` (21 source-level and 6 pure function cases).

The pure helper has been tested **locally** with Node 22 and the equivalent typed source passed local strict TypeScript compilation. Independent GitHub source-level V8 checks verified 21/21 predicates bound to the exact associated Git blobs; these are not equivalent to a deployed React keyboard/browser test. No autoplay media, sound, consent tracking, payment behavior, security boundary or protected-main behavior changed. Production release remains blocked pending actual browser/device user flow QA, complete build and signed admission.
