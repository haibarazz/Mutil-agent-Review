from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol


class ArtifactStore(Protocol):
    def run_dir(self, run_id: str) -> Path:
        """Return the artifact directory for a run."""

    def write_json(self, run_id: str, name: str, payload: Any) -> Path:
        """Write a JSON artifact and return its path."""

    def write_text(self, run_id: str, name: str, text: str) -> Path:
        """Write a text artifact and return its path."""
