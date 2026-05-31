#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

cd "${ROOT_DIR}"
"${PYTHON_BIN}" -m unittest discover tests
"${PYTHON_BIN}" -m src.cli doctor
"${ROOT_DIR}/scripts/check-api-contract.sh"

cd "${ROOT_DIR}/frontend"
npm run build

if [[ "${CHECK_FRONTEND_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_FAILURE_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-failure-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_PRESET_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-preset-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_COMMAND_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-command-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_DESKTOP_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-desktop-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_UPLOAD_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-upload-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_CANCEL_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-cancel-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_RETRY_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-retry-smoke.sh"
fi

if [[ "${CHECK_FRONTEND_FILTER_SMOKE:-0}" == "1" ]]; then
  cd "${ROOT_DIR}"
  "${ROOT_DIR}/scripts/check-frontend-filter-smoke.sh"
fi
