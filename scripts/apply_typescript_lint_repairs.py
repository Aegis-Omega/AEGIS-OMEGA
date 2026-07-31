#!/usr/bin/env python3
"""Apply the bounded TypeScript lint repair set for PR #248.

This script is intentionally temporary. Every replacement asserts the expected
preimage count and exits before writing the affected file if the preimage does
not match the admitted source state.
"""

from pathlib import Path
import textwrap


def replace_exact(path: str, old: str, new: str, expected: int = 1) -> None:
    target = Path(path)
    text = target.read_text(encoding="utf-8")
    count = text.count(old)
    if count != expected:
        raise SystemExit(
            f"{path}: expected {expected} matches, found {count}: {old!r}"
        )
    target.write_text(text.replace(old, new), encoding="utf-8")


replace_exact(
    "sovereign-omega-v2/src/api/claude-client.ts",
    "            input_tokens: (event as any).usage?.input_tokens ?? 0,",
    """            input_tokens:
              'input_tokens' in event.usage && typeof event.usage.input_tokens === 'number'
                ? event.usage.input_tokens
                : 0,""",
)

managed_path = Path("sovereign-omega-v2/src/api/managed-agent-client.ts")
managed = managed_path.read_text(encoding="utf-8")

config_marker = """export interface ManagedAgentClientConfig {
  readonly apiKey?: string
  readonly agentId?: string  // pre-existing agent to reuse
}
"""
wire_types = """export interface ManagedAgentClientConfig {
  readonly apiKey?: string
  readonly agentId?: string  // pre-existing agent to reuse
}

interface ManagedAgentWireRecord {
  readonly id: string
}

interface ManagedSessionWireRecord {
  readonly id: string
  readonly agent_id?: string
  readonly status?: AgentSession['status']
  readonly created_at?: string
}

interface ManagedSessionWireEvent {
  readonly type?: SessionEvent['type']
  readonly content?: unknown
}

type ManagedSessionWireStream = AsyncIterable<ManagedSessionWireEvent>

interface ManagedAnthropicExtension {
  readonly beta: {
    readonly agents: {
      create(input: unknown): Promise<ManagedAgentWireRecord>
    }
    readonly sessions: {
      create(input: unknown): Promise<ManagedSessionWireRecord>
      stream(sessionId: string): ManagedSessionWireStream | null | Promise<ManagedSessionWireStream | null>
      createEvent(sessionId: string, event: unknown): Promise<unknown>
      retrieve(sessionId: string): Promise<ManagedSessionWireRecord>
    }
  }
}
"""
if managed.count(config_marker) != 1:
    raise SystemExit("managed-agent-client.ts: config marker mismatch")
managed = managed.replace(config_marker, wire_types, 1)

replacements = {
    "(this._client as any).beta?.agents?.create": "this.managedClient().beta.agents.create",
    "(this._client as any).beta?.sessions?.create": "this.managedClient().beta.sessions.create",
    "(this._client as any).beta?.sessions?.stream": "this.managedClient().beta.sessions.stream",
    "(this._client as any).beta?.sessions?.createEvent": "this.managedClient().beta.sessions.createEvent",
    "(this._client as any).beta?.sessions?.retrieve": "this.managedClient().beta.sessions.retrieve",
}
replaced_casts = 0
for old, new in replacements.items():
    count = managed.count(old)
    replaced_casts += count
    managed = managed.replace(old, new)
if replaced_casts != 6 or "as any" in managed:
    raise SystemExit(
        f"managed-agent-client.ts: expected 6 any-cast replacements, got {replaced_casts}"
    )

method_marker = "\n  /** Create or retrieve the AEGIS constitutional agent. Returns agent_id. */"
helper = """
  private managedClient(): ManagedAnthropicExtension {
    return this._client as unknown as ManagedAnthropicExtension
  }

  /** Create or retrieve the AEGIS constitutional agent. Returns agent_id. */"""
if managed.count(method_marker) != 1:
    raise SystemExit("managed-agent-client.ts: method marker mismatch")
managed = managed.replace(method_marker, helper, 1)

cause_line = "        `Ensure your API key has Managed Agents access.`"
if managed.count(cause_line) != 1:
    raise SystemExit("managed-agent-client.ts: cause line mismatch")
managed = managed.replace(
    cause_line,
    """        `Ensure your API key has Managed Agents access.`,
        { cause: err },""",
    1,
)
managed_path.write_text(managed, encoding="utf-8")

ralph_path = Path("sovereign-omega-v2/src/core/ralph-loop.ts")
ralph = ralph_path.read_text(encoding="utf-8")
ralph_changes = [
    (
        "    const loop = this\n",
        "    const cycleNumber = this._cycleNumber\n    const targetScale = this.targetScale\n",
    ),
    ("      harmonize(gateResult) {", "      harmonize: (gateResult) => {"),
    ("          cycle_number: loop._cycleNumber,", "          cycle_number: cycleNumber,"),
    ("          target_scale: loop.targetScale,", "          target_scale: targetScale,"),
    ("        loop.cycles.push(cycle)", "        this.cycles.push(cycle)"),
]
for old, new in ralph_changes:
    if ralph.count(old) != 1:
        raise SystemExit(f"ralph-loop.ts marker mismatch: {old!r}")
    ralph = ralph.replace(old, new, 1)
ralph_path.write_text(ralph, encoding="utf-8")

replace_exact(
    "sovereign-omega-v2/src/scale-os/control-plane.ts",
    "const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@/+\\-]{1,255}$/",
    "const IDENTIFIER_PATTERN = /^[A-Za-z0-9][A-Za-z0-9._:@/+-]{1,255}$/",
)

replace_exact(
    "sovereign-omega-v2/src/skill-harness/scanner/codebase-scanner.ts",
    "      let content = ''",
    "      let content: string",
)
