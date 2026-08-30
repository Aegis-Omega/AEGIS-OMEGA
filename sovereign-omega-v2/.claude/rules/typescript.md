# TypeScript Rules
## Applied to: src/**/*.ts, test/**/*.ts
## Epistemic Tier: T0

All TypeScript code in this project uses strict mode with exactOptionalPropertyTypes
and noUncheckedIndexedAccess enabled. These settings are non-negotiable and must not
be disabled or suppressed with @ts-ignore or @ts-expect-error without a Guardian-approved
justification comment explaining why the suppression is necessary and safe.

Branded types must be used for all domain-critical primitives: UUIDv7, SHA256Hex,
BoundedDelta, and SequenceNumber. Never use raw string or number where a branded type
is defined. The normalizeDelta function in src/core/types.ts is the only permitted
path for producing a BoundedDelta value.

All functions that could throw must document their error conditions. All async functions
that return Promises must handle rejection paths explicitly — never leave unhandled
Promise rejections.

Components under 150 lines. If a module exceeds 150 lines, decompose it. The sole
exception is type definition files, which may be longer if the types are cohesive.

Imports must use the .js extension suffix for all relative imports, even in TypeScript
source files. This is required for ESM compatibility with the bundler configuration.
