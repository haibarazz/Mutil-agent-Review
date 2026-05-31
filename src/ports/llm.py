from __future__ import annotations

from collections.abc import Callable
from typing import Any, Protocol


JsonValidator = Callable[..., dict[str, Any]]


class LLMClient(Protocol):
    def complete_text(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        top_p: float | None = None,
        max_tokens: int | None = None,
    ) -> str:
        """Return plain text from an LLM call."""

    def complete_json(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        prompt_name: str | None = None,
        model: str | None = None,
        temperature: float = 0.2,
        top_p: float | None = None,
        max_tokens: int | None = None,
        validator: JsonValidator | None = None,
    ) -> dict[str, Any]:
        """Return a JSON-compatible object from an LLM call."""
