from __future__ import annotations

from pathlib import Path
from typing import Protocol

from src.core.models import ParsedPaper


class DocumentParser(Protocol):
    def parse(self, path: Path) -> ParsedPaper:
        """Parse a manuscript into structured paper text."""
