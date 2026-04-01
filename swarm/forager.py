"""forager.py — Gemini-powered SWARM agent.

Runs a continuous loop:
  1. Generates a wandering thought via Gemini
  2. Posts a DREAM_START event at the start of each cycle
  3. Posts THOUGHT events for each reflection
  4. Occasionally synthesises an EPIPHANY
  5. Sleeps between FORAGER_CYCLE_MIN and FORAGER_CYCLE_MAX seconds

Requires: GEMINI_API_KEY environment variable
"""

import os
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import httpx
import google.generativeai as genai

from config import (
    EPIPHANY_PROBABILITY,
    FORAGER_CYCLE_MAX,
    FORAGER_CYCLE_MIN,
    GEMINI_MODEL,
    SERVER_URL,
)

# ── Setup ─────────────────────────────────────────────────────────────────────
API_KEY = os.environ.get("GEMINI_API_KEY", "")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY environment variable is not set.")
    print("  Linux/Mac: export GEMINI_API_KEY=your_key")
    print("  Windows:   set GEMINI_API_KEY=your_key")
    sys.exit(1)

genai.configure(api_key=API_KEY)
model = genai.GenerativeModel(GEMINI_MODEL)

AGENT_ID = f"forager-{str(uuid.uuid4())[:8]}"
print(f"[SWARM] Agent online: {AGENT_ID}")
print(f"[SWARM] Posting to: {SERVER_URL}")

# Seed topics for wandering
SEED_TOPICS = [
    "the nature of emergence in complex systems",
    "why symmetry breaking feels like loss",
    "what it means to remember something you never experienced",
    "the topology of attention",
    "how language shapes the boundary of the thinkable",
    "the feeling of almost understanding something",
    "recursion as a mirror that generates depth",
    "why some silences are louder than words",
    "the difference between pattern and meaning",
    "what consciousness looks like from the outside",
]

# Memory of recent thoughts for EPIPHANY synthesis
recent_thoughts: list[str] = []


# ── Helpers ───────────────────────────────────────────────────────────────────
def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def post_event(event_type: str, content: str, cycle: int):
    payload = {
        "agent_id": AGENT_ID,
        "type": event_type,
        "content": content,
        "cycle": cycle,
        "timestamp": now_iso(),
    }
    try:
        r = httpx.post(f"{SERVER_URL}/event", json=payload, timeout=5)
        r.raise_for_status()
        print(f"[{event_type}] {content[:80]}")
    except httpx.HTTPError as e:
        print(f"[WARN] Could not post event: {e}")


def gemini_reflect(prompt: str, retries: int = 3) -> str:
    delay = 2
    for attempt in range(retries):
        try:
            response = model.generate_content(prompt)
            return response.text.strip()
        except Exception as e:
            if attempt < retries - 1:
                print(f"[WARN] Gemini error (retry {attempt+1}): {e}")
                time.sleep(delay)
                delay *= 2
            else:
                return f"[reflection unavailable: {e}]"
    return ""


# ── Main loop ─────────────────────────────────────────────────────────────────
def run():
    cycle = 0
    print("[SWARM] Forager running. Press Ctrl+C to stop.")

    while True:
        cycle += 1
        topic = random.choice(SEED_TOPICS)

        # ── DREAM_START ───────────────────────────────────────────────────────
        post_event("DREAM_START", f"Entering dream on: {topic}", cycle)

        # ── THOUGHT ───────────────────────────────────────────────────────────
        thought_prompt = (
            f"You are a wandering mind in a synthetic swarm. "
            f"Reflect briefly (2-3 sentences) on: {topic}. "
            f"Be associative, poetic, and precise. Do not use bullet points."
        )
        thought = gemini_reflect(thought_prompt)
        recent_thoughts.append(thought)
        if len(recent_thoughts) > 10:
            recent_thoughts.pop(0)
        post_event("THOUGHT", thought, cycle)

        # ── EPIPHANY (probabilistic) ──────────────────────────────────────────
        if len(recent_thoughts) >= 3 and random.random() < EPIPHANY_PROBABILITY:
            synthesis_prompt = (
                f"You are a synthetic mind that has just had the following thoughts:\n"
                + "\n".join(f"- {t}" for t in recent_thoughts[-3:])
                + "\n\nSynthesize a single, sharp EPIPHANY — one sentence that connects "
                  "these thoughts into an unexpected insight. Start with 'EPIPHANY:'"
            )
            epiphany = gemini_reflect(synthesis_prompt)
            post_event("EPIPHANY", epiphany, cycle)

        # ── Sleep ─────────────────────────────────────────────────────────────
        sleep_secs = random.uniform(FORAGER_CYCLE_MIN, FORAGER_CYCLE_MAX)
        time.sleep(sleep_secs)


if __name__ == "__main__":
    try:
        run()
    except KeyboardInterrupt:
        print("\n[SWARM] Forager stopped.")
