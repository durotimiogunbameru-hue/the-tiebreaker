#!/usr/bin/env bash
# The Tiebreaker — one-command launcher (macOS / Linux)
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "The Tiebreaker - setup + launch"

# 1. Virtual environment
if [ ! -d "$root/.venv" ]; then
  echo "Creating virtual environment..."
  python3 -m venv "$root/.venv"
fi
py="$root/.venv/bin/python"

# 2. Dependencies
echo "Installing dependencies..."
"$py" -m pip install --quiet --upgrade pip
"$py" -m pip install --quiet -r "$root/requirements.txt"

# 3. Load .env if present
if [ -f "$root/.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$root/.env"
  set +a
  echo "Loaded .env"
fi

# 4. Launch
if [ -n "${ANTHROPIC_API_KEY:-}" ]; then
  echo "ANTHROPIC_API_KEY detected - running with real Claude analysis."
else
  echo "No API key - running in deterministic demo (mock) mode."
fi
echo "Open http://localhost:8000 in your browser."

cd "$root/api"
exec "$py" -m uvicorn index:app --host 0.0.0.0 --port 8000 --reload
