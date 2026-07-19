# Automaton-3 threat model

## Protected assets

Canonical repository state, constitutional files, capability registry, policy roots, workflow state, database governance state, external side effects, operator approvals, receipts, and attestations.

## Trust boundaries

The operator, requesting actor, configured model, reviewing model, physical executor, tool process, workflow runner, repository workspace, and external provider are distinct identities. None is inferred from another.

## Primary threats and controls

| Threat | Control | Failure mode |
|---|---|---|
| Unknown or documentation-only capability | Evidence registry plus minimum three validated runs | `UNMAPPED_CAPABILITY`, `UNOBSERVED_CAPABILITY`, or `INSUFFICIENT_VALIDATED_RUNS` |
| Repository or namespace confusion | Canonical remote, real-path root checks, nested-repository selection, path-view reconciliation | workspace denial receipt |
| Symlink, traversal, mount, UNC, WSL, drive, or case escape | `resolve(strict)` containment and normalized path-view comparison | no mutation |
| Controller identity conflation | Separate actor, model, session, executor, tool, and workflow fields | invalid identity envelope |
| Concurrent or stale writers | single active lease, generation, fencing token, expected parent, replay set | deterministic lease denial |
| Workflow invisibility or orphaning | durable registry, monotone transitions, heartbeat generation, cancellation and orphan state | authority revoked |
| Retry duplicates | per-execution idempotency keys and terminal-state checks | `DUPLICATE_EXTERNAL_ACTION` |
| Raw peer instructions becoming authority | typed EventEnvelope, bounded text, payload digest, policy and receipt references | envelope rejected |
| Unicode/control-character bypass | NFC equality and Unicode control-category rejection in authority fields | identity/event denial |
| Broken evidence or receipt chain | repository containment, file existence, parent digest, monotone sequence | exact denial code |
| Authority service outage | no local fallback | `AUTHORITY_SERVICE_UNAVAILABLE` |
| Operator notification suppression | notifications and receipts are outside peer-message restrictions | constitutional violation |

## Residual risks

The local lease and durable registry are reference implementations. Multi-host persistence requires a transactional backend that enforces the same compare-and-swap, generation, parent-hash, idempotency, and cancellation contracts. No distributed exact-once claim is made.

GitHub branch-ruleset administration depends on repository administration API access. A tracking issue and exact configuration artifact are required when that interface is unavailable.
