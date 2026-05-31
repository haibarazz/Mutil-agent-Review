#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
BACKEND_PORT_IS_DEFAULT=0
FRONTEND_PORT_IS_DEFAULT=0
CDP_PORT_IS_DEFAULT=0
if [[ -z "${BACKEND_PORT+x}" ]]; then
  BACKEND_PORT="8017"
  BACKEND_PORT_IS_DEFAULT=1
fi
if [[ -z "${FRONTEND_PORT+x}" ]]; then
  FRONTEND_PORT="5181"
  FRONTEND_PORT_IS_DEFAULT=1
fi
if [[ -z "${CDP_PORT+x}" ]]; then
  CDP_PORT="9231"
  CDP_PORT_IS_DEFAULT=1
fi
BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
SMOKE_SCREENSHOT="${SMOKE_SCREENSHOT:-/tmp/paper-review-frontend-filter-smoke.png}"
SMOKE_TMP_DIR="${SMOKE_TMP_DIR:-$(mktemp -d /tmp/paper-review-filter-smoke.XXXXXX)}"
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
  echo "Chrome is required for frontend filter smoke. Set CHROME_BIN to a Chrome-compatible binary." >&2
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

port_in_use() {
  "${PYTHON_BIN}" - "$1" <<'PY'
import socket
import sys

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.settimeout(0.5)
    raise SystemExit(0 if sock.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
PY
}

pick_free_port() {
  "${PYTHON_BIN}" - <<'PY'
import socket

with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
    sock.bind(("127.0.0.1", 0))
    print(sock.getsockname()[1])
PY
}

if port_in_use "${BACKEND_PORT}"; then
  if [[ "${BACKEND_PORT_IS_DEFAULT}" == "1" ]]; then
    OLD_BACKEND_PORT="${BACKEND_PORT}"
    BACKEND_PORT="$(pick_free_port)"
    BACKEND_URL="http://127.0.0.1:${BACKEND_PORT}"
    echo "Backend port ${OLD_BACKEND_PORT} is already in use; using ${BACKEND_PORT} for filter smoke."
  else
    echo "Backend port ${BACKEND_PORT} is already in use; choose a free BACKEND_PORT for filter smoke." >&2
    exit 1
  fi
fi

if port_in_use "${FRONTEND_PORT}"; then
  if [[ "${FRONTEND_PORT_IS_DEFAULT}" == "1" ]]; then
    OLD_FRONTEND_PORT="${FRONTEND_PORT}"
    FRONTEND_PORT="$(pick_free_port)"
    FRONTEND_URL="http://127.0.0.1:${FRONTEND_PORT}"
    echo "Frontend port ${OLD_FRONTEND_PORT} is already in use; using ${FRONTEND_PORT} for filter smoke."
  else
    echo "Frontend port ${FRONTEND_PORT} is already in use; choose a free FRONTEND_PORT for filter smoke." >&2
    exit 1
  fi
fi

if port_in_use "${CDP_PORT}"; then
  if [[ "${CDP_PORT_IS_DEFAULT}" == "1" ]]; then
    OLD_CDP_PORT="${CDP_PORT}"
    CDP_PORT="$(pick_free_port)"
    echo "Chrome CDP port ${OLD_CDP_PORT} is already in use; using ${CDP_PORT} for filter smoke."
  else
    echo "Chrome CDP port ${CDP_PORT} is already in use; choose a free CDP_PORT for filter smoke." >&2
    exit 1
  fi
fi

cd "${ROOT_DIR}"

DATA_DIR="${SMOKE_DATA_DIR}" LLM_PROVIDER=mock "${PYTHON_BIN}" - <<'PY'
import os
from pathlib import Path

from src.core.models import OutputLanguage, ReviewMode, ReviewRequest, VenueCollection, VenueDomain
from src.services.review_jobs import build_job_runner

data_dir = Path(os.environ["DATA_DIR"])
runner = build_job_runner()

def seed(name: str):
    paper = data_dir / "uploads" / name
    paper.parent.mkdir(parents=True, exist_ok=True)
    paper.write_text(
        f"{name}\n\nAbstract\nA seeded job for frontend filter smoke.\n\n1 Introduction\nContent.",
        encoding="utf-8",
    )
    return runner.create_job(
        ReviewRequest(
            paper_path=str(paper),
            review_mode=ReviewMode.QUICK_REVIEW,
            output_language=OutputLanguage.ZH,
            venue_domain=VenueDomain.CS,
            venue_collection=VenueCollection.CCFA,
            venue_code="AAAI",
        )
    )

seed("codex_filter_active.md")
seed("codex_filter_extra.md")
canceled = seed("codex_filter_canceled.md")
runner.cancel_job(canceled.job_id)
PY

DATA_DIR="${SMOKE_DATA_DIR}" \
APP_CORS_ORIGINS="${FRONTEND_URL}" \
LLM_PROVIDER=mock \
PORT="${BACKEND_PORT}" \
  "${PYTHON_BIN}" -m uvicorn src.api.app:app --host 127.0.0.1 --port "${BACKEND_PORT}" >/tmp/paper-review-filter-smoke-backend.log 2>&1 &
BACKEND_PID="$!"
wait_for_url "${BACKEND_URL}/health" "backend"

(
  cd "${ROOT_DIR}/frontend"
  VITE_API_BASE_URL="${BACKEND_URL}" npm run dev -- --host 127.0.0.1 --port "${FRONTEND_PORT}"
) >/tmp/paper-review-filter-smoke-frontend.log 2>&1 &
FRONTEND_PID="$!"
wait_for_url "${FRONTEND_URL}" "frontend"

"${CHROME}" \
  --headless=new \
  --disable-gpu \
  --remote-debugging-port="${CDP_PORT}" \
  --user-data-dir="/tmp/paper-review-filter-smoke-chrome-${CDP_PORT}" \
  about:blank >/tmp/paper-review-filter-smoke-chrome.log 2>&1 &
CHROME_PID="$!"

wait_for_url "http://127.0.0.1:${CDP_PORT}/json/version" "Chrome CDP"

"${PYTHON_BIN}" "${ROOT_DIR}/scripts/frontend_smoke.py" \
  --frontend-url "${FRONTEND_URL}" \
  --cdp-url "http://127.0.0.1:${CDP_PORT}" \
  --screenshot "${SMOKE_SCREENSHOT}" \
  --flow filter

echo "Frontend filter smoke screenshot: ${SMOKE_SCREENSHOT}"
echo "Frontend filter smoke data dir: ${SMOKE_DATA_DIR}"
