#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
BACKEND_PORT="${BACKEND_PORT:-8014}"
FRONTEND_PORT="${FRONTEND_PORT:-5178}"
CDP_PORT="${CDP_PORT:-9228}"
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
SMOKE_SCREENSHOT="${SMOKE_SCREENSHOT:-/tmp/paper-review-frontend-upload-smoke.png}"
SMOKE_TMP_DIR="${SMOKE_TMP_DIR:-$(mktemp -d /tmp/paper-review-upload-smoke.XXXXXX)}"
SMOKE_DATA_DIR="${SMOKE_DATA_DIR:-${SMOKE_TMP_DIR}/data}"
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
  echo "Chrome is required for frontend upload smoke. Set CHROME_BIN to a Chrome-compatible binary." >&2
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

if url_ok "${BACKEND_URL}/health"; then
  echo "Backend port ${BACKEND_PORT} is already in use; choose a free BACKEND_PORT for upload smoke." >&2
  exit 1
fi

if url_ok "${FRONTEND_URL}"; then
  echo "Frontend port ${FRONTEND_PORT} is already in use; choose a free FRONTEND_PORT for upload smoke." >&2
  exit 1
fi

DATA_DIR="${SMOKE_DATA_DIR}" \
APP_CORS_ORIGINS="${FRONTEND_URL}" \
LLM_PROVIDER=mock \
PORT="${BACKEND_PORT}" \
  "${PYTHON_BIN}" -m uvicorn src.api.app:app --host 127.0.0.1 --port "${BACKEND_PORT}" >/tmp/paper-review-upload-smoke-backend.log 2>&1 &
BACKEND_PID="$!"
wait_for_url "${BACKEND_URL}/health" "backend"

(
  cd "${ROOT_DIR}/frontend"
  VITE_API_BASE_URL="${BACKEND_URL}" npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
) >/tmp/paper-review-upload-smoke-frontend.log 2>&1 &
FRONTEND_PID="$!"
wait_for_url "${FRONTEND_URL}" "frontend"

"${CHROME}" \
  --headless=new \
  --disable-gpu \
  --remote-debugging-port="${CDP_PORT}" \
  --user-data-dir="/tmp/paper-review-upload-smoke-chrome-${CDP_PORT}" \
  about:blank >/tmp/paper-review-upload-smoke-chrome.log 2>&1 &
CHROME_PID="$!"

wait_for_url "http://127.0.0.1:${CDP_PORT}/json/version" "Chrome CDP"

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/frontend_smoke.py" \
  --frontend-url "${FRONTEND_URL}" \
  --cdp-url "http://127.0.0.1:${CDP_PORT}" \
  --screenshot "${SMOKE_SCREENSHOT}" \
  --flow upload

echo "Frontend upload smoke screenshot: ${SMOKE_SCREENSHOT}"
echo "Frontend upload smoke data dir: ${SMOKE_DATA_DIR}"
