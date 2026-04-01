# config.py — central configuration for SWARM

PORT = 8000
HOST = "0.0.0.0"

# Rolling event buffer size (in-memory)
MAX_EVENTS = 200

# Gemini model
GEMINI_MODEL = "gemini-1.5-flash"

# Forager timing (seconds)
FORAGER_CYCLE_MIN = 5
FORAGER_CYCLE_MAX = 15

# Probability of EPIPHANY event per cycle (0.0–1.0)
EPIPHANY_PROBABILITY = 0.12

# Server URL (forager posts here)
SERVER_URL = f"http://localhost:{PORT}"
