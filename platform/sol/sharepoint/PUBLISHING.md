# SharePoint Knowledge Publishing Policy

SharePoint is the approved human-readable publication surface for SOL operating knowledge. It is not the executable policy root.

## Intended library structure

```text
AEGIS-OMEGA/
  00-Governance/
  10-Architecture/
  20-Runbooks/
  30-Provider-Integrations/
  40-Evaluations/
  50-Receipts-and-Releases/
  90-Archive/
```

## Required metadata

Every published document must carry:

- source repository;
- source Git ref and commit SHA;
- source path;
- document digest;
- AEGIS receipt root when applicable;
- evidence tier;
- owner;
- review state;
- published time;
- supersedes/superseded-by relation.

## Publication workflow

1. Material is authored and reviewed in GitHub.
2. CI validates schemas, links, and prohibited secret patterns.
3. Automaton-3 admits the exact publication candidate.
4. The publisher uploads a versioned immutable copy to SharePoint.
5. A publication receipt records the Graph item ID, version ID, source commit, and content digest.
6. A mutable index page may point to the current version, but previous versions are retained.

## Precedence

When content conflicts:

1. executable repository policy and schemas;
2. admitted Git commit and receipt;
3. versioned SharePoint publication;
4. draft SharePoint notes;
5. model-generated summaries.

SharePoint content cannot grant authority or amend executable policy.

## Access

- Default sharing scope: organization, view-only.
- Edit permission is limited to maintainers of the corresponding repository area.
- Anonymous links are prohibited for governance, security, receipts, or private integration material.
- Named recipient invitations require an explicit operator request.

## Current connector limitation

The connected Microsoft account is a personal MSA surface rather than a SharePoint organizational tenant. Microsoft Graph search returned that the enterprise search API is unsupported for this account. The intended library cannot be safely created until an organizational SharePoint site is connected or an exact existing site URL is supplied. No folders or files were created under the personal account as a substitute.