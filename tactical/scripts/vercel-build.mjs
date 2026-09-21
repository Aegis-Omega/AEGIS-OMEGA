#!/usr/bin/env node
import { spawnSync } from 'node:child_process'

function fail(message) {
  console.error(`TACTICAL_VERCEL_PREFLIGHT_DENIED: ${message}`)
  process.exit(1)
}

const onVercel = process.env.VERCEL === '1'
const bridge = (process.env.VITE_BRIDGE_URL ?? '').trim()

if (onVercel) {
  if (!bridge) fail('VITE_BRIDGE_URL is required on Vercel')
  let parsed
  try {
    parsed = new URL(bridge)
  } catch {
    fail('VITE_BRIDGE_URL must be an absolute URL')
  }
  if (parsed.protocol !== 'https:') {
    fail('VITE_BRIDGE_URL must use HTTPS on Vercel')
  }
  if (parsed.username || parsed.password) {
    fail('VITE_BRIDGE_URL must not contain credentials')
  }
  console.log(`TACTICAL_VERCEL_BRIDGE=${parsed.origin}`)
}

if (process.env.AEGIS_DEPLOY_PREFLIGHT_ONLY === '1') {
  console.log('TACTICAL_VERCEL_PREFLIGHT=PASS')
  process.exit(0)
}

const result = spawnSync('npm', ['run', 'build'], {
  stdio: 'inherit',
  env: process.env,
  shell: false,
})
if (result.error) {
  fail(`failed to start npm build: ${result.error.name}`)
}
if (result.status !== 0) {
  process.exit(result.status ?? 1)
}
