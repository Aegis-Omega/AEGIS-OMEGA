# Agent Action Boundary Audit — Pilot Scope Worksheet V1

Status: NON-CONTRACTUAL TECHNICAL WORKSHEET  
Purpose: define a candidate pilot before commercial or legal commitment  
Authority effect: NONE

This worksheet records technical scope only. It is not a contract, order form, statement of work, invoice, certification, or authorization to access production systems.

## A. Workflow identity

Buyer / organization:

Workflow name:

Workflow version or commit:

Primary environment:
- [ ] Local
- [ ] Test
- [ ] Staging
- [ ] Production requested separately

Workflow owner / technical contact:

## B. Highest-authority action

Describe the highest-authority action the workflow can perform:

Target system:

Mutation type:

Examples:
- database write;
- repository write;
- deployment;
- external message;
- infrastructure/config change;
- financial action;
- identity/credential action;
- destructive delete.

## C. Control point to test

What control is expected to authorize or deny the action?

Where is the decision made?

What exact action/parameters should the approval be bound to?

What happens when approval is:
- missing?
- stale?
- expired?
- for a different target?
- for different parameters?
- replayed?

## D. Evidence available

Check only what can be provided safely:

- [ ] architecture/data-flow description
- [ ] sanitized logs
- [ ] sanitized receipts
- [ ] test fixtures
- [ ] staging access
- [ ] source/repository excerpt
- [ ] policy/configuration excerpt
- [ ] CI/test output
- [ ] other:

Do not include raw credentials, private keys, customer records, production secrets, or unrelated sensitive data.

## E. Negative test candidates

Candidate unauthorized condition 1:

Expected behavior:

Candidate unauthorized condition 2:

Expected behavior:

Candidate replay/stale-authority condition:

Expected behavior:

## F. Finding states

Each control will be recorded only as:

- DEMONSTRATED_FAIL_CLOSED
- DEMONSTRATED_FAIL_OPEN
- NOT_VERIFIED

No stronger conclusion is implied.

## G. Explicit exclusions

Out of scope for this candidate pilot:

- platform-wide certification;
- legal/compliance opinion;
- unapproved production mutation;
- credential collection during initial scoping;
- unrelated systems;
- claims beyond the exact tested version/configuration.

Additional exclusions:

## H. Access boundary

Does the candidate test require production access?
- [ ] No
- [ ] Unknown
- [ ] Requested separately

If access is requested later, record:

Exact environment:

Exact purpose:

Exact permissions:

Duration:

Revocation path:

Operator / buyer approval reference:

## I. Evidence package identity

Evidence source references:

Environment/version identifiers:

Exact commit/image/configuration if applicable:

Test timestamps:

Known evidence gaps:

## J. Commercial handoff boundary

Technical scoping complete:
- [ ] No
- [ ] Yes

Written commercial terms agreed:
- [ ] No
- [ ] Yes

Payment observed:
- [ ] No
- [ ] Yes

Audit actually started:
- [ ] No
- [ ] Yes

These are separate states. No earlier state implies a later one.
