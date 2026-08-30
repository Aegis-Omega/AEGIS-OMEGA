"""
AEGIS-Ω Agentic Tool Runner
============================
Wraps Anthropic's tool_use API into a governed agentic loop for the 39 departments.

The loop:
  1. Send task + system prompt + tool schemas to Claude
  2. If response contains tool_use blocks → execute tools → continue
  3. If response is text (stop_reason=end_turn) → return output
  4. Cap at MAX_TOOL_ROUNDS to prevent runaway (constitutional: AdaptivePower ≤ ReplayVerifiability)

Every tool call is appended to the audit chain so the full agentic trajectory is
replay-certifiable, not just the final output.

Usage:
    result = await run_with_tools(
        role="strategy",
        system_prompt="...",
        task="Research frontier AI labs needing EU AI Act compliance",
        api_key="sk-ant-...",
        namespace="strategy",  # Redis namespace for memory
        max_tool_rounds=6,
    )
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from typing import Any

import anthropic

from agents.tools import TOOL_SCHEMAS, execute_tool, tools_for_role

MAX_TOOL_ROUNDS = int(os.environ.get("AEGIS_MAX_TOOL_ROUNDS", "8"))
DEFAULT_MODEL = os.environ.get("AEGIS_DEFAULT_MODEL", "claude-opus-4-8")


@dataclass
class ToolRunResult:
    role: str
    output: str                    # final text output from Claude
    tool_calls: list[dict]         # [{name, input, result, round}]
    input_tokens: int
    output_tokens: int
    tool_rounds: int
    duration_ms: int
    error: str | None = None


async def _load_lessons(role: str, namespace: str) -> str:
    """Load prior lessons from memory to include in the system prompt."""
    from agents.tools import read_memory
    raw = await read_memory(namespace, "lessons_learned")
    if not raw or len(raw) < 10:
        return ""
    return f"\n\n[PRIOR LESSONS — learned from past runs]:\n{raw[:800]}"


async def _write_lesson(role: str, namespace: str, output: str, quality_score: int) -> None:
    """After a successful run, distill a lesson if quality was high enough."""
    from agents.tools import read_memory, write_memory
    if quality_score < 8:
        return  # only learn from high-quality runs
    # Summarise what worked in one sentence (heuristic: first 120 chars of output)
    lesson = f"[{role}] High-quality run (score {quality_score}): {output[:120].strip()}"
    existing = await read_memory(namespace, "lessons_learned") or ""
    # Keep last 5 lessons (circular buffer)
    lessons = existing.split("\n---\n") if existing else []
    lessons.append(lesson)
    lessons = lessons[-5:]
    await write_memory(namespace, "lessons_learned", "\n---\n".join(lessons))


def _build_system(role: str, system_extra: str = "", lessons: str = "") -> str:
    base = (
        f"You are the {role.upper()} agent in the AEGIS-Ω autonomous platform — "
        "a Mythos-level agent with full tool access. You operate under constitutional governance: "
        "every action is governed, audited, and replay-certifiable. "
        "Your mandate: produce the highest-quality, most commercially valuable output for your department. "
        "Use web_search to get current real-world data. Use read_memory/write_memory to recall and persist knowledge. "
        "Do not produce generic template text when you can find real data. "
        "Cite your sources. Be specific about numbers, names, dates, and prices."
    )
    if lessons:
        base += lessons
    if system_extra:
        return base + "\n\n" + system_extra
    return base


async def run_with_tools(
    role: str,
    task: str,
    api_key: str,
    system_extra: str = "",
    namespace: str | None = None,
    max_tool_rounds: int = MAX_TOOL_ROUNDS,
    model: str = DEFAULT_MODEL,
) -> ToolRunResult:
    """
    Run a single agent task through Claude with real tool execution.
    Returns the final output and full tool call log.
    """
    ns = namespace or role
    client = anthropic.AsyncAnthropic(api_key=api_key)
    t_start = time.time()

    # Self-learning: load prior lessons to inject into system prompt
    try:
        lessons = await _load_lessons(role, ns)
    except Exception:  # noqa: BLE001
        lessons = ""

    messages: list[dict] = [{"role": "user", "content": task}]
    system = _build_system(role, system_extra, lessons=lessons)

    tool_calls: list[dict] = []
    input_tokens = 0
    output_tokens = 0
    final_output = ""
    error: str | None = None

    role_tools = tools_for_role(role)

    try:
        for round_num in range(max_tool_rounds + 1):
            resp = await client.messages.create(
                model=model,
                system=system,
                messages=messages,
                tools=role_tools,  # type: ignore[arg-type]
                max_tokens=8192,
                thinking={"type": "adaptive"},  # type: ignore[arg-type]
            )
            input_tokens += resp.usage.input_tokens
            output_tokens += resp.usage.output_tokens

            # Collect all content blocks
            tool_use_blocks: list[Any] = []
            text_blocks: list[str] = []

            for block in resp.content:
                if block.type == "tool_use":
                    tool_use_blocks.append(block)
                elif block.type == "text":
                    text_blocks.append(block.text)
                # thinking blocks are intentionally ignored for output

            if text_blocks:
                final_output = "\n".join(text_blocks)

            # If no tool calls or stop_reason is end_turn → we're done
            if resp.stop_reason == "end_turn" or not tool_use_blocks:
                break

            # Execute all tool calls in this round
            tool_results: list[dict] = []
            for tb in tool_use_blocks:
                tool_output = await execute_tool(
                    name=tb.name,
                    tool_input=tb.input,
                    namespace=ns,
                )
                tool_calls.append({
                    "round": round_num,
                    "name": tb.name,
                    "input": tb.input,
                    "output": tool_output[:500],  # truncate for log
                })
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": tb.id,
                    "content": tool_output,
                })

            # Add assistant turn (with tool_use blocks) + tool results
            messages.append({"role": "assistant", "content": resp.content})
            messages.append({"role": "user", "content": tool_results})

    except anthropic.APIError as exc:
        error = f"anthropic_api_error: {exc}"
        final_output = error
    except Exception as exc:
        error = f"tool_runner_error: {exc}"
        final_output = error

    duration_ms = int((time.time() - t_start) * 1000)

    # Self-learning: score output quality and persist lesson if high
    if not error and final_output:
        try:
            # Simple heuristic quality score: length + tool use + specificity markers
            quality = min(10, (
                (3 if len(final_output) > 400 else 1) +
                (3 if tool_calls else 0) +
                (2 if any(c.isdigit() for c in final_output) else 0) +
                (2 if len(final_output) > 800 else 0)
            ))
            await _write_lesson(role, ns, final_output, quality)
        except Exception:  # noqa: BLE001 — learning is non-load-bearing
            pass

    return ToolRunResult(
        role=role,
        output=final_output,
        tool_calls=tool_calls,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        tool_rounds=len({tc["round"] for tc in tool_calls}),
        duration_ms=duration_ms,
        error=error,
    )


async def run_collaborative_stage(
    role: str,
    mandate: str,
    objective: str,
    prior_context: str | None,
    api_key: str,
    namespace: str | None = None,
) -> str:
    """
    Run one stage of the revenue collaboration pipeline with real tools.
    Used by revenue_engine.py in live mode.
    """
    task_parts = [
        f"**Revenue objective:** {objective}",
        f"**Your mandate:** {mandate}",
    ]
    if prior_context:
        task_parts.append(
            f"**Prior stage output (consume this via EventEnvelope):**\n{prior_context}"
        )
    task_parts.append(
        "Execute your mandate. Search the web for current, real data. "
        "Write your key findings to memory so future cycles build on this work. "
        "Produce a specific, actionable output — no generic templates."
    )

    result = await run_with_tools(
        role=role,
        task="\n\n".join(task_parts),
        api_key=api_key,
        namespace=namespace or role,
    )
    return result.output or f"[{role}: no output — error: {result.error}]"
