#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_PID=""
FRONTEND_PID=""

cleanup() {
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

"${ROOT_DIR}/scripts/dev-backend.sh" &
BACKEND_PID="$!"

"${ROOT_DIR}/scripts/dev-frontend.sh" &
FRONTEND_PID="$!"

echo "Backend:  http://127.0.0.1:${PORT:-8000}"
echo "Frontend: http://127.0.0.1:5173"
wait "${BACKEND_PID}" "${FRONTEND_PID}"
