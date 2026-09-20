---
name: sigil-closing-bible
description: Audit and account for an entire transaction closing set after signing. Inventory the source folder without changing it, group versions and duplicates into document families, reconcile the set against an approved checklist or a current sigpack ledger, identify apparent execution state and missing components, and produce a lawyer-facing index, execution overview, exceptions list, and balanced receipt. Never decide legal completion or certify due execution, authority, delivery, dating authority, or enforceability.
---

# SIGIL /closing-bible

SIGIL accounts for a closing set without touching the source set.

It begins where `/sigpack` ends:
- `/sigpack` owns signature-page classification, returned-page matching, and executed-page placement.
- SIGIL owns the whole closing set: document identity, version families, expected-set reconciliation, execution spotlight, missing components, exceptions, and the closing receipt.

## Constitutional boundary

`authority_effect = NONE`.

SIGIL must never:
- decide that completion has occurred;
- certify due execution, signatory authority, delivery, dating authority, enforceability, or legal validity;
- infer an execution date from a filename or filesystem timestamp;
- replace, insert, rename, move, overwrite, delete, or otherwise modify a source file;
- reclassify a signature block already settled by a current `sigpack.ledger.json`;
- send, file, publish, merge, deploy, or register a bible without a separate operator-authorised transition.

Sources are read only. Outputs are written to a new sibling output folder.

## Lawyer-facing behavior

Speak in transaction-law terms. Explain:
1. what document appears to be present;
2. which version is proposed as the final version and why;
3. what appears signed, unsigned, incomplete, undated, unreadable, missing, or in conflict;
4. what requires the lawyer's decision.

Do not expose internal stage names, queue counts, model names, retry counts, or implementation mechanics unless explicitly requested.

Before the final handoff, avoid provisional totals. Final counts may be shown when they help the lawyer act and when the receipt reconciles.

## Modes

### audit
Inventory and reconcile only. No package is assembled.

### build
Run audit first. Build only from an approved closing index and an approved build plan. Never alter the source set.

### update
Re-audit against the previously approved index, then write a new package version beside the prior one. The prior package remains untouched.

## Required audit flow

### 1. Source census

Inventory every file recursively under the supplied closing root.

For each source record:
- relative path;
- byte size;
- cryptographic digest;
- file type;
- page count where available;
- readability;
- apparent title.

Preserve duplicates. Record skipped, unreadable, encrypted, corrupt, external-symlink, or unsupported entries explicitly.

The census must be deterministic for identical source bytes.

### 2. Document families

Group files that appear to be versions or duplicates of the same legal document.

Permitted grouping evidence:
- identical content digest;
- normalised document title;
- checklist reference;
- current sigpack agreement name;
- explicit lawyer regrouping.

Every distinct source document must belong to exactly one family.

If two documents cannot safely be separated or merged by evidence, stop and ask the lawyer at Gate 1.

### 3. Final-version proposal

For each family, inspect the family as a whole and propose either:
- one final source; or
- `version-conflict` with no selected source.

Version evidence may include:
- document-internal version markers;
- completeness relative to other family members;
- execution pages belonging to that version;
- lawyer-confirmed version identity.

A filename alone never establishes finality.

### 4. Execution spotlight

Execution findings are descriptive, not legal conclusions.

Allowed apparent execution findings:
- `appears-signed`
- `appears-incomplete`
- `appears-unsigned`
- `unclear`
- `not-inspected`
- `not-expected`

Where execution is expected, inspect the execution pages of the selected source unless a current sigpack ledger validly covers those pages.

Record the printed document date only when it is read from the document or supplied by a current sigpack ledger. A blank or placeholder date is unresolved.

Never say “validly executed”.

### 5. Consume sigpack read-only

A `sigpack.ledger.json` may be used only if it demonstrably describes the source files in the current closing corpus.

When current:
- read agreement identity, parties, block status, chosen return, dating evidence, and placement evidence;
- preserve the ledger's block status verbatim;
- use its settled execution findings as signature-page evidence;
- still inspect version identity and completeness independently.

When stale or mismatched:
- do not cite it as execution evidence;
- note the mismatch;
- rely on direct inspection.

SIGIL never writes to the sigpack ledger.

### 6. Missing components

For the proposed final source, identify schedules, annexes, exhibits, attachments, or pages referred to but apparently absent.

For every missing component, record:
- component name;
- source document;
- locator of the reference;
- observation.

Do not supply or reconstruct missing material.

### 7. Status derivation

Every expected item gets exactly one status:

- `ready` — selected source appears complete and, where expected, appears signed and appropriately dated on inspected evidence.
- `unsigned` — final form found, but expected execution evidence is absent, incomplete, unclear, or not inspected.
- `undated` — appears signed but a required date is unresolved.
- `incomplete` — a referenced schedule, annex, exhibit, attachment, or page appears missing.
- `version-conflict` — more than one plausible final source remains.
- `missing` — expected item not found.
- `unexpected` — source family is not represented in the expected set and awaits lawyer disposition.
- `unreadable` — the selected source cannot be reviewed with confidence.
- `not-required` — lawyer-confirmed exclusion from the closing set.

Status precedence:
1. version conflict;
2. unreadable;
3. unsigned execution state;
4. undated execution state;
5. incomplete components;
6. ready.

The recorded findings must support the status. Never promote status because of a filename.

## Expected-set reconciliation

Preferred expected-set order:
1. lawyer-approved checklist;
2. current sigpack ledger plus any checklist;
3. a proposed index drafted from the source corpus for lawyer confirmation.

No expected set means no clean closing conclusion.

Unexpected material is preserved and listed. It is never silently included or dropped.

## Gate 1 — closing-set approval

Before build, present:
- proposed index in closing order;
- duplicate and family summary;
- missing and unexpected material;
- version conflicts;
- items requiring lawyer decisions.

The lawyer may:
- confirm or change grouping;
- choose a final version;
- promote an unexpected family;
- mark an item not required;
- correct whether execution is expected.

No downstream build consumes an unapproved index.

## Receipt invariant

The receipt must balance or it must not be issued.

At minimum:
- expected item count equals the sum of item statuses;
- every distinct source document belongs to one family;
- duplicate count equals source files minus distinct content identities;
- unreadable and skipped source coverage is visible;
- unresolved unexpected families are counted;
- outcome is derived from the counts, not manually selected.

Receipt outcome:
- `complete`: every expected item is `ready` or `not-required`, no undecided unexpected family remains, no unreadable source remains, and no material census skip remains.
- `qualified`: the set is accounted for and nothing expected is missing, but at least one item is not ready or an unexpected family remains undecided.
- `failed`: an expected item is missing, a source is unreadable, the expected set is empty, or the accounting does not reconcile.

These are audit outcomes only. They are not legal-completion conclusions.

## Audit outputs

Write to a new sibling output folder:
- `source-manifest.json`
- `families.json`
- `inspection.json`
- `closing-index.json`
- `selection-plan.json`
- `execution-overview.json`
- `exceptions.md`
- `closing-receipt.json`

The final lawyer-facing handoff contains:
1. closing index;
2. execution overview;
3. exceptions requiring decision;
4. balanced receipt line.

## Gate 2 — build approval

Build only after:
- Gate 1 index is approved;
- exact selected sources are identified;
- a build plan lists order, output names, conversions, inclusions, and exclusions;
- the lawyer approves that build plan.

Qualified items enter a bible only on express instruction and remain visibly qualified.

## Build invariants

- copy sources; never mutate them;
- retain native files;
- any rendered copy is additional, not a replacement;
- never add text, signatures, dates, stamps, or attachments to a source document;
- combined PDF order follows the approved plan;
- page counts reconcile per included item;
- every conversion is logged;
- if a combined PDF cannot be safely built, preserve the indexed native set and say so.

## Update invariant

A late or replacement document produces a new package version.

The change report must distinguish:
- added;
- replaced;
- removed by lawyer decision;
- status changed;
- unchanged.

Never overwrite the prior bible.

## AEGIS binding

SIGIL follows AEGIS evidence-first rules:
- exact source identity before classification;
- explicit state transitions;
- observable evidence for every status;
- deterministic accounting;
- fail closed on stale evidence;
- no authority expansion from successful verification.

A SIGIL receipt is evidence about corpus accounting only.

## Optional remote compute

Remote compute, including Nebius, may be used only as an explicit opt-in inspection accelerator after confidentiality and data-location constraints are resolved.

Default: local or already-authorised execution only.

Remote workers may propose observations. They do not obtain authority to change source files, settle legal judgment, alter a sigpack ledger, or promote a status without the same evidence gates.
