from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from src.core.models import to_jsonable


class LocalArtifactStore:
    def __init__(self, root: Path) -> None:
        self.root = root

    def run_dir(self, run_id: str) -> Path:
        path = self.root / run_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def write_json(self, run_id: str, name: str, payload: Any) -> Path:
        path = self.run_dir(run_id) / name
        path.write_text(
            json.dumps(to_jsonable(payload), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return path

    def write_text(self, run_id: str, name: str, text: str) -> Path:
        path = self.run_dir(run_id) / name
        path.write_text(text, encoding="utf-8")
        return path
