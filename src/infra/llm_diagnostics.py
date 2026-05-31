from __future__ import annotations

import json
import threading
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterator

from src.core.models import to_jsonable


_current_run_id: ContextVar[str] = ContextVar("llm_diagnostics_run_id", default="")
_collectors: dict[str, "LLMCallCollector"] = {}
_lock = threading.RLock()


@dataclass
class LLMCallCollector:
    """收集单个 run 内的 LLM 调用事件；只存安全摘要，不存 prompt 正文。"""

    run_id: str
    events: list[dict[str, Any]] = field(default_factory=list)

    def append(self, event: str, fields: dict[str, Any]) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": event,
            **_safe_fields(fields),
        }
        self.events.append(payload)

    def summary(self) -> dict[str, int]:
        return {
            "event_count": len(self.events),
            "call_count": sum(1 for event in self.events if event.get("event") == "start"),
            "error_count": sum(1 for event in self.events if event.get("event") == "error"),
            "fallback_count": sum(1 for event in self.events if event.get("event") == "fallback"),
        }

    def to_jsonl(self) -> str:
        return "\n".join(json.dumps(to_jsonable(event), ensure_ascii=False) for event in self.events)


def start_llm_call_collection(run_id: str) -> LLMCallCollector:
    with _lock:
        collector = LLMCallCollector(run_id=run_id)
        _collectors[run_id] = collector
        return collector


def stop_llm_call_collection(run_id: str) -> LLMCallCollector:
    with _lock:
        return _collectors.pop(run_id, LLMCallCollector(run_id=run_id))


@contextmanager
def llm_diagnostics_run(run_id: str | None) -> Iterator[None]:
    token = _current_run_id.set(str(run_id or ""))
    try:
        yield
    finally:
        _current_run_id.reset(token)


def record_llm_event(event: str, fields: dict[str, Any]) -> None:
    run_id = _current_run_id.get()
    if not run_id:
        return
    with _lock:
        collector = _collectors.get(run_id)
        if collector is None:
            return
        collector.append(event, fields)


def _safe_fields(fields: dict[str, Any]) -> dict[str, Any]:
    # 白名单字段：避免误把 prompt 正文、API key、响应正文写进本地产物。
    allowed = {
        "kind",
        "prompt",
        "requested_model",
        "model",
        "provider",
        "provider_model",
        "attempt",
        "max_attempts",
        "fallback",
        "from_model",
        "to_model",
        "reason",
        "temperature",
        "top_p",
        "max_tokens",
        "system_chars",
        "user_chars",
        "elapsed_ms",
        "error_type",
        "retryable",
    }
    return {
        key: value
        for key, value in fields.items()
        if key in allowed and value not in ("", None)
    }
