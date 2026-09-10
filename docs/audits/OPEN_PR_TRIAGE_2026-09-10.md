# AEGIS Ω Open-PR Triage — 2026-09-10

Epistemic status: repository-bound triage record. This document is not merge authority, production admission, theorem authority, or evidence that an uninspected PR is redundant.

## Snapshot

- repository: `Aegis-Omega/AEGIS-OMEGA`
- protected main observed at triage start: `495bfd85d79abcb2b4f6898fe9c156488492426a`
- migration PR: `#428`
- migration head before this triage commit: `570b8c9bb2211df9698aea2b050cabe6ca54efd0`
- live open-PR search count: `131`
- #428 pre-triage hosted check surface: 45 check runs observed; substantive required/runtime lanes reviewed as successful, Agent Dispatch skipped by policy.

## Triage laws

1. `SUPERSEDED` requires purpose-level replacement plus path-level inspection; title similarity is insufficient.
2. Closing a PR does not delete its branch, commits, artifacts, workflow history, or evidentiary value.
3. Unique code, tests, proofs, schemas, receipts, migrations, or research artifacts must be preserved or explicitly classified before closure.
4. Historical GREEN evidence stays bound to its original SHA. Rebase/restack/head changes require new exact-head verification.
5. `.claude.json`, `skill-hashes.sha256`, cognitive-manifest writer/admission machinery, and Claude-specific authority hooks receive no new canonical authority from this triage.
6. Provider-neutral evidence, authority separation, fail-closed execution, proof, research, product, genomics, quantum, payment, repository-enforcement, and artifact-lineage work remain separate lanes unless mechanically shown to be superseded.

## Class A — SUPERSEDED_BY_428 / close candidate

These were inspected at changed-file level and their active purpose is removed or replaced by #428.

### #414 — `chore(manifest): stabilize main cognitive lineage after #401 and #402`

Changed files: `.claude.json` only.

Disposition: `SUPERSEDED_BY_428_HIGH_CONFIDENCE`.
Reason: #428 removes `.claude.json` from the active execution/admission boundary. The proposed lineage repair has no remaining target in the replacement architecture.

### #413 — `security(anchor): let the writer produce main's own anchor`

Changed files: `.claude.json`, `.github/workflows/cognitive-manifest-refresh.yml`, `scripts/test-cognitive-anchor-writer-boundary.py`.

Disposition: `SUPERSEDED_BY_428_HIGH_CONFIDENCE`.
Reason: all three changed surfaces belong to the decommissioned cognitive-anchor writer path.

### #422 — `fix(automaton2): bind Automaton-2 admission to exact checked-out commit and add regressions`

Changed files: `scripts/validate-automaton2.py`, `sovereign-omega-v2/python/tests/test_automaton2.py`.

Disposition: `SUPERSEDED_BY_428_HIGH_CONFIDENCE_WITH_CONCEPT_PRESERVED`.
Reason: #428 removes the old cognitive Automaton-2 validator and replaces the required `aegis / automaton-2` lane with a provider-neutral exact-head/worktree gate. The exact-head invariant remains required; the old implementation path does not.

## Class B — SALVAGE / REPURPOSE before closure

### #387 — cognitive anchor writer authority

Contains the old writer/recovery workflow, validator, anchor files, and tests. Do not merge as-is. Preserve any generic recovery-state/fail-closed invariants that are not specific to the deleted anchor representation.

Disposition: `SALVAGE_THEN_ARCHIVE_CANDIDATE`.

### #389 — recovery admission validator/design

Contains executable recovery-admission schemas, validator, tests and design documents. These are not equivalent to `.claude.json` itself.

Disposition: `REPURPOSE_TO_PROVIDER_NEUTRAL_STATE_RECOVERY`.

### #390 — trusted admission + Claude mutation guard

Contains substantial Claude-specific settings/guard code plus trusted-admission/anchor machinery. The provider-specific mutation guard is not canonical after #428, but the confused-deputy/direct-main-write security invariant remains valuable.

Disposition: `SALVAGE_PROVIDER_NEUTRAL_AUTHORITY_GUARD; DO_NOT_MERGE_AS_IS`.

### #391 — offline recovery admission validator

Contains recovery request/receipt schemas, CLI, replay registry and extensive tests. Preserve the general replay/admission machinery; detach it from the retired cognitive-manifest object model.

Disposition: `REPURPOSE_TO_GENERIC_STATE_RECOVERY`.

### #396 — atomic recovery replay store

Contains a Supabase migration, replay-store workflow/test, and recovery-executor tests. This is durable state-machine work, not merely an anchor refresh.

Disposition: `REVIEW_DB_SEMANTICS_AND_REPURPOSE`; no live migration implied.

### #308 — manifest branch invariance + bridge repair

Contains `.claude.json` and manifest-generator work that is obsolete under #428, but also `bridge.py` and live-state tests that may carry independent value.

Disposition: `SPLIT_SALVAGE`; retire manifest pieces, inspect/preserve bridge semantics separately.

### #290 — Claude artifact discovery

Claude-hook packaging is provider-specific, but the underlying law — narrow search misses must not become global non-existence claims — remains valid.

Disposition: `PORT_ABSENCE_CLAIM_GATE_TO_PROVIDER_NEUTRAL_REPOSITORY_COGNITION`.

### #310 — repository cognition

The repository-content census/fail-closed completeness idea remains valuable. Claude lifecycle hooks and cognitive-manifest convergence coupling must be removed before integration.

Disposition: `KEEP_ENGINE / DECOUPLE_PROVIDER_HOOKS / REBASE`.

## Class C — KEEP / REBASE / independent technical lane

The following visible current PRs carry independent implementation, proof, research, product, security, or evidence work and are not superseded merely by #428:

- #428 provider-neutral governance migration / Skill Factory — canonical migration candidate, remain DRAFT until post-triage exact-head checks complete.
- #427 CoRN→O0 trig image identities — formal-math lane; retain strict non-RH boundary.
- #426 PayPal capture validation — payment/security lane.
- #425 authority-meet Coq proof — formal authority algebra; old cognitive-admission blocker wording must be reconciled after migration.
- #424 QuantumDNA claim/witness gate — genomics/quantum research lane; re-evaluate admission wording under new boundary.
- #423 immutable Integration Ledger — repository evidence lane; old cognitive blocker becomes historical after migration.
- #421 main Automaton enforcement policy — inspect against already-active live ruleset and #428 check topology before deciding redundancy.
- #420 AEGIS-Q signed calibration→numerical IFG — independent research-evidence lane.
- #419 Coq attestation build binding — formal supply/provenance lane.
- #417 ThreadManifold contract — semantic/authority-plane separation lane.
- #416 Coq diagnostic-scope correction — formal-attestation policy lane.
- #415 Spectral Time Inference — independent implementation/evidence lane; cognitive refresh narrative becomes historical.
- #412 QuantumManifold scheduler — independent runtime lane; must be restacked/reverified, not discarded because its old cognitive admission failed.
- #410 QuantumManifold Phase-1 kernel — stacked implementation evidence; reconcile with #412 rather than merge independently by default.
- #409 QP-PD V2 biological binding — empirical-pipeline implementation lane.
- #408 fail-closed claim-promotion tuples — governance/claims lane, independent of Claude anchor identity.
- #407 claim-promotion admission v1 — compare with #408 for verified supersession before any closure.
- #406 PR overlap guard — directly useful for future consolidation; live full-census execution remains distinct from unit tests.
- #405 own-principal capability binding — authority-confusion defense; preserve and reconcile with provider-neutral policy.
- #403 repository-knowledge main-push attestation — inspect current workflow topology; preserve exact-head observability invariant.
- #399 agent-dispatch fail-closed routing — runtime/effect lane.
- #397 GCP WIF preflight — external identity/recovery lane.
- #395 repository enforcement — preserve live-ruleset contract but remove any dead trusted-cognitive workflow assumptions.
- #392 Claude API model migration — provider-specific application integration; independently review whether each Claude call site should survive provider-neutral migration.
- #386 equality-saturation experiment — research-only lane.
- #377 polyglot metacognitive capability fabric — aligned with provider-neutral direction; rebase/reverify.
- #376 AEDR IAP Sigstore verifier — provenance/identity lane.
- #375 legacy quantum demonstrator quarantine — safety/governance lane.
- #374/#370/#427 formal CoRN/O0 stack — keep as a proof DAG; do not flatten into an RH claim.
- #373 CUDA-Q Self-Witness-0 — diagnostic quantum lane.
- #371 AVD benchmark — research/falsification lane.
- #367 AEDR DAG consolidator — diagnostic consolidation lane; no authority transfer.
- #365 provider-native cognitive fabric — strategically aligned; remove any surviving `.claude.json` coupling during rebase.
- #363/#362 QuantumTourbillon stack — experimental/diagnostic lanes.
- #361/#360 Coq prime-source/inventory stack — formal tooling/proof lane.
- #356 MHP-1 derivation composition — current main already contains related MHP lineage; requires exact semantic-delta comparison before disposition.
- #350 H_meta contract — audit/governance record; old cognitive-anchor binding should be treated as historical.
- #342 universal intelligence/RH spine — very large integration branch; do not merge wholesale; selective preservation only.
- #341 RH finite prime-phase reconstruction — independent negative/diagnostic research evidence.
- #339 cross-runtime exact-source receipt — evidence/provenance lane.
- #338 rational quotient error algebra — formal sub-obligation.
- #335 QForm proof-carrying bridge — research/formal-evidence lane.
- #334 resident intelligence runtime — large evolved runtime lane; selective comparison required.
- #333 Vercel deployment throttling repair — product/ops lane; cognitive generated delta must not control disposition.
- #332/#274 Khatt/Abjad stack — language/research lane.
- #331 RH conditioning / observable contraction — research lane.
- #330/#324 cross-domain prospective research stack — research-only.
- #329 shard-closure negative result — preserve as falsification evidence.
- #322 finite Archimedean-tail Gram positivity — formal sub-obligation.
- #320 zero-discretion type gates — research-method gate.
- #319 system rebuild, #318 platform reconciliation, #312/#314/#315/#316/#317 component repairs — likely consolidation family; determine dominance/unique-file preservation before closure.
- #313 UCI restack, #311 authorization/effect integration, #309 effect-chain reconciliation, #297 execution principal — authority/effect ancestry family; consolidate only by exact behavior/file dominance.
- #307/#303 Weil globalization/convergence bridge — formal proof line, `RH=NOT_PROVEN` unless all concrete premises and criterion binding are closed.
- #301/#298 ProofTrace-security evidence stack — security/evidence containment lane.
- #296 Epistemic Admission Kernel — provider-neutral epistemic boundary candidate.
- #295 semantic lineage/Drive triage — forensic/audit lane; separate from runtime authority.
- #294 model artifact/provider registry — aligned provider-neutral model fabric.
- #293 Holon LLM inference — experimental inference lane.
- #292/#289/#286 proof-producing refinement chain — formal/correspondence lane.
- #291 Company Brain — organizational orchestration candidate.
- #285/#284 metacognitive executive + ProofTrace — core candidate architecture; compare against later evolved runtimes before integration.
- #283 boundary falsifiers — preserve as regression/falsification corpus where still applicable.
- #282 Daybreak Blue security hardening — security ancestor; likely partially absorbed by later runtime work, requires dominance check.
- #281 cross-plane transfer experiment — research/experiment lane.
- #280/#275 UCI evaluation/integration family — old integration spine; compare with #342/newer runtime before closure.
- #273/#272/#270/#268 effect-verification stack — historical causal chain; later #309/#311/#334 may supersede implementation, but exact unique-test/proof preservation must be established first.
- #267 Memory Sentinel hackathon subtree — isolated product/research lane.
- #265 provider containment — security/governance concept remains aligned; current author is deleted/ghost, so preservation should be via explicit reviewed transplant rather than blind merge.
- #264 provider mesh — aligned provider-neutral orchestration lineage.
- #263 public expansion — product/docs lane.
- #262 operator meta-model — metacognition lane; review for privacy/provider-neutrality before use.
- #261 provenance forensics — evidence/audit lane.
- #260 reproducible-build evidence — supply/provenance lane.
- #259 Jetson execution contract — hardware lane.
- #258 LifeQuest admission — product/runtime lane.
- #256 claims-ledger always-report — CI reliability lane; compare current workflow before integration.

## Class D — repository-wide remainder

The live search contains 131 open PRs. PRs not explicitly enumerated above are assigned the conservative default:

`HOLD_REVIEW_REQUIRED / NO_MERGE / NO_CLOSE / AUTHORITY_EFFECT_NONE`

This is a real triage state, not a redundancy claim. They must be processed through exact changed-file census and ancestry/dominance comparison before promotion or closure.

## Immediate execution order

1. Close #414, #413 and #422 as superseded by #428, preserving their branches/history.
2. Keep #428 draft and re-run exact-head CI after this triage-record commit.
3. Port the useful invariants from #290/#310/#390/#391 into provider-neutral surfaces rather than merging their provider-specific control planes.
4. Reconcile repository enforcement (#395/#421/#405/#406) with #428's new required-check topology.
5. Reconcile the main production/runtime family (#334/#399/#365/#377/#294/#264) by exact file/behavior dominance.
6. Preserve the formal-math DAG (#303/#307/#322/#335/#338/#360/#361/#370/#374/#416/#419/#427) as evidence-scoped modules; never infer RH closure from stacked GREEN checks.
7. Triage research/quantum/genomics/product lanes independently so governance cleanup cannot silently delete scientific or commercial work.

## Current bounded disposition

```text
open_pr_census = 131
migration_pr = 428
migration_pre_triage_head = 570b8c9bb2211df9698aea2b050cabe6ca54efd0
main_at_triage = 495bfd85d79abcb2b4f6898fe9c156488492426a
high_confidence_superseded = [414, 413, 422]
salvage_before_archive = [387, 389, 390, 391, 396, 308, 290, 310]
merge_authority = NONE
production_authority = NONE
claim_promotion = NONE
rh_status = NOT_PROVEN
```
