from __future__ import annotations

from src.ports.search import SearchResult


class NullSearchClient:
    def search(self, query: str, *, limit: int = 5) -> list[SearchResult]:
        return []
