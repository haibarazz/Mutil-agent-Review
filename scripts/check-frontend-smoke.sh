#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-5174}"
CDP_PORT="${CDP_PORT:-9224}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
SMOKE_SCREENSHOT="${SMOKE_SCREENSHOT:-/tmp/paper-review-frontend-smoke.png}"
BACKEND_PID=""
FRONTEND_PID=""
CHROME_PID=""

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

if [[ -n "${CHROME_BIN:-}" ]]; then
  CHROME="${CHROME_BIN}"
elif [[ -x "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" ]]; then
  CHROME="/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"
else
  CHROME="$(command -v google-chrome || command -v chromium || true)"
fi

if [[ -z "${CHROME}" ]]; then
  echo "Chrome is required for frontend smoke. Set CHROME_BIN to a Chrome-compatible binary." >&2
  exit 1
fi

cleanup() {
  if [[ -n "${CHROME_PID}" ]]; then
    kill "${CHROME_PID}" 2>/dev/null || true
  fi
  if [[ -n "${FRONTEND_PID}" ]]; then
    kill "${FRONTEND_PID}" 2>/dev/null || true
  fi
  if [[ -n "${BACKEND_PID}" ]]; then
    kill "${BACKEND_PID}" 2>/dev/null || true
  fi
}

trap cleanup EXIT INT TERM

url_ok() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import sys
from urllib.request import urlopen

try:
    with urlopen(sys.argv[1], timeout=1.5) as response:
        raise SystemExit(0 if response.status < 500 else 1)
except Exception:
    raise SystemExit(1)
PY
}

wait_for_url() {
  local url="$1"
  local label="$2"
  for _ in {1..60}; do
    if url_ok "${url}"; then
      return 0
    fi
    sleep 0.5
  done
  echo "Timed out waiting for ${label}: ${url}" >&2
  exit 1
}

cd "${ROOT_DIR}"

if ! url_ok "${BACKEND_URL}/health"; then
  APP_CORS_ORIGINS="${APP_CORS_ORIGINS:-${FRONTEND_URL}}" \
  PORT="${BACKEND_PORT}" \
    "${PYTHON_BIN}" -m uvicorn src.api.app:app --host 127.0.0.1 --port "${BACKEND_PORT}" >/tmp/paper-review-smoke-backend.log 2>&1 &
  BACKEND_PID="$!"
  wait_for_url "${BACKEND_URL}/health" "backend"
fi

if ! url_ok "${FRONTEND_URL}"; then
  (
    cd "${ROOT_DIR}/frontend"
    if [[ "${BACKEND_PORT}" == "8000" ]]; then
      npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
    else
      VITE_API_BASE_URL="${BACKEND_URL}" npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
    fi
  ) >/tmp/paper-review-smoke-frontend.log 2>&1 &
  FRONTEND_PID="$!"
  wait_for_url "${FRONTEND_URL}" "frontend"
fi

"${CHROME}" \
  --headless=new \
  --disable-gpu \
  --remote-debugging-port="${CDP_PORT}" \
  --user-data-dir="/tmp/paper-review-smoke-chrome-${CDP_PORT}" \
  about:blank >/tmp/paper-review-smoke-chrome.log 2>&1 &
CHROME_PID="$!"

wait_for_url "http://127.0.0.1:${CDP_PORT}/json/version" "Chrome CDP"

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/frontend_smoke.py" \
  --frontend-url "${FRONTEND_URL}" \
  --cdp-url "http://127.0.0.1:${CDP_PORT}" \
  --screenshot "${SMOKE_SCREENSHOT}"

echo "Frontend smoke screenshot: ${SMOKE_SCREENSHOT}"
