#!/bin/bash
set -e

# ── Ensure common tool locations are on PATH ──────────────────────────────────
export PATH="/usr/local/bin:/usr/bin:/bin:/usr/local/sbin:/usr/sbin:/sbin:$PATH"

# Also source nvm if present
[ -s "$HOME/.nvm/nvm.sh" ] && source "$HOME/.nvm/nvm.sh"
[ -s "$HOME/.profile" ] && source "$HOME/.profile"

# ── Resolve project root (directory containing this script) ───────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

echo "=== Hospital Scraper Startup ==="

# ── Check dependencies ────────────────────────────────────────────────────────
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 is not installed or not on PATH"
  exit 1
fi

if ! command -v node &>/dev/null; then
  echo "ERROR: node is not installed or not on PATH"
  echo "Install Node.js from https://nodejs.org (v18+ recommended)"
  exit 1
fi

if ! command -v npm &>/dev/null; then
  echo "ERROR: npm is not installed or not on PATH"
  exit 1
fi

echo "  python3: $(python3 --version)"
echo "  node:    $(node --version)"
echo "  npm:     $(npm --version)"
echo ""

# ── Create folder structure if it doesn't exist ───────────────────────────────
mkdir -p backend frontend outputs

# ── Backend: install Python deps ──────────────────────────────────────────────
echo "=== Setting up backend ==="
if [ -f "backend/requirements.txt" ]; then
  pip3 install -r backend/requirements.txt --break-system-packages -q
elif [ -f "requirements.txt" ]; then
  pip3 install -r requirements.txt --break-system-packages -q
fi

# ── Frontend: install npm deps ────────────────────────────────────────────────
echo "=== Setting up frontend ==="
FRONTEND_DIR="frontend"
if [ ! -f "$FRONTEND_DIR/package.json" ] && [ -f "package.json" ]; then
  # Flat layout fallback — run npm install from root
  FRONTEND_DIR="."
fi

(cd "$FRONTEND_DIR" && npm install --silent)

# ── Start backend ─────────────────────────────────────────────────────────────
echo ""
echo "=== Starting FastAPI backend on http://localhost:8000 ==="
BACKEND_ENTRY="backend/main.py"
if [ ! -f "$BACKEND_ENTRY" ] && [ -f "main.py" ]; then
  BACKEND_ENTRY="main.py"
fi

BACKEND_DIR="$(dirname "$BACKEND_ENTRY")"
BACKEND_MODULE="$(basename "$BACKEND_ENTRY" .py)"
(cd "$BACKEND_DIR" && python3 -m uvicorn "${BACKEND_MODULE}:app" \
  --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID"

# ── Start frontend ────────────────────────────────────────────────────────────
echo "=== Starting Vite frontend on http://localhost:5173 ==="
(cd "$FRONTEND_DIR" && npm run dev -- --host) &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID"

echo ""
echo "✓ Both servers running."
echo "  Frontend → http://localhost:5173"
echo "  Backend  → http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop both servers."

# ── Cleanup on exit ───────────────────────────────────────────────────────────
trap "echo ''; echo 'Stopping servers...'; kill $BACKEND_PID $FRONTEND_PID 2>/dev/null; exit 0" SIGINT SIGTERM

wait