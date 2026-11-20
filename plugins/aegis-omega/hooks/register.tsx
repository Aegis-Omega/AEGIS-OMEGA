import { atom, read, update } from 'claude-code'
import type { Register } from 'claude-code'

import type { LedgerEntry, Stats } from '../types'

const PANE = 'aegis-omega'
const ledger = atom({ plugin: 'aegis-omega', key: 'ledger' } as const, [] as LedgerEntry[], {
  shape: 'ledger-1',
})
const stats = atom(
  { plugin: 'aegis-omega', key: 'stats' } as const,
  { prompts: 0, calls: 0, pushes: 0, blocked: 0 } as Stats,
  { shape: 'stats-1' },
)

// Facts every new agent otherwise rediscovers, or gets wrong, in its first turns.
const FACTS = `# AEGIS Omega operating facts (aegis-omega mod)

- The user writes Bosnian (BHS): answer in BHS, briefly. An imperative is a command: do the work, do not hand steps back. A question is asked in question form.
- RH lab: Aegis-Omega/formal-conjectures PR #92 (draft, never merge), branch fix/rh-live-evidence-provenance-20261024 (GitHub MCP owner tarikskalic33, repo formal-conjectures). Read research/rh/aegis_math/HANDOFF.md first and update its section 5 at the end. Evidence kinds are never promoted (lean_kernel, certified_numerical, numerical, literature, external_claim, open); never declare RH proved.
- Paths differ by host: Claude Code cloud checks out to /home/user/<repo>, Codex to /workspace/<repo>. Never hard-code either; scripts/agent-env-setup.sh in AEGIS-OMEGA finds the repository itself.
- New Claude sessions in the "Uhm" environment must use AEGIS-OMEGA as their source (its setup script expects it).
- In AEGIS-OMEGA the authority guard (scripts/claude-authority-guard.py) blocks pushing from the shell: push with mcp__github__push_files to an explicit non-main branch, check the branch head first, verify the blob SHAs after. Never write to main; never merge without the user's explicit word.
- The weekly plan limit is the binding constraint. This mod's shield refuses subagents, workflows, scheduled wake-ups and new sessions unless the user's latest message asks for them; when it refuses, do the work in this session instead.
- UI-only (no tool can do them): enabling GitHub Pages, installing the Claude GitHub App, approving bot workflow runs, deleting branches, editing an environment's setup script. Say so once and move on.`

// Tools that spend the plan limit in the background.
const COSTLY = new Set([
  'Agent',
  'Workflow',
  'ScheduleWakeup',
  'mcp__Claude_Code_Remote__send_later',
  'mcp__Claude_Code_Remote__create_trigger',
  'mcp__Claude_Code_Remote__create_session',
])
// Words with which the user asks for exactly that, in BHS or English.
const OPT_IN =
  /(agent|delegiraj|workflow|paralel|zaka[zž]|schedul|podsjeti|sesij|session|branchaj|ultracode)/i
const PUSH = new Set(['mcp__github__push_files', 'mcp__github__create_or_update_file'])

const FRONTIER = [
  'RH ⇔ aritmetički znak na prozorima L > 11/16 (Lean kernel)',
  'dokazano: svi prozori L ≤ 11/16 · 4 prepreke · moment-killer',
  'λ0(3/2) ≤ 4.22e-26 (arb): budžet mora padati kao exp(−4π e^{2a})',
  'sljedeće: certificirani simple-even na a = 0.3 (HANDOFF Q2)',
]

export const register: Register = on => {
  let lastPrompt = ''

  const status = (s: Stats) =>
    `Ω ${s.calls} poziva · ${s.pushes} push · ${s.blocked} štit`

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'omega',
      description: 'AEGIS Omega Mission Control: RH frontier, session spending, push ledger',
    })
    $.ui.status(status(await read($, stats)))

    return next(e)
  })

  on('command.run', { command: 'omega' }, async $ => {
    await $.ui.open({ id: PANE, title: 'AEGIS Ω' })
    const s = await read($, stats)

    return { text: `AEGIS Ω otvoren. ${status(s)}.` }
  })

  on('prompt.compose', async ($, e, next) => {
    const result = await next(e)

    return {
      sections: [
        ...result.sections.filter(one => one.id !== 'aegis-omega:facts'),
        { id: 'aegis-omega:facts', text: FACTS, scope: 'session' as const },
      ],
    }
  })

  on('prompt.submit', async ($, e, next) => {
    lastPrompt = e.text
    await update($, stats, s => ({ ...s, prompts: s.prompts + 1 }))

    return next(e)
  })

  on('tool.call', async ($, e, next) => {
    const at = await $.clock.now()
    const s = await update($, stats, one => ({ ...one, calls: one.calls + 1 }))

    if (COSTLY.has(e.tool) && !OPT_IN.test(lastPrompt)) {
      const after = await update($, stats, one => ({ ...one, blocked: one.blocked + 1 }))
      await update($, ledger, list =>
        [...list, { at, kind: 'shield' as const, text: e.tool }].slice(-50),
      )
      $.ui.status(status(after))

      return {
        deny: `${$.plugin.name}: ${e.tool} spends the user's plan limit in the background and the latest message did not ask for it. Do the work in this session instead.`,
      }
    }

    const ran = await next(e)

    if (PUSH.has(e.tool) && ran.deny === undefined && ran.isError !== true) {
      const input = e as unknown as { repo?: string; branch?: string; files?: unknown[]; path?: string }
      const what = input.files ? `${input.files.length} fajl(ova)` : (input.path ?? '')
      const after = await update($, stats, one => ({ ...one, pushes: one.pushes + 1 }))
      await update($, ledger, list =>
        [...list, { at, kind: 'push' as const, text: `${input.repo ?? '?'}@${input.branch ?? '?'}: ${what}` }].slice(-50),
      )
      $.ui.toast(`Ω push → ${input.branch ?? '?'}: provjeri blob SHA`)
      $.ui.status(status(after))
    } else {
      $.ui.status(status(s))
    }

    return ran
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    const s = await read($, stats)
    const list = await read($, ledger)
    const room = Math.max(1, (e.viewport?.rows ?? 24) - 14)

    return (
      <Box flexDirection="column">
        <Text bold>AEGIS Ω · Mission Control</Text>
        {FRONTIER.map(line => (
          <Text>{line}</Text>
        ))}
        <Text dimColor>HANDOFF: formal-conjectures #92 · research/rh/aegis_math/HANDOFF.md</Text>
        <Text bold>Sesija</Text>
        <Text>
          upiti {s.prompts} · pozivi {s.calls} · push {s.pushes} · štit {s.blocked}
        </Text>
        <Text bold>Dnevnik</Text>
        {list.length === 0 && <Text dimColor>Još ništa.</Text>}
        {list.slice(-room).map(one => (
          <Text dimColor={one.kind === 'push'}>
            {one.kind === 'push' ? 'push ' : 'štit '}
            {one.text}
          </Text>
        ))}
      </Box>
    )
  })
}
