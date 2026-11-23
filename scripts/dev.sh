#!/usr/bin/env bash
# Starts everything for local use in one terminal: voice (if installed), backend and app.
# Each line is prefixed with its service; Ctrl+C stops all of them.
#
#   make dev              # voice + backend + desktop app
#   make dev NO_VOICE=1   # skip the voice service (frees ~3 GB of VRAM)
#   make dev WEB=1        # serve the UI for a browser instead of opening the window
set -u
cd "$(dirname "$0")/.."

pids=()

# Each service runs in its own session/process group so stopping it also stops the
# processes it spawns (npm -> electron-vite -> electron, for example).
run() {
  local name=$1 dir=$2 command=$3
  setsid bash -c "cd '$dir' && $command 2>&1 | sed -u 's/^/[$name] /'" &
  pids+=("$!")
}

stop_all() {
  trap - INT TERM EXIT
  echo "[dev] stopping..."
  for pid in "${pids[@]}"; do
    kill -TERM -- "-$pid" 2>/dev/null
  done
  wait 2>/dev/null
  echo "[dev] stopped"
}
trap stop_all INT TERM EXIT

if [[ -n "${NO_VOICE:-}" ]]; then
  echo "[dev] voice disabled (NO_VOICE); replies will be text-only"
elif [[ -x apps/tts/.venv/bin/python ]]; then
  run "voz" apps/tts ".venv/bin/python -m tts_service.server"
else
  echo "[dev] voice not installed (make setup-tts); replies will be text-only"
fi
run "backend" apps/backend ".venv/bin/python -m app.main"
if [[ -n "${WEB:-}" ]]; then
  # Under WSL a Windows browser plays the voice natively (WSLg audio stutters).
  run "web" apps/desktop "npm run web"
  echo "[dev] open http://127.0.0.1:5173 in your browser"
else
  run "app" apps/desktop "npm run dev"
fi

echo "[dev] running: Ctrl+C to stop everything"
wait
