#!/usr/bin/env node
import { existsSync } from 'node:fs'
import process from 'node:process'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'

const SAFE = /^[A-Za-z0-9._:/@+\-]{1,128}$/
const ENV_NAME = /^[A-Z][A-Z0-9_]{0,63}$/
const here = dirname(fileURLToPath(import.meta.url))
const repoRoot = resolve(here, '..')

function fail(code, detail = '') {
  process.stderr.write(`${code}${detail ? `:${detail}` : ''}\n`)
  process.exit(2)
}

function resolveModel(provider, arg) {
  if (!arg) return provider
  if (!arg.startsWith('@')) return arg
  const envName = arg.slice(1)
  if (!ENV_NAME.test(envName)) fail('AEGIS_MODEL_ENV_NAME_INVALID')
  return process.env[envName] || provider
}

const provider = process.argv[2]
const model = resolveModel(provider, process.argv[3])
if (!provider || !SAFE.test(provider)) fail('AEGIS_PROVIDER_ID_INVALID')
if (!model || !SAFE.test(model)) fail('AEGIS_MODEL_ID_INVALID')

const suppliedSession = process.env.AEGIS_PROVIDER_SESSION_ID
const generatedSession = `session:${provider}:${process.pid}:${Date.now()}`
const session = suppliedSession || generatedSession
if (!SAFE.test(session)) fail('AEGIS_PROVIDER_SESSION_ID_INVALID')

process.env.AEGIS_PROVIDER_ID = provider
process.env.AEGIS_MODEL_ID = model
process.env.AEGIS_PROVIDER_SESSION_ID = session
process.env.AEGIS_REPO_ROOT = repoRoot

const serverPath = join(repoRoot, 'sovereign-omega-v2', 'mcp-server', 'dist', 'index.js')
if (!existsSync(serverPath)) fail('AEGIS_MCP_BUILD_MISSING', 'run npm --prefix sovereign-omega-v2/mcp-server run build')

if (process.argv.includes('--describe')) {
  process.stdout.write(JSON.stringify({
    launcher_kind: 'AEGIS_PROVIDER_MCP_LAUNCHER_V1',
    provider,
    model,
    session,
    repo_root: repoRoot,
    server_path: serverPath,
    authority: 'IDENTITY_ONLY_NOT_AUTHORIZATION',
  }, null, 2) + '\n')
  process.exit(0)
}

await import(pathToFileURL(serverPath).href)
