#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
CONTRACT_PATH="${ROOT_DIR}/docs/api/openapi.json"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

cd "${ROOT_DIR}"

"${PYTHON_BIN}" - "${CONTRACT_PATH}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.api.app import create_app

contract_path = Path(sys.argv[1])
if not contract_path.exists():
    raise SystemExit(f"{contract_path} is missing. Run scripts/export-openapi.sh")

expected = json.dumps(create_app().openapi(), ensure_ascii=False, indent=2, sort_keys=True) + "\n"
actual = contract_path.read_text(encoding="utf-8")
if actual != expected:
    raise SystemExit("docs/api/openapi.json is out of date. Run scripts/export-openapi.sh")

print("OpenAPI contract is up to date.")
PY
