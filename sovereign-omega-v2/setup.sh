#!/usr/bin/env bash
# ============================================================
# SOVEREIGN OMEGA — Full Environment Setup
# Installs and configures both layers (TypeScript + Python)
# plus the orchestration stack (Paperclip, skills, MCP).
# Run once after cloning the repository.
# ============================================================
set -euo pipefail

echo "=== SOVEREIGN OMEGA ENVIRONMENT SETUP ==="
echo ""

# ── Prerequisites Check ─────────────────────────────────────
check_cmd() { command -v "$1" >/dev/null 2>&1 || { echo "ERROR: $1 not found. Install it first."; exit 1; }; }
check_cmd node
check_cmd npm
check_cmd python3
check_cmd pip3
check_cmd git

NODE_VER=$(node -e "process.exit(parseInt(process.version.slice(1)) < 20 ? 1 : 0)" 2>&1 && echo "ok" || echo "fail")
if [ "$NODE_VER" = "fail" ]; then
  echo "ERROR: Node.js 20+ required. Current: $(node --version)"
  exit 1
fi

echo "[1/7] Installing TypeScript dependencies..."
npm install

echo "[2/7] Installing Python dependencies..."
pip3 install --break-system-packages -r requirements.txt 2>/dev/null || \
pip3 install -r requirements.txt

echo "[3/7] Setting up environment configuration..."
if [ ! -f ".env" ]; then
  cp .env.example .env
  echo "  Created .env from .env.example — fill in required values before running"
else
  echo "  .env already exists — skipping"
fi

echo "[4/7] Verifying frozen constitutional files..."
node scripts/verify-hashes.mjs || true  # non-fatal if files not present

echo "[5/7] Running TypeScript smoke tests (Gates 1-3)..."
npm run test -- test/unit/jcs.test.ts test/unit/immutable.test.ts --reporter=verbose 2>&1 | tail -5

echo "[6/7] Running Python smoke validation..."
cd python && python3 tests/stress_test.py --quick 2>&1 | tail -10
cd ..

echo "[7/7] Installing Claude Code orchestration stack..."
if command -v claude >/dev/null 2>&1; then
  echo "  Claude Code detected — installing superpowers..."
  claude --skip-permissions /plugin marketplace add obra/superpowers 2>/dev/null || \
    echo "  (Install manually: /plugin marketplace add obra/superpowers)"

  echo "  Installing antigravity skills library..."
  npx antigravity-awesome-skills --claude 2>/dev/null || \
    echo "  (Install manually: npx antigravity-awesome-skills --claude)"
else
  echo "  Claude Code not detected — skip orchestration setup"
  echo "  Install Claude Code, then run:"
  echo "    /plugin marketplace add obra/superpowers"
  echo "    npx antigravity-awesome-skills --claude"
fi

echo ""
echo "=== SETUP COMPLETE ==="
echo ""
echo "Next steps:"
echo "  TypeScript: npm run test:gates  (run all 8 gates)"
echo "  Python:     python python/tests/stress_test.py --quick"
echo "  Deploy:     vercel --prod  (only after Gate 8 and P1 pass)"
echo ""
echo "Paperclip (multi-agent orchestration):"
echo "  npm install -g paperclipai && paperclipai onboard --yes --bind lan"
