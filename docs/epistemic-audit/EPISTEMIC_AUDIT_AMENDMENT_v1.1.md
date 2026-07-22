# AEGIS Epistemic Audit Amendment

Version: 1.1
State: Architecture frozen
Next admissible event: Empirical preregistration
Authority class: Methodological constitution

Adoption record (this repository):
- adopted_at: 2026-07-22
- adopted_by: operator transfer into session on branch `claude/fable-mythos-behavior-analysis-yjm4yr`
- authorship: v1.1 additions authored external to the adopting session; adopted verbatim
- operator rule: material sent by the operator is adopted work-product regardless of authoring agent; origin is recorded in this field and changes nothing else

## Frozen precision note — Blackwell–Dubins directionality

Blackwell–Dubins merging is directional. If P ≪ Q, then Q's predictive
conditionals merge to P's, P-almost surely. Mutual absolute continuity gives
the symmetric two-agent form. A dogmatic zero can destroy the
absolute-continuity condition and therefore the theorem's guarantee, but a
zero alone does not prove permanent divergence.

Aumann remains the correct contrast case: a common prior plus common knowledge
of posterior probabilities forces equality, but it does not adjudicate agents
whose prior structures differ.

Open executable-field declaration (admissible under §5 — changes the metric):
the pilot must declare whether Q_E(t) is computed as total variation over the
entire predictive future (strong merging, the Blackwell–Dubins form above) or
over finite-horizon next-k predictions (weak merging, Kalai–Lehrer), since
only the finite-horizon quantity is empirically measurable.

---

## 1. Observable-indexed faithfulness

Let X_i and X_j be representational systems and let

    τ_ij : X_i → X_j

be a translation, interpretation, transmission, or formalization map.

Faithfulness is not a scalar property of τ_ij. It is indexed by a declared
observable family.

For each observable a ∈ 𝒜, declare:

    O_i^a : X_i → Y_a,    O_j^a : X_j → Y_a,

where Y_a has a declared metric or discrepancy function d_a.

The observable-specific translation error is

    ε_a(τ_ij) = sup_{x ∈ D_a} d_a( O_j^a(τ_ij(x)), O_i^a(x) ),

where D_a ⊆ X_i is the preregistered evaluation domain.

The translation certificate is therefore the vector

    ε(τ_ij) = ( ε_a(τ_ij) )_{a ∈ 𝒜},

not a single global designation.

### Arrow–observable classes

For every pair (τ_ij, a):

- Exact: ε_a = 0.
- Lax-certified: 0 < ε_a ≤ θ_a, where θ_a is declared before evaluation.
- Lossy: ε_a > θ_a.
- Uncertified: the observable correspondence, metric, domain, or bound is missing.
- Inapplicable: the target system makes no claim to preserve that observable.

An arrow may therefore be exact for one observable and non-certifying for another.

### Required dossier fields

Every translation pathway must record:

    source system
    target system
    translation map
    observable identifier
    source observable
    target observable
    evaluation domain
    discrepancy function
    acceptance threshold
    measured error
    certification state
    known invariants
    known losses
    claim scope

The unit of certification is:

    (arrow, observable),

not the arrow alone.

This accommodates cases in which a translation is adequate for juridical,
propositional, pedagogical, or conversion-related use while being formally
invalid for recitational, liturgical, phonological, or performative use.
These are not contradictory global judgments. They are different observable
certificates.

---

## 2. Epistemic contraction and non-merging

Let P and Q be probability measures over an evidence-generating sequence with
information filtration

    𝓕_1 ⊆ 𝓕_2 ⊆ ⋯ .

Let P_t and Q_t denote their conditional predictive distributions after
observing 𝓕_t.

The contraction quantity is

    Q_E(t) = ‖ P_t − Q_t ‖_TV,

where total variation is declared as the comparison metric.

### Directional merging condition

If

    P ≪ Q,

then the Blackwell–Dubins result gives, under its regularity conditions,

    ‖ P_t − Q_t ‖_TV → 0    P-almost surely.

This is directional: Q learns to predict like P on histories generated under P.

For symmetric merging, require

    P ∼ Q,

meaning mutual absolute continuity.

### Dogmatic-zero diagnostic

A blocking zero exists when some event A satisfies

    P(A) > 0    and    Q(A) = 0.

This defeats P ≪ Q.

The audit must therefore distinguish:

- differing prior weights;
- very small but positive prior weights;
- explicit zero probability;
- logical impossibility;
- methodological exclusion;
- inadmissibility imposed by a tradition's evidence guard.

The uniqueness burden becomes operational:

Does the epistemology require live rival hypotheses to retain positive
probability, or may they be assigned zero before shared evidence arrives?

A zero does not itself prove non-merging, but it removes the Blackwell–Dubins
guarantee and identifies a possible permanent-disagreement mechanism.

### Aumann boundary

Aumann's agreement result applies when agents share a common prior and their
posterior probabilities are common knowledge.

It is therefore a theorem about coherence under shared prior structure, not a
direct test between traditions that reject a common prior, use different
possibility spaces, or condition on different admissibility systems.

---

## 3. Challenge protocols and undeclared selectors

A challenge of the form "produce something like T" is not scoreable until
"like" is operationalized.

Declare:

    S(x, T; λ, R, C),

where:

- x is the candidate;
- T is the reference;
- λ is the feature-weight vector;
- R is the rater or evaluator population;
- C is the comparison corpus or genre context.

The protocol must preregister:

    candidate eligibility
    reference text or corpus
    language constraints
    genre constraints
    length normalization
    feature family
    feature weights
    human or machine raters
    blinding procedure
    aggregation function
    decision threshold
    null corpus
    null distribution
    adversarial candidate process
    appeal procedure

The null score must be stated as

    S_null,

with the explicit recognition that its construction is selector-dependent.

The achievement is not a selector-free verdict. It is conversion of an
unscoreable challenge into a scoreable, inspectable, selector-laden protocol.

The selector burden must remain visible in the final result.

---

## 4. Audit-data endogeneity

Let H be the latent historical evidence field.

Let the admissibility guard be

    G : H → D_G,

where D_G is the preserved and admitted corpus visible to the auditor.

An audit that estimates the properties of G only from D_G is using data
already selected by the mechanism being audited.

This is audit-data endogeneity:

    D_G = G(H).

It is distinct from later corpus alteration. Even a perfectly preserved
admitted corpus remains selection-conditioned.

### Non-identifiability warning

From D_G alone, the auditor generally cannot distinguish:

- evidence that never existed;
- evidence that existed but was rejected;
- evidence that was destroyed;
- evidence that survived outside the guard;
- evidence that was admitted under a different description;
- evidence that entered through an exceptional pathway.

### Guard-differentiated channels

The mitigation is not to assume perfectly independent sources. It is to seek
channels with materially different selection mechanisms.

For each external channel C_k, record:

    production mechanism
    custody mechanism
    preservation mechanism
    discovery mechanism
    transcription mechanism
    institutional incentives
    relationship to audited guard
    known shared dependencies
    known adversarial dependencies

Candidate channel classes include:

- physical manuscripts;
- inscriptions;
- papyri;
- coinage;
- archaeological contexts;
- rival-school preservation;
- hostile or adversarial quotation;
- administrative documentation;
- accidental survival;
- independently transmitted translations.

These channels are guard-differentiated, not automatically statistically
independent.

### Evidence-dependence matrix

For channels C_1, …, C_n, construct a dependence matrix

    M_kl = Dep(C_k, C_l),

with declared qualitative or quantitative coding.

No triangulation claim may count two channels as independent merely because
they reside in different modern databases.

### Symmetric valence

Evidence must not receive a single scalar label such as "for" or "against."

For a frozen claim set

    𝒞 = {c_1, …, c_m},

each evidence item e receives a valence vector

    v(e) = ( v_1(e), …, v_m(e) ),    v_j(e) ∈ [−1, 1].

The same item may:

- support the accuracy of a traditional variation taxonomy;
- support the historical existence of real variation;
- support the consequential nature of standardization;
- undermine a stronger uniformity claim;
- leave an intentionality claim unresolved.

These effects must be recorded simultaneously.

The Ṣanʿāʾ lower text is suitable as a model case because it survives outside
the ordinary literary admissibility pathway and has been described in
scholarship as an extant witness to a textual tradition distinct from the
standard ʿUthmānic text. Its implications must be coded claim by claim rather
than compressed into a single apologetic or polemical direction.

---

## 5. Termination obligation

### Principle

An architecture is complete when its next admissible event is not about itself.

### Meta-amendment admissibility

After architecture freeze, a proposed formal amendment is admissible only if
it changes at least one executable field:

    sample frame
    source channel
    entity-resolution rule
    selector
    observable
    metric
    threshold
    falsifier
    analysis procedure
    event schema
    authority boundary

An amendment that merely increases coherence, elegance, analogy density,
explanatory unity, or mutual legibility is denied.

### Co-tuning null

Let L_n be the formal ledger after n rounds of refinement.

Sustained interaction between mutually legible models under a shared unifying
constraint is itself sufficient to generate increasing coherence:

    Coh(L_{n+1}) ≥ Coh(L_n)

without any corresponding increase in truth-tracking.

Therefore:

    ΔCoh > 0  ⇏  ΔEvidence > 0.

The architecture applies this null hypothesis to its own authors.

### Freeze rule

After this amendment:

- no fifth conceptual obligation is admitted;
- no further arrow taxonomy is admitted;
- no additional cross-domain correspondence is admitted;
- no refinement is accepted solely because it resolves conceptual discomfort.

The next valid ledger event must be one of:

    PILOT_SPEC_FROZEN
    CORPUS_SNAPSHOT_RECORDED
    ENTITY_MAP_FROZEN
    SAMPLE_FRAME_FROZEN
    SAMPLE_DRAWN
    OBSERVATION_RECORDED
    ANALYSIS_EXECUTED
    PROTOCOL_DEVIATION_RECORDED
    RESULT_ADMITTED
    RESULT_REJECTED

---

## Pilot Preregistration

### 6. Pilot identity

    pilot_id: MUSTALAH-ANANA-REPLAY-001
    title: Replayed treatment of a mudallis's an'ana
    mode: feasibility-first empirical replay
    status: preregistration-draft
    architecture_state: frozen
    primary_critics:
      - Yahya ibn Ma'in
      - Ahmad ibn Hanbal

The pilot does not attempt to validate or invalidate an entire hadith-critical
tradition.

It tests whether one frozen rule can be replayed against a bounded classical
evidence sample.

### 7. Research questions

RQ1 — Inter-critic agreement: On cases for which both critics have an eligible
recorded judgment, how often do their normalized dispositions agree?

RQ2 — Rule consistency: For each critic, how frequently does the recorded
disposition conform to the preregistered operational rule?

RQ3 — Symmetric valence treatment: After case characteristics are frozen, is
favorable material treated differently from unfavorable material under the
same declared rule?

No research question may be added after the corpus hashes are frozen.

### 8. Rule declaration

Before sampling, freeze:

    rule_id: MUSTALAH-RULE-001
    arabic_text: null
    translation: null
    classical_source: null
    source_locator: null
    applicability_conditions: []
    expected_disposition: null
    declared_exceptions: []
    non_applicable_conditions: []
    ambiguity_policy: EXCLUDE_PRIMARY_INCLUDE_SENSITIVITY

The rule must be quoted from a declared source.

The audit must not silently substitute a modern simplified maxim for the
source rule.

Minimum applicability fields — a case classification must distinguish:

- transmitter identity;
- whether the transmitter is classified as a mudallis;
- who supplies that classification;
- whether the isnād wording is ʿan;
- whether explicit audition is stated;
- whether contemporaneity is established;
- whether meeting is established;
- whether corroborating routes exist;
- whether an exception is invoked;
- whether the critic's statement is general or case-specific.

### 9. Corpus freeze

Each corpus receives:

    corpus_id: string
    title: string
    version: string
    publisher_or_editor: string
    retrieval_date: ISO-8601
    license: string
    source_location: string
    file_sha256: string
    record_count: integer
    encoding: string
    normalization_version: string
    included_sections: []
    excluded_sections: []
    known_ocr_defects: []
    known_editorial_interventions: []

No corpus may be replaced after sample generation.

A corrected corpus requires a new pilot identifier.

### 10. Entity resolution

Primary rule: stable corpus identifiers take precedence over string similarity.

Merge requirements — two records may be merged only when supported by at least
two independent identity features, such as:

    full name
    kunyah
    nisbah
    patronymic chain
    teachers
    students
    location
    generation
    death date
    explicit editor cross-reference

Prohibitions — do not merge solely because:

- normalized names match;
- an English transliteration matches;
- one field is a substring of another;
- a language model judges the names likely equivalent.

Ambiguity — ambiguous entities receive a unique unresolved identifier. They are:

- excluded from the primary analysis;
- retained in the sensitivity dataset;
- never silently assigned to the most probable identity.

Resolution log — every manual merge or split records:

    resolution_id: string
    record_ids: []
    decision: MERGE | SPLIT | UNRESOLVED
    features_used: []
    resolver_1: string
    resolver_2: string
    agreement: boolean
    adjudicator: string | null
    outcome_blinded: true

### 11. Sampling rule

Construct the full eligible overlap frame first.

Let N be the number of eligible cases with sufficient data.

    N < 30:
        stop as feasibility failure
    30 ≤ N ≤ 100:
        use the full census
    N > 100:
        select 100 cases deterministically

For N > 100, rank cases by

    h_i = SHA256( spec_hash ‖ case_id ),

and select the 100 smallest hashes.

This removes discretionary sampling after eligibility is known.

### 12. Outcome normalization

Preserve all raw critic language.

Map raw judgments into a frozen analysis vocabulary:

    ACCEPT
    REJECT
    CONDITIONAL
    UNRESOLVED
    NO_JUDGMENT

The mapping table must be frozen before the sample is drawn.

Every normalized outcome retains:

    raw Arabic text
    source citation
    editorial translation
    normalization rule
    normalizer identity
    uncertainty flag

### 13. Valence coding

Valence must be relative to a frozen proposition, not to "the tradition"
globally.

For each claim c_j, code:

    v_j(e) ∈ {−1, 0, +1},

where −1 is unfavorable to the named proposition, 0 neutral or irrelevant,
+1 favorable.

Coders must be blind to: critic identity; critic judgment; inclusion in
primary or sensitivity analysis.

Two independent coders classify each item. Disagreements are adjudicated, but
the original disagreement rate remains reported.

### 14. Primary measurements

14.1 Inter-critic agreement — primary statistic:

    A = (# exact agreements) / (# co-observed eligible cases).

Report the full contingency table. Secondary, selector-explicit statistics:
Cohen's κ; Gwet's AC1; bootstrap confidence intervals. No chance-corrected
coefficient is treated as uniquely canonical.

14.2 Rule consistency — for critic c:

    C_c = ( Σ_i 1[ judgment_ic conforms to rule ] ) / N_{c,applicable}.

Report: numerator; denominator; exception count; ambiguity count;
source-by-source breakdown.

14.3 Symmetric treatment — for critic c, define:

    Δ_c = P(ACCEPT | v = +1, c) − P(ACCEPT | v = −1, c).

Also report the same contrast for rejection, conditional treatment, and rule
conformity. Primary output is descriptive. No causal claim is permitted from
the pilot. Where data permit, report stratified contrasts by: transmitter;
source; period; explicit-audition status; corroboration status.

### 15. Falsifiers

The pilot must be capable of producing findings adverse to every major
interpretation. Examples include:

    low inter-critic agreement
    high agreement but low rule consistency
    high consistency for only one critic
    large favorable/unfavorable asymmetry
    apparent symmetry explained by case imbalance
    insufficient overlap for measurement
    entity ambiguity too high for reliable replay
    rule too underspecified to operationalize
    source editions too editorially dependent

A feasibility failure is a result, not permission to redefine the question
post hoc.

### 16. Protocol deviations

Every deviation records:

    deviation_id: string
    detected_at_stage: string
    description: string
    reason: string
    affected_records: []
    effect_on_primary_analysis: string
    operator_decision: CONTINUE | RESTART | TERMINATE
    approval_receipt: string

No deviation may be hidden inside cleaning code.

### 17. AEGIS event format

    {
      "event_version": "1.0",
      "event_id": "sha256:...",
      "event_type": "CORPUS_SNAPSHOT_RECORDED",
      "pilot_id": "MUSTALAH-ANANA-REPLAY-001",
      "parent_event_id": "sha256:...",
      "spec_hash": "sha256:...",
      "source_roots": ["sha256:..."],
      "actor": { "id": "operator-or-process-id", "role": "CURATOR" },
      "authority": {
        "decision": "ALLOW",
        "policy_id": "AEGIS-EPISTEMIC-PILOT-1",
        "approval_receipt": "sha256:..."
      },
      "payload_hash": "sha256:...",
      "payload": {},
      "observational_metadata": { "recorded_at": "ISO-8601" },
      "signature": {
        "algorithm": "declared-algorithm",
        "key_id": "declared-key-id",
        "value": "..."
      }
    }

Wall-clock time is observational metadata, not part of the deterministic
identity root unless the protocol explicitly requires it.

### 18. Admission gates

A result may not be admitted unless:

    spec hash matches frozen preregistration
    corpus hashes match
    entity map hash matches
    sample algorithm reproduces the sample
    analysis code hash matches
    all deviations are disclosed
    all exclusions are enumerated
    raw counts are included
    valence coder agreement is reported
    no post-freeze metric substitution occurred

The result receipt must distinguish:

    MEASURED
    INCONCLUSIVE
    FEASIBILITY_FAILURE
    PROTOCOL_VIOLATION
    REJECTED

### 19. Final stopping condition

After PILOT_SPEC_FROZEN, the next accepted event must contain either: a corpus
hash; an entity-resolution decision; a sampled case; an observed judgment; an
analysis output; or a protocol deviation.

Another conceptual refinement is denied unless it identifies a blocking defect
that makes execution impossible.

The formal ledger is closed.

The next entry is the first replayed denial.
