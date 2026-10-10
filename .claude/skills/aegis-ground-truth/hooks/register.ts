import type { Register, EngineInterface } from 'claude-code'

// Measured state comes from the repo's own scripts/agent_context.py, so humans,
// Codex and classic hooks read the same truth this mod injects.
const SCRIPT = 'scripts/agent_context.py'
const MAIN = /^(origin\/)?main$/

async function context($: EngineInterface, query: string): Promise<string | undefined> {
  const root = await $.session.root()
  const ran = await $.process.run(['python3', SCRIPT, query.slice(0, 2000)], { cwd: root, timeoutMs: 20000 })
  return ran.exitCode === 0 && ran.stdout.trim() ? ran.stdout.trim() : undefined
}

// Base a shell command would branch from or open a PR against, when it names one.
export function stackedBase(command: string): string | undefined {
  const branch = command.match(/git\s+(?:checkout\s+-[bB]|switch\s+-[cC]|branch)\s+(?!-)(\S+)\s+([^\s;&|]+)/)
  if (branch && !branch[2].startsWith('-') && !MAIN.test(branch[2])) return branch[2]
  const pr = command.match(/gh\s+pr\s+create\b.*?(?:--base[=\s]|-B\s+)([^\s;&|]+)/)
  if (pr && !MAIN.test(pr[1])) return pr[1]
  return undefined
}

const refuse = (base: string) =>
  `aegis-ground-truth: '${base}' is not main. Stacking branches/PRs on unmerged branches is how ` +
  `this repo reached 391 open PRs. Branch from origin/main and target main; if you need ` +
  `unmerged work, get that PR merged first or say so to the operator.`

export const register: Register = on => {
  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'aegis',
      description: 'Measured AEGIS state: main age, open-PR queue, PRs overlapping <task>',
      argumentHint: '[task text]',
    })
    return next(e)
  })

  on('command.run', { command: 'aegis' }, async ($, e) => {
    const text = (await context($, e.args)) ?? `${SCRIPT} not found or failed in this project.`
    return { text, context: [text] }
  })

  on('prompt.submit', async ($, e, next) => {
    if (e.origin.kind !== 'composer' && e.origin.kind !== 'bridge') return next(e)
    const text = await context($, e.text).catch(() => undefined)
    return next(text ? { ...e, context: [...(e.context ?? []), text] } : e)
  })

  on('tool.call', { tool: 'Bash' }, ($, e, next) => {
    const base = stackedBase(e.command)
    return base ? { deny: refuse(base) } : next(e)
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'aegis-ground-truth: its guard failed.' }))

  on('tool.call', { tool: 'mcp__github__create_pull_request' }, ($, e, next) => {
    const base = String((e as { base?: unknown }).base ?? 'main')
    return MAIN.test(base) ? next(e) : { deny: refuse(base) }
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'aegis-ground-truth: its guard failed.' }))

  on('tool.call', { tool: 'mcp__github__create_branch' }, ($, e, next) => {
    const from = (e as { from_branch?: unknown }).from_branch
    return from === undefined || MAIN.test(String(from)) ? next(e) : { deny: refuse(String(from)) }
  }).catch(($, e, next) => (next.called ? next(e) : { deny: 'aegis-ground-truth: its guard failed.' }))
}
