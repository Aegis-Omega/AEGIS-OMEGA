#!/usr/bin/env node
// Generates a fresh P-256 ECDSA key pair for the AEGIS grant token system.
//
// Usage:
//   node scripts/gen-grant-keypair.mjs
//
// Output:
//   1. GRANT_PRIVATE_KEY_JWK — set this as a Supabase secret:
//        supabase secrets set GRANT_PRIVATE_KEY_JWK='<value>'
//
//   2. GRANT_PUBLIC_JWK — replace the hardcoded constant in:
//        packages/shared/lib/access.ts   (GRANT_PUBLIC_JWK)
//        hub/src/lib/access.ts           (GRANT_PUBLIC_JWK)
//
// After rotation, redeploy both edge functions:
//   supabase functions deploy issue-token --no-verify-jwt
//   supabase functions deploy restore-access --no-verify-jwt

const { subtle } = globalThis.crypto

const keyPair = await subtle.generateKey(
  { name: 'ECDSA', namedCurve: 'P-256' },
  true,
  ['sign', 'verify'],
)

const privateJwk = await subtle.exportKey('jwk', keyPair.privateKey)
const publicJwk  = await subtle.exportKey('jwk', keyPair.publicKey)

// Strip key_ops / ext so the stored private key is clean
const { key_ops: _kop, ext: _ext, ...privateClean } = privateJwk
// Public key needs key_ops: ['verify'], ext: true for client importKey call
const publicEmbedded = { key_ops: ['verify'], ext: true, ...publicJwk }

console.log('\n═══════════════════════════════════════════════════════════')
console.log(' AEGIS Grant Key Pair — generated', new Date().toISOString())
console.log('═══════════════════════════════════════════════════════════\n')

console.log('── 1. SUPABASE SECRET (private key) ─────────────────────────')
console.log('   Run this command to set the secret:\n')
console.log(`   supabase secrets set GRANT_PRIVATE_KEY_JWK='${JSON.stringify(privateClean)}'\n`)

console.log('── 2. CLIENT PUBLIC KEY (embed in access.ts files) ──────────')
console.log('   Replace GRANT_PUBLIC_JWK in:')
console.log('     packages/shared/lib/access.ts')
console.log('     hub/src/lib/access.ts\n')
console.log('   const GRANT_PUBLIC_JWK =', JSON.stringify(publicEmbedded, null, 2))
console.log('\n── 3. AFTER ROTATION ────────────────────────────────────────')
console.log('   supabase functions deploy issue-token --no-verify-jwt')
console.log('   supabase functions deploy restore-access --no-verify-jwt')
console.log('\n⚠️  The private key above grants token-signing authority.')
console.log('   Never commit it. Store it only in Supabase secrets.\n')
