// TypeScript declarations for the adjacent runtime .mjs security guard.
export declare const BLOCKED_PUBLIC_PROVIDER_KEYS: readonly string[]
export declare function assertNoPublicProviderKeys(env: Record<string, unknown> | null | undefined): void
