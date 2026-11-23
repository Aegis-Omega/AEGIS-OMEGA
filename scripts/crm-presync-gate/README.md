# AEGIS CRM pre-sync gate v1 (offline, read-only)

This is executable Python for a *preflight candidate-matching audit*, not a HubSpot sync client.
It does not call external APIs, update contacts, or invoke imports or activations.
It runs entirely offline on operator-provided CSV snapshots.

## Usage

```sh
python aegis_crm_presync_gate.py \
  --crm fixtures/crm.csv \
  --source google_contacts=fixtures/google_contacts.csv \
  --source outlook_default=fixtures/outlook_default.csv \
  --source outlook_iphone=fixtures/outlook_iphone.csv \
  --out candidates.json
python -m unittest discover -s tests -v
```

## Input contract

HubSpot contact CSV **must** have `hs_object_id,email`. Optional columns are
`phone,mobilephone,company`. CRM object IDs must be unique.

Each external source CSV **must** have `source_record_id,email`. Optional columns:
`phone,company`. `source_record_id` must be nonempty, unique **within its named
source**, and opaque (must not contain `@`). Sources are separate namespaces;
never use the email itself as a source ID. Repeating a source name is rejected.

UTF-8 with or without BOM is accepted. Required sources default to
`google_contacts`, `outlook_default`, `outlook_iphone`. Missing source **files**
are represented as missing/UNKNOWN, never as zero rows. A valid, supplied
header-only source file is correctly recorded as zero rows in *that file*, not
as zero rows in live Data Studio.

Output excludes email addresses, phone numbers and contact names. It contains
source-native IDs and *candidate* HubSpot IDs, never permission to merge.
If IDs are personally identifying in your provider, restrict output access.
Source file SHA-256 digests establish which bytes were analyzed, not source
freshness or completeness.

## Status/exit contract

- 0: complete three-source input evaluation, **still HOLD** for every CRM write
- 2: invalid or unreadable input; **HOLD**
- 3: one or more required source snapshots missing; **HOLD**

Even exit 0 never means safe to sync. Every record verdict is review-only.
Cross-source collisions, missing emails, non-CRM emails, conflicting phones,
and incompatible organization values are never used to auto-update CRM.
A cross-source email overlap means the normalized email appears in at least two
distinct named source namespaces. Repeated normalized emails within one source
are flagged as `DUPLICATE_EMAIL_WITHIN_SOURCE` and remain `FIELD_REVIEW`, not
`CROSS_SOURCE_REVIEW`. The report also counts
`same_source_duplicate_email_groups`. Both conditions can exist simultaneously;
all candidate verdicts remain non-authorizing.
No fuzzy name match, Gmail plus-address aliasing, phone-based matching, or
permission inference is performed.

Before a real sync, independently inspect Data Studio activation modes,
match keys, last/next runs, account ownership, license, billing impact,
source freshness, consent, and an explicit operator-approved change scope.

## Safety

The fixture data uses reserved `.test` domains and is synthetic. None of the
42 real HubSpot CRM contacts nor the connected Google Contacts record are
included in this package. No Microsoft connector was accessed for this tool.
