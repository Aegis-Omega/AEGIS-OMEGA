# AEGIS Ω — Total Experience Evidence Contract v1 (advisory)

**Scope:** every AEGIS deliverable, not only a code artifact. This is an operator quality objective, not a declaration of worldwide superiority. **State:** draft / candidate / no authority effect. Parent issues: #734, #757, #758, #760. Reuse the already existing Holon Glass design and evaluation in PR #745; no new dispatcher, design system or permission grant.

## What “everything” requires

Treat each deliverable as a complete interaction over time: what the user sees, hears, understands, believes, attempts, receives, remembers and can trust. Evaluate all of these 13 **mandatory-disposition** dimensions, plus namespaced extensions (`ext.*`) where task-specific:

| Dimension | Observational evidence and failure case |
| --- | --- |
| visual | Blinded design preference, hierarchy and legibility tests; do not mistake glow/illustrations for product quality |
| typography | Readability/comprehension at device widths and language scripts; poor contrast or truncation |
| motion | Reduced-motion, pause/stop, intentionality, performance; vestibular discomfort or purposeless loops |
| sonic | **Silence is a legitimate design choice.** Opt-in, control/mute, intelligibility, mixing and rights if sound exists; unsolicited playback |
| narrative | User-problem → credible mechanism → bounded evidence → next action; misleading story or unsupported grandeur |
| product_utility | Actual task success and first value, not feature count |
| usability | End-to-end first/repeat use, errors and recovery, navigation and mobile ergonomics |
| accessibility | Keyboard/assistive technology, content alternatives and WCAG-relevant checks |
| performance | Real device and network budgets, loading, animation jank, energy cost |
| reliability | Failures, offline/timeout states, recovery and predictability |
| privacy_safety | No hidden collection, unwanted sound, excessive permissions or false authority cues |
| originality_rights | Traceable source media/licensing, meaningful distinctiveness, no unattributed copying |
| business_value | Customer outcome, willingness to use, retention/qualified conversion with realistic cost |

The list is not exhaustive: additional fields for haptics, translation/localisation, hardware, learning, environment, ethics, physical ergonomics or other media use `ext.<name>`. Do not assume every task needs every feature; mark **MEASURED, UNMEASURED, NOT_APPLICABLE**, with an explicit rationale. Avoid invented ratings or extrapolating one small sample to all users.

## Source-first discovery

For the Holon Glass pilot inspect exact-current branch files, not historical labels: `hub/HOLON_GLASS_DESIGN.md`, `hub/src/holon-glass.css`, `hub/src/HolonGlass.tsx`, `hub/public/design-system/colors_and_type.css`; inspect authorized image/media/narrative references (including connected sources only with appropriate access). The Holon CSS currently declares reduced-motion handling, but that one style rule is **not proof** of WCAG conformance or perceptual quality. The current component does not establish a tested sound system: do not manufacture one. Preserve existing user-supplied identity assets and rights.

Narrative and sonic/voice work must preserve source/transform lineage and uncertainty. Captures, transcription, translation, interpretation, claims and UX copy are separate evidence classes. Do not infer genuine voice emotion, user intent, or scientific validity from a transcript. When a connected private semantic-lineage reference exists, verify visibility/licensing before reuse; never paste its contents into public GitHub by default.

## Standards are scoped, not a recipe for style

- [ISO 9241-210:2019](https://www.iso.org/standard/77520.html): human-centred design process for interactive systems; reviewed/confirmed in 2025.
- [WCAG 2.2](https://www.w3.org/TR/WCAG22/): relevant accessibility criteria, including 2.2.2 pause/stop/hide and 2.3.3 interaction-triggered animation (AAA); `prefers-reduced-motion` can be a technique, not a full conformance declaration.
- [W3C Making Audio and Video Media Accessible](https://www.w3.org/WAI/media/av/): audio/video captions, descriptive transcripts, descriptions and accessible players where applicable.

Standard issuer, edition, applicability and observation must be recorded; no universal single “best style” follows from these documents.

## Runnable bounded structure check

```bash
python3 -m unittest -q scripts/test_experience_eval.py
python3 scripts/experience_eval.py manifest.json
# Or: cat manifest.json | python3 scripts/experience_eval.py -
```

The validator requires exact source HEAD, different baseline and candidate SHA-256s, all 13 dimension dispositions, rationales and standard/source references. For reported measurements it requires unit, directional metric, matched baseline, candidate, tolerance, and evidence SHA-256, rejecting nonfinite numbers, wrong types and extra untrusted keys. The comparator reports each axis's improvement/regression; the output is **STRUCTURAL_VALIDATION_ONLY**, with independent measurements **NOT AUTHENTICATED**, standards **NOT VERIFIED**, world-best **NOT ESTABLISHED** and authority **NONE**. A hash proves only content identity *relative to a known digest*. It does not prove truth, proper sampling, authenticity of reviewer, or business impact.

No changes to original work contract, protected branch policies, deployment, billing, credentials or customer data. This tool is not a release gate or scientific peer review. Evidence promotion requires independent check of actual study materials, build, user observations and signed/protected admission.

## Pilot acceptance for existing product

Perform three matched end-to-end scenarios on baseline and candidate: (1) new user understands proposition and completes first useful action; (2) returning researcher starts a task and recovers from a failure; (3) operator traces an evidence claim to a valid source and decides what is permitted. Record 390/768/1440 px, motion preference, keyboard/screen-reader, muted/no-audio baseline, low bandwidth, real error messages and privacy. Collect blinded preference and comprehension feedback, task completion, trust/claim fidelity, performance and adverse findings. For actual sound, independently test user consent, accessible equivalence, loudness, decoding/latency and rights. Do not treat synthetic test vectors or model opinions as user data.

**Promotion requires:** verified actual measurement provenance; independent review; no material safety, accessibility, accuracy or rights regression; controlled external comparison before any 'world-leading' claim.
