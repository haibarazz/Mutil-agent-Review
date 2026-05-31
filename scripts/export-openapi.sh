#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${ROOT_DIR}/.venv/bin/python"
OUTPUT_PATH="${1:-docs/api/openapi.json}"

if [[ ! -x "${PYTHON_BIN}" ]]; then
  PYTHON_BIN="python"
fi

cd "${ROOT_DIR}"
mkdir -p "$(dirname "${OUTPUT_PATH}")"

"${PYTHON_BIN}" - "${OUTPUT_PATH}" <<'PY'
from __future__ import annotations

import json
import sys
from pathlib import Path

from src.api.app import create_app

output_path = Path(sys.argv[1])
schema = create_app().openapi()
output_path.write_text(
    json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
)
print(f"wrote {output_path}")
PY
