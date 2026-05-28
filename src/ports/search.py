from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class SearchResult:
    title: str
    url: str
    snippet: str


class SearchClient(Protocol):
    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        """Search external literature or web sources."""
