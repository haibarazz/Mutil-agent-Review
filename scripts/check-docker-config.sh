#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

if ! command -v docker >/dev/null 2>&1; then
  echo "docker is not installed; skipping docker compose config check."
  exit 0
fi

cd "${ROOT_DIR}"
docker compose config --quiet
